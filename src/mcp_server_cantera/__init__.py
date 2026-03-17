# Copyright Step Function, 2026
"""MCP Server for Cantera.

An MCP server wrapped around Cantera to facilitate use by an LLM for accurate 
equilibrium and kinetics calculations.
"""

__version__ = "0.1.0"
__author__ = "Dave Tew"

from mcp_server_cantera.server import main

__all__ = ["main"]
