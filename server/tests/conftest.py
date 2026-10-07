import sys
from pathlib import Path

import pytest
from starlette.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import auth  # noqa: E402
from app.server import create_app  # noqa: E402

POOL = "agents.global.proj-123.system.id.goog"
AGENT = f"principal://{POOL}/resources/aiplatform/reader-engine"
HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


def rpc(method: str, params: dict | None = None, id_: int = 1) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "method": method, "params": params or {}}


@pytest.fixture
def identities(monkeypatch):
    monkeypatch.setenv("MCP_READER_IDENTITIES", f"reader@example.iam.gserviceaccount.com,{AGENT}")
    monkeypatch.setenv("MCP_ADMIN_IDENTITIES", "admin@example.iam.gserviceaccount.com")
    monkeypatch.delenv("MCP_ALLOW_ANONYMOUS", raising=False)


@pytest.fixture
def tokens(monkeypatch):
    """Stub the signature check: a token is `claims-<name>` mapped to fixed claims."""
    claims = {
        "reader": {"email": "reader@example.iam.gserviceaccount.com", "email_verified": True,
                   "sub": "1"},
        "admin": {"email": "admin@example.iam.gserviceaccount.com", "email_verified": True,
                  "sub": "2"},
        "stranger": {"email": "x@example.iam.gserviceaccount.com", "email_verified": True,
                     "sub": "3"},
        "unverified": {"email": "admin@example.iam.gserviceaccount.com", "email_verified": False,
                       "sub": "4"},
        "engine": {"sub": f"spiffe://{POOL}/resources/aiplatform/reader-engine"},
    }

    def fake_verify(token: str) -> dict:
        if token not in claims:
            raise ValueError("bad signature")
        return claims[token]

    monkeypatch.setattr(auth, "verify_token", fake_verify)


@pytest.fixture(scope="session")
def client():
    # FastMCP's session manager can only be started once per process, so one client
    # (and one lifespan) serves every test; identities are read per request. The host
    # must be localhost: FastMCP rejects other Host headers (421) when bound to 127.0.0.1.
    with TestClient(create_app(), base_url="http://localhost:8080") as c:
        yield c


@pytest.fixture(autouse=True)
def _restore_notes():
    from app.server import NOTES

    before = dict(NOTES)
    yield
    NOTES.clear()
    NOTES.update(before)


def bearer(token: str) -> dict:
    return {**HEADERS, "Authorization": f"Bearer {token}"}
