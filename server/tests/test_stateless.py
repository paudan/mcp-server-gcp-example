from conftest import HEADERS, rpc


def test_unknown_session_id_is_not_a_404(client, monkeypatch):
    """A request carrying a session id this process never issued must still be served:
    another Cloud Run instance may have issued it. A 404 here is what MCP clients
    report as `Session terminated`."""
    monkeypatch.setenv("MCP_ALLOW_ANONYMOUS", "true")
    r = client.post("/mcp", json=rpc("tools/list"),
                    headers={**HEADERS, "mcp-session-id": "issued-by-another-instance"})
    assert r.status_code == 200


def test_initialize_issues_no_session_id(client, monkeypatch):
    monkeypatch.setenv("MCP_ALLOW_ANONYMOUS", "true")
    init = rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                              "clientInfo": {"name": "t", "version": "0"}})
    r = client.post("/mcp", json=init, headers=HEADERS)
    assert r.status_code == 200
    assert "mcp-session-id" not in r.headers
