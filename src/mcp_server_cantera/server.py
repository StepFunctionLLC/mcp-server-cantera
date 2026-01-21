"""Main MCP server module for Cantera integration.

This module provides an MCP server that wraps Cantera functionality to enable
LLMs to perform accurate equilibrium and kinetics calculations.
"""

import logging
from typing import Any

import cantera as ct
from mcp.server import Server
from mcp.server.stdio import stdio_server

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create the server instance
app = Server("mcp-server-cantera")


@app.list_tools()
async def list_tools() -> list[dict[str, Any]]:
    """List available tools for Cantera calculations.
    
    Returns:
        List of tool definitions that can be used by the MCP client.
    """
    return [
        {
            "name": "get_gas_properties",
            "description": "Get thermodynamic properties of a gas mixture at specified conditions",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "mechanism": {
                        "type": "string",
                        "description": "Cantera mechanism file or mechanism name (e.g., 'gri30.yaml')",
                    },
                    "temperature": {
                        "type": "number",
                        "description": "Temperature in Kelvin",
                    },
                    "pressure": {
                        "type": "number",
                        "description": "Pressure in Pascals",
                    },
                    "composition": {
                        "type": "string",
                        "description": "Gas composition in Cantera format (e.g., 'CH4:1, O2:2, N2:7.52')",
                    },
                },
                "required": ["mechanism", "temperature", "pressure", "composition"],
            },
        },
        {
            "name": "equilibrate_gas",
            "description": "Calculate equilibrium composition of a gas mixture",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "mechanism": {
                        "type": "string",
                        "description": "Cantera mechanism file or mechanism name",
                    },
                    "temperature": {
                        "type": "number",
                        "description": "Temperature in Kelvin",
                    },
                    "pressure": {
                        "type": "number",
                        "description": "Pressure in Pascals",
                    },
                    "composition": {
                        "type": "string",
                        "description": "Initial gas composition in Cantera format",
                    },
                    "basis": {
                        "type": "string",
                        "description": "Equilibration basis: 'TP' (temperature-pressure), 'HP' (enthalpy-pressure), 'SP' (entropy-pressure), 'UV' (internal energy-volume)",
                        "enum": ["TP", "HP", "SP", "UV"],
                        "default": "TP",
                    },
                },
                "required": ["mechanism", "temperature", "pressure", "composition"],
            },
        },
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[dict[str, Any]]:
    """Execute a tool with the given arguments.
    
    Args:
        name: Name of the tool to execute
        arguments: Tool arguments
        
    Returns:
        List of text content results from the tool execution
    """
    try:
        if name == "get_gas_properties":
            return await get_gas_properties(
                mechanism=arguments["mechanism"],
                temperature=arguments["temperature"],
                pressure=arguments["pressure"],
                composition=arguments["composition"],
            )
        elif name == "equilibrate_gas":
            return await equilibrate_gas(
                mechanism=arguments["mechanism"],
                temperature=arguments["temperature"],
                pressure=arguments["pressure"],
                composition=arguments["composition"],
                basis=arguments.get("basis", "TP"),
            )
        else:
            raise ValueError(f"Unknown tool: {name}")
            
    except Exception as e:
        logger.error(f"Error executing tool {name}: {e}")
        return [
            {
                "type": "text",
                "text": f"Error: {str(e)}",
            }
        ]


async def get_gas_properties(
    mechanism: str, temperature: float, pressure: float, composition: str
) -> list[dict[str, Any]]:
    """Get thermodynamic properties of a gas mixture.
    
    Args:
        mechanism: Cantera mechanism file or name
        temperature: Temperature in Kelvin
        pressure: Pressure in Pascals
        composition: Gas composition string
        
    Returns:
        List containing text result with gas properties
    """
    # Create gas object
    gas = ct.Solution(mechanism)
    gas.TPX = temperature, pressure, composition
    
    # Format properties
    result = f"""Gas Properties:
Temperature: {gas.T:.2f} K
Pressure: {gas.P:.2f} Pa
Density: {gas.density:.4f} kg/m³
Mean molecular weight: {gas.mean_molecular_weight:.4f} g/mol
Enthalpy: {gas.enthalpy_mass:.2f} J/kg
Entropy: {gas.entropy_mass:.2f} J/kg/K
Cp: {gas.cp_mass:.2f} J/kg/K
Cv: {gas.cv_mass:.2f} J/kg/K

Mole Fractions:
"""
    
    for species, mole_frac in zip(gas.species_names, gas.X):
        if mole_frac > 1e-10:  # Only show species with significant concentrations
            result += f"  {species}: {mole_frac:.6e}\n"
    
    return [{"type": "text", "text": result}]


async def equilibrate_gas(
    mechanism: str, temperature: float, pressure: float, composition: str, basis: str = "TP"
) -> list[dict[str, Any]]:
    """Calculate equilibrium composition of a gas mixture.
    
    Args:
        mechanism: Cantera mechanism file or name
        temperature: Temperature in Kelvin
        pressure: Pressure in Pascals
        composition: Initial gas composition string
        basis: Equilibration basis (TP, HP, SP, UV)
        
    Returns:
        List containing text result with equilibrium composition
    """
    # Create gas object
    gas = ct.Solution(mechanism)
    gas.TPX = temperature, pressure, composition
    
    # Store initial state
    initial_T = gas.T
    initial_P = gas.P
    
    # Equilibrate
    gas.equilibrate(basis)
    
    # Format results
    result = f"""Equilibrium Calculation (basis: {basis}):

Initial State:
Temperature: {initial_T:.2f} K
Pressure: {initial_P:.2f} Pa

Equilibrium State:
Temperature: {gas.T:.2f} K
Pressure: {gas.P:.2f} Pa
Density: {gas.density:.4f} kg/m³
Enthalpy: {gas.enthalpy_mass:.2f} J/kg
Entropy: {gas.entropy_mass:.2f} J/kg/K

Equilibrium Mole Fractions:
"""
    
    for species, mole_frac in zip(gas.species_names, gas.X):
        if mole_frac > 1e-10:  # Only show species with significant concentrations
            result += f"  {species}: {mole_frac:.6e}\n"
    
    return [{"type": "text", "text": result}]


def main() -> None:
    """Main entry point for the MCP server."""
    import asyncio
    
    logger.info("Starting MCP Server for Cantera")
    asyncio.run(stdio_server(app))


if __name__ == "__main__":
    main()
