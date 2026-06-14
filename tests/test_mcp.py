"""MCP server builds and registers its tools. Skipped if the [mcp] extra (fastmcp) is absent,
so CI on core+dev stays green."""
import pytest

pytest.importorskip("fastmcp")

from specrag import mcp_server  # noqa: E402


def test_server_builds():
    assert mcp_server.mcp.name == "specrag"


def test_tools_registered_with_fastmcp():
    # assert the tools are actually registered with the FastMCP instance, not just that the
    # module has the attribute (which would pass even if @mcp.tool were removed).
    import asyncio
    import inspect

    for name in ("verify_code_against_card", "verify_file_against_card", "check_code_stamp"):
        got = mcp_server.mcp.get_tool(name)
        if inspect.isawaitable(got):
            got = asyncio.run(got)
        assert got is not None
