"""Who is calling, and which role that makes them.

Cloud Run IAM already admits only listed invokers; this maps each admitted caller's
ID token to `reader` (query tools) or `admin` (also `delete_note`), so a caller's
reach is decided on the server, not by what its own client chooses to call.

Two kinds of token arrive:
- a service account's, signed by Google's OAuth2 keys;
- an Agent Runtime engine's, issued by the project's agent workload identity pool,
  whose `sub` is `spiffe://<pool>/...` and whose keys are served at `<iss>/openid/jwks`.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass

import google.auth.transport.requests
import jwt as pyjwt
from google.auth import jwt
from google.oauth2 import id_token
from starlette.responses import JSONResponse

from . import config

logger = logging.getLogger(__name__)

ROLE_READER = "reader"
ROLE_ADMIN = "admin"
LOCAL_CALLER = "local"

_STATE_KEY = "caller"
_SPIFFE = "spiffe://"
_AGENT_ISSUER = re.compile(
    r"^https://sts\.googleapis\.com/v1/projects/(?P<number>\d+)/locations/global/"
    r"workloadIdentityPools/(?P<pool>agents\.global\.proj-(?P=number)\.system\.id\.goog)$"
)
_PRINCIPAL = re.compile(r"^principal://(agents\.global\.proj-\d+\.system\.id\.goog)/")

_verified: dict[str, tuple[float, dict]] = {}
_jwks_clients: dict[str, pyjwt.PyJWKClient] = {}


@dataclass(frozen=True)
class Caller:
    principal: str
    role: str


def caller_from_claims(claims: dict) -> Caller | None:
    """The caller's role, or None for an identity on neither list. An `email` only
    counts when Google marks it verified."""
    principals = [claims["email"]] if claims.get("email") and claims.get("email_verified") else []
    if claims.get("sub"):
        principals.append(claims["sub"])
        if claims["sub"].startswith(_SPIFFE):
            # Tokens say `spiffe://<pool>/...`; IAM and our role lists say `principal://<pool>/...`.
            principals.append("principal://" + claims["sub"][len(_SPIFFE):])
    for role, allowed in ((ROLE_ADMIN, config.admin_identities()),
                          (ROLE_READER, config.reader_identities())):
        for principal in principals:
            if principal in allowed:
                return Caller(principal, role)
    return None


def _trusted_agent_pools() -> set[str]:
    """Agent pools worth believing: only those the role lists already name."""
    listed = config.admin_identities() | config.reader_identities()
    return {m.group(1) for identity in listed if (m := _PRINCIPAL.match(identity))}


def _verify_agent_token(token: str, issuer: str, pool: str) -> dict:
    if pool not in _trusted_agent_pools():
        raise ValueError(f"agent identity pool {pool} is not named by any role list")
    client = _jwks_clients.setdefault(
        issuer, pyjwt.PyJWKClient(f"{issuer}/openid/jwks", cache_keys=True, timeout=10)
    )
    claims = pyjwt.decode(
        token,
        client.get_signing_key_from_jwt(token).key,
        algorithms=["RS256"],
        issuer=issuer,
        options={"verify_aud": False, "require": ["exp", "iss", "sub"]},
    )
    if not str(claims["sub"]).startswith(f"{_SPIFFE}{pool}/"):
        raise ValueError("subject does not belong to the issuing pool")
    return claims


def verify_token(token: str) -> dict:
    """Claims of an ID token from Google or from an agent identity pool, checked once
    per token. The audience is not compared: Cloud Run's IAM check already bound the
    token to this service before the request got here."""
    now = time.time()
    cached = _verified.get(token)
    if cached and cached[0] > now:
        return cached[1]
    issuer = str(jwt.decode(token, verify=False).get("iss", ""))
    agent = _AGENT_ISSUER.match(issuer)
    if agent:
        claims = _verify_agent_token(token, issuer, agent.group("pool"))
    else:
        claims = id_token.verify_oauth2_token(token, google.auth.transport.requests.Request())
    _verified[token] = (float(claims["exp"]), claims)
    for stale in [t for t, (exp, _) in _verified.items() if exp <= now]:
        del _verified[stale]
    return claims


def describe_token(token: str) -> dict:
    """Header and claims of a rejected token, read without verifying and never the
    token itself, so a rejection can be diagnosed from the logs."""
    try:
        header = jwt.decode_header(token)
        claims = jwt.decode(token, verify=False)
    except Exception:
        return {"unreadable": True}
    wanted = {"kid": header.get("kid"), "alg": header.get("alg")}
    wanted.update({n: claims.get(n) for n in ("iss", "aud", "sub", "email", "azp")})
    return {n: v for n, v in wanted.items() if v is not None}


def caller_of(request) -> Caller | None:
    """The caller the middleware recorded; the local caller when there is no HTTP request."""
    if request is None:
        return Caller(LOCAL_CALLER, ROLE_ADMIN)
    return request.scope.get("state", {}).get(_STATE_KEY)


class CallerAuthMiddleware:
    """Authenticates every HTTP request before MCP sees it: 401 for a missing or
    invalid token, 403 for a valid token whose identity is on no role list."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        caller = await self._authenticate(scope)
        if isinstance(caller, JSONResponse):
            await caller(scope, receive, send)
            return
        scope.setdefault("state", {})[_STATE_KEY] = caller
        await self.app(scope, receive, send)

    async def _authenticate(self, scope) -> Caller | JSONResponse:
        if config.allow_anonymous():
            return Caller("anonymous", ROLE_ADMIN)
        header = dict(scope["headers"]).get(b"authorization", b"").decode()
        scheme, _, token = header.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return JSONResponse({"error": "missing bearer token"}, status_code=401)
        try:
            claims = await asyncio.to_thread(verify_token, token)
        except Exception as exc:
            logger.warning("rejected token: %s; token is %s", exc, describe_token(token))
            return JSONResponse({"error": "invalid token"}, status_code=401)
        caller = caller_from_claims(claims)
        if caller is None:
            logger.warning("caller on no role list: %s", claims.get("email") or claims.get("sub"))
            return JSONResponse({"error": "caller has no role on this server"}, status_code=403)
        return caller
