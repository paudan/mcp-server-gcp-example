import json

from conftest import bearer, rpc


def _body(response) -> dict:
    """The JSON-RPC message, whether sent as JSON or as a single SSE event."""
    text = response.text
    if response.headers["content-type"].startswith("text/event-stream"):
        text = next(line[6:] for line in text.splitlines() if line.startswith("data: "))
    return json.loads(text)


def _tool_names(client, token) -> set[str]:
    r = client.post("/mcp", json=rpc("tools/list"), headers=bearer(token))
    return {t["name"] for t in _body(r)["result"]["tools"]}


def test_reader_sees_only_query_tools(client, identities, tokens):
    assert _tool_names(client, "reader") == {"list_notes", "get_note"}


def test_admin_also_sees_delete(client, identities, tokens):
    assert _tool_names(client, "admin") == {"list_notes", "get_note", "delete_note"}


def test_reader_cannot_call_an_admin_tool(client, identities, tokens):
    call = rpc("tools/call", {"name": "delete_note", "arguments": {"note_id": "welcome"}})
    msg = _body(client.post("/mcp", json=call, headers=bearer("reader")))
    assert msg["result"]["isError"] is True
    assert "not available" in msg["result"]["content"][0]["text"]


def test_admin_can_call_it(client, identities, tokens):
    call = rpc("tools/call", {"name": "delete_note", "arguments": {"note_id": "deploy"}})
    msg = _body(client.post("/mcp", json=call, headers=bearer("admin")))
    assert msg["result"]["isError"] is False
