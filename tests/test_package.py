# Copyright Step Function, 2026
"""Basic tests for the package structure."""

import pytest


def test_package_import():
    """Test that the package can be imported."""
    import mcp_server_cantera
    
    assert mcp_server_cantera.__version__ == "0.1.0"
    assert mcp_server_cantera.__author__ == "Dave Tew"


def test_main_function_exists():
    """Test that the main function exists."""
    from mcp_server_cantera import main
    
    assert callable(main)


def test_server_module_import():
    """Test that the server module can be imported."""
    from mcp_server_cantera import server
    
    assert hasattr(server, "main")
    assert hasattr(server, "mcp")


def test_server_instructions_configured():
    """Test that the MCP server has instructions set for hierarchical agent integration."""
    from mcp_server_cantera.server import mcp
    
    assert mcp.instructions is not None
    assert len(mcp.instructions) > 0
    assert "MULTI-AGENT" in mcp.instructions.upper()
    assert "WORKFLOW" in mcp.instructions.upper()


def test_nasa_gas_resource_callable():
    """Test that the nasa_gas resource function is callable and returns meaningful data."""
    from mcp_server_cantera.server import nasa_gas
    
    result = nasa_gas()
    assert isinstance(result, str)
    assert "NASA Gas Database" in result
    assert "species available" in result
    assert "O2" in result
