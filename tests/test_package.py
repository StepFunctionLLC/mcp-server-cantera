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
    assert hasattr(server, "app")
