from conftest import HEADERS, bearer, rpc


def test_missing_token_is_401(client, identities):
    assert client.post("/mcp", json=rpc("tools/list"), headers=HEADERS).status_code == 401


def test_invalid_token_is_401(client, identities, tokens):
    assert client.post("/mcp", json=rpc("tools/list"), headers=bearer("junk")).status_code == 401


def test_valid_token_without_role_is_403(client, identities, tokens):
    r = client.post("/mcp", json=rpc("tools/list"), headers=bearer("stranger"))
    assert r.status_code == 403


def test_unverified_email_does_not_count(client, identities, tokens):
    r = client.post("/mcp", json=rpc("tools/list"), headers=bearer("unverified"))
    assert r.status_code == 403


def test_agent_identity_subject_matches_principal_form(client, identities, tokens):
    r = client.post("/mcp", json=rpc("tools/list"), headers=bearer("engine"))
    assert r.status_code == 200
