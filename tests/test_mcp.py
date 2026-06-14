"""MCP server builds and registers its tools. Skipped if the [mcp] extra (fastmcp) is absent,
so CI on core+dev stays green."""
import pytest

pytest.importorskip("fastmcp")

from specrag import mcp_server  # noqa: E402


def test_server_builds():
    assert mcp_server.mcp.name == "specrag"


def test_tools_defined():
    for name in ("verify_code_against_card", "verify_file_against_card", "check_code_stamp"):
        assert hasattr(mcp_server, name)
