"""Main MCP server module for Cantera integration.

This module provides an MCP server that wraps Cantera functionality to enable
LLMs to perform accurate equilibrium, thermodynamic, and transport calculations.
"""

import logging
import os
from pathlib import Path
from typing import Any

import cantera as ct
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =============================================================================
# Custom Mechanism Discovery
# =============================================================================

def get_custom_mechanisms_dir() -> Path:
    """Get path to custom mechanisms directory.
    
    Returns the mechanisms/ folder at the package root level.
    Path: server.py -> mcp_server_cantera -> src -> mcp-server-cantera -> mechanisms
    """
    # Navigate from server.py -> mcp_server_cantera -> src -> package_root -> mechanisms
    return Path(__file__).parent.parent.parent / "mechanisms"


def discover_custom_mechanisms() -> list[tuple[str, str, Path]]:
    """Discover custom mechanism files in mechanisms/ folder.
    
    Returns:
        List of tuples: (filename, description, full_path)
    """
    mech_dir = get_custom_mechanisms_dir()
    mechanisms = []
    if mech_dir.exists():
        for f in sorted(mech_dir.glob("*.yaml")):
            mechanisms.append((f.name, f"Custom mechanism: {f.stem}", f))
        for f in sorted(mech_dir.glob("*.yml")):
            mechanisms.append((f.name, f"Custom mechanism: {f.stem}", f))
    return mechanisms


def resolve_mechanism(mechanism: str) -> str:
    """Resolve mechanism name to full path if it's a custom mechanism.
    
    This allows users to specify just the filename (e.g., 'JetSurf2.yaml')
    and have it automatically resolved to the full path in the mechanisms/ folder.
    
    Args:
        mechanism: Mechanism name or path
        
    Returns:
        Full path to mechanism file if found in custom folder, otherwise original string
    """
    # If it looks like an absolute path or built-in, return as-is first
    if os.path.isabs(mechanism) or os.path.exists(mechanism):
        return mechanism
    
    # Check if it exists in the custom mechanisms folder
    custom_dir = get_custom_mechanisms_dir()
    custom_path = custom_dir / mechanism
    if custom_path.exists():
        logger.info(f"Resolved mechanism '{mechanism}' to custom path: {custom_path}")
        return str(custom_path)
    
    # Return as-is for built-in mechanisms (gri30.yaml, etc.)
    return mechanism


# Create the server instance
app = Server("mcp-server-cantera")


# =============================================================================
# Tool Definitions
# =============================================================================

@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools for Cantera calculations.
    
    Returns:
        List of tool definitions that can be used by the MCP client.
    """
    return [
        Tool(
            name="get_gas_properties",
            description="Get comprehensive thermodynamic and transport properties of a gas mixture at specified conditions. Returns temperature, pressure, density, enthalpy, entropy, heat capacities, viscosity, thermal conductivity, speed of sound, and mole fractions.",
            inputSchema={
                "type": "object",
                "properties": {
                    "mechanism": {
                        "type": "string",
                        "description": "Cantera mechanism file or mechanism name (e.g., 'gri30.yaml' for combustion, 'air.yaml' for simple air)",
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
                        "description": "Gas composition in Cantera format (e.g., 'CH4:1, O2:2, N2:7.52' or 'N2:0.79, O2:0.21')",
                    },
                },
                "required": ["mechanism", "temperature", "pressure", "composition"],
            },
        ),
        Tool(
            name="get_transport_properties",
            description="Get detailed transport properties of a gas mixture including viscosity, thermal conductivity, and species diffusion coefficients.",
            inputSchema={
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
                        "description": "Gas composition in Cantera format",
                    },
                },
                "required": ["mechanism", "temperature", "pressure", "composition"],
            },
        ),
        Tool(
            name="equilibrate_gas",
            description="Calculate equilibrium composition of a gas mixture. Returns equilibrium state, heat release, and Gibbs free energy change.",
            inputSchema={
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
                        "description": "Equilibration basis: 'TP' (constant T,P), 'HP' (adiabatic, constant P), 'SP' (isentropic), 'UV' (constant U,V)",
                        "enum": ["TP", "HP", "SP", "UV"],
                        "default": "TP",
                    },
                },
                "required": ["mechanism", "temperature", "pressure", "composition"],
            },
        ),
        Tool(
            name="calculate_adiabatic_flame_temperature",
            description="Calculate the adiabatic flame temperature for combustion of a fuel with an oxidizer at a given equivalence ratio.",
            inputSchema={
                "type": "object",
                "properties": {
                    "mechanism": {
                        "type": "string",
                        "description": "Cantera mechanism file (e.g., 'gri30.yaml' for methane combustion)",
                    },
                    "fuel": {
                        "type": "string",
                        "description": "Fuel composition (e.g., 'CH4:1' or 'H2:1' or 'CH4:0.9, C2H6:0.1')",
                    },
                    "oxidizer": {
                        "type": "string",
                        "description": "Oxidizer composition (e.g., 'O2:1, N2:3.76' for air)",
                    },
                    "equivalence_ratio": {
                        "type": "number",
                        "description": "Equivalence ratio (phi). phi=1 is stoichiometric, phi<1 is lean, phi>1 is rich",
                    },
                    "initial_temperature": {
                        "type": "number",
                        "description": "Initial temperature in Kelvin (typically 298.15 K)",
                    },
                    "pressure": {
                        "type": "number",
                        "description": "Pressure in Pascals",
                    },
                },
                "required": ["mechanism", "fuel", "oxidizer", "equivalence_ratio", "initial_temperature", "pressure"],
            },
        ),
        Tool(
            name="get_species_properties",
            description="Get detailed thermodynamic properties for a specific species from a mechanism file.",
            inputSchema={
                "type": "object",
                "properties": {
                    "mechanism": {
                        "type": "string",
                        "description": "Cantera mechanism file or mechanism name",
                    },
                    "species_name": {
                        "type": "string",
                        "description": "Name of the species (e.g., 'CH4', 'O2', 'H2O')",
                    },
                    "temperature": {
                        "type": "number",
                        "description": "Temperature in Kelvin for property evaluation",
                    },
                },
                "required": ["mechanism", "species_name", "temperature"],
            },
        ),
        Tool(
            name="list_available_mechanisms",
            description="List commonly available Cantera mechanism files with descriptions of their applications.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="list_species_in_mechanism",
            description="List all species defined in a Cantera mechanism file.",
            inputSchema={
                "type": "object",
                "properties": {
                    "mechanism": {
                        "type": "string",
                        "description": "Cantera mechanism file or mechanism name",
                    },
                },
                "required": ["mechanism"],
            },
        ),
    ]


# =============================================================================
# Tool Router
# =============================================================================

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
        elif name == "get_transport_properties":
            return await get_transport_properties(
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
        elif name == "calculate_adiabatic_flame_temperature":
            return await calculate_adiabatic_flame_temperature(
                mechanism=arguments["mechanism"],
                fuel=arguments["fuel"],
                oxidizer=arguments["oxidizer"],
                equivalence_ratio=arguments["equivalence_ratio"],
                initial_temperature=arguments["initial_temperature"],
                pressure=arguments["pressure"],
            )
        elif name == "get_species_properties":
            return await get_species_properties(
                mechanism=arguments["mechanism"],
                species_name=arguments["species_name"],
                temperature=arguments["temperature"],
            )
        elif name == "list_available_mechanisms":
            return await list_available_mechanisms()
        elif name == "list_species_in_mechanism":
            return await list_species_in_mechanism(
                mechanism=arguments["mechanism"],
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


# =============================================================================
# Tool Implementations
# =============================================================================

async def get_gas_properties(
    mechanism: str, temperature: float, pressure: float, composition: str
) -> list[dict[str, Any]]:
    """Get comprehensive thermodynamic and transport properties of a gas mixture.
    
    Args:
        mechanism: Cantera mechanism file or name
        temperature: Temperature in Kelvin
        pressure: Pressure in Pascals
        composition: Gas composition string
        
    Returns:
        List containing text result with gas properties
    """
    # Resolve custom mechanism path
    mechanism = resolve_mechanism(mechanism)
    
    # Create gas object
    gas = ct.Solution(mechanism)
    gas.TPX = temperature, pressure, composition
    
    # Calculate derived properties
    gamma = gas.cp / gas.cv  # Heat capacity ratio
    speed_of_sound = (gamma * ct.gas_constant * temperature / gas.mean_molecular_weight) ** 0.5
    
    # Format properties
    result = f"""Gas Properties for {mechanism}:

=== Thermodynamic State ===
Temperature:           {gas.T:.2f} K
Pressure:              {gas.P:.2f} Pa ({gas.P/1e5:.4f} bar)
Density:               {gas.density:.6f} kg/m³
Mean molecular weight: {gas.mean_molecular_weight:.4f} g/mol

=== Thermodynamic Properties ===
Specific enthalpy (mass):  {gas.enthalpy_mass/1000:.4f} kJ/kg
Specific entropy (mass):   {gas.entropy_mass/1000:.6f} kJ/(kg·K)
Specific Cp (mass):        {gas.cp_mass:.4f} J/(kg·K)
Specific Cv (mass):        {gas.cv_mass:.4f} J/(kg·K)
Heat capacity ratio γ:     {gamma:.6f}
Internal energy (mass):    {gas.int_energy_mass/1000:.4f} kJ/kg
Gibbs free energy (mass):  {gas.gibbs_mass/1000:.4f} kJ/kg

=== Transport Properties ===
Dynamic viscosity:         {gas.viscosity:.6e} Pa·s
Thermal conductivity:      {gas.thermal_conductivity:.6f} W/(m·K)
Speed of sound (ideal):    {speed_of_sound:.2f} m/s

=== Mole Fractions ===
"""
    
    for species, mole_frac in zip(gas.species_names, gas.X):
        if mole_frac > 1e-10:
            result += f"  {species}: {mole_frac:.6e}\n"
    
    return [{"type": "text", "text": result}]


async def get_transport_properties(
    mechanism: str, temperature: float, pressure: float, composition: str
) -> list[dict[str, Any]]:
    """Get detailed transport properties of a gas mixture.
    
    Args:
        mechanism: Cantera mechanism file or name
        temperature: Temperature in Kelvin
        pressure: Pressure in Pascals
        composition: Gas composition string
        
    Returns:
        List containing text result with transport properties
    """
    # Resolve custom mechanism path
    mechanism = resolve_mechanism(mechanism)
    
    # Create gas object
    gas = ct.Solution(mechanism)
    gas.TPX = temperature, pressure, composition
    
    # Get mixture-averaged diffusion coefficients
    mix_diff_coeffs = gas.mix_diff_coeffs
    
    # Calculate Prandtl number
    Pr = gas.cp * gas.viscosity / gas.thermal_conductivity
    
    result = f"""Transport Properties for {mechanism}:

=== Conditions ===
Temperature: {gas.T:.2f} K
Pressure:    {gas.P:.2f} Pa

=== Mixture Transport Properties ===
Dynamic viscosity (μ):     {gas.viscosity:.6e} Pa·s
Kinematic viscosity (ν):   {gas.viscosity/gas.density:.6e} m²/s
Thermal conductivity (k):  {gas.thermal_conductivity:.6f} W/(m·K)
Thermal diffusivity (α):   {gas.thermal_conductivity/(gas.density*gas.cp):.6e} m²/s
Prandtl number (Pr):       {Pr:.4f}

=== Species Mixture-Averaged Diffusion Coefficients ===
"""
    
    for species, D, X in zip(gas.species_names, mix_diff_coeffs, gas.X):
        if X > 1e-10:
            result += f"  {species}: D = {D:.6e} m²/s\n"
    
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
    # Resolve custom mechanism path
    mechanism = resolve_mechanism(mechanism)
    
    # Create gas object
    gas = ct.Solution(mechanism)
    gas.TPX = temperature, pressure, composition
    
    # Store initial state
    initial_T = gas.T
    initial_P = gas.P
    initial_H = gas.enthalpy_mass
    initial_G = gas.gibbs_mass
    
    # Equilibrate
    gas.equilibrate(basis)
    
    # Calculate changes
    delta_H = gas.enthalpy_mass - initial_H  # Heat release (negative = exothermic)
    delta_G = gas.gibbs_mass - initial_G
    
    # Format results
    result = f"""Equilibrium Calculation (basis: {basis}):

=== Initial State ===
Temperature: {initial_T:.2f} K
Pressure:    {initial_P:.2f} Pa

=== Equilibrium State ===
Temperature: {gas.T:.2f} K
Pressure:    {gas.P:.2f} Pa
Density:     {gas.density:.6f} kg/m³

=== Thermodynamic Changes ===
ΔH (enthalpy change): {delta_H/1000:.4f} kJ/kg {"(exothermic)" if delta_H < 0 else "(endothermic)"}
ΔG (Gibbs change):    {delta_G/1000:.4f} kJ/kg

=== Equilibrium State Properties ===
Enthalpy:            {gas.enthalpy_mass/1000:.4f} kJ/kg
Entropy:             {gas.entropy_mass/1000:.6f} kJ/(kg·K)
Gibbs free energy:   {gas.gibbs_mass/1000:.4f} kJ/kg

=== Equilibrium Mole Fractions ===
"""
    
    for species, mole_frac in zip(gas.species_names, gas.X):
        if mole_frac > 1e-10:
            result += f"  {species}: {mole_frac:.6e}\n"
    
    return [{"type": "text", "text": result}]


async def calculate_adiabatic_flame_temperature(
    mechanism: str, fuel: str, oxidizer: str, equivalence_ratio: float,
    initial_temperature: float, pressure: float
) -> list[dict[str, Any]]:
    """Calculate adiabatic flame temperature for combustion.
    
    Args:
        mechanism: Cantera mechanism file
        fuel: Fuel composition string
        oxidizer: Oxidizer composition string
        equivalence_ratio: Equivalence ratio (phi)
        initial_temperature: Initial temperature in Kelvin
        pressure: Pressure in Pascals
        
    Returns:
        List containing text result with flame temperature and products
    """
    # Resolve custom mechanism path
    mechanism = resolve_mechanism(mechanism)
    
    # Create gas object
    gas = ct.Solution(mechanism)
    
    # Set the equivalence ratio
    gas.set_equivalence_ratio(equivalence_ratio, fuel, oxidizer)
    gas.TP = initial_temperature, pressure
    
    # Store initial state
    initial_H = gas.enthalpy_mass
    initial_composition = dict(zip(gas.species_names, gas.X))
    
    # Equilibrate at constant enthalpy and pressure (adiabatic)
    gas.equilibrate('HP')
    
    # Calculate heat release
    heat_release = -(gas.enthalpy_mass - initial_H)  # Positive = heat released
    
    result = f"""Adiabatic Flame Temperature Calculation:

=== Combustion Setup ===
Mechanism:          {mechanism}
Fuel:               {fuel}
Oxidizer:           {oxidizer}
Equivalence ratio:  {equivalence_ratio:.3f} {"(stoichiometric)" if abs(equivalence_ratio - 1.0) < 0.01 else "(lean)" if equivalence_ratio < 1 else "(rich)"}
Initial temperature: {initial_temperature:.2f} K
Pressure:           {pressure:.2f} Pa ({pressure/1e5:.4f} bar)

=== Results ===
Adiabatic flame temperature: {gas.T:.2f} K ({gas.T - 273.15:.2f} °C)
Temperature rise:            {gas.T - initial_temperature:.2f} K

=== Major Product Species (X > 0.1%) ===
"""
    
    for species, mole_frac in zip(gas.species_names, gas.X):
        if mole_frac > 0.001:
            result += f"  {species}: {mole_frac*100:.4f}%\n"
    
    result += f"""
=== Minor Product Species (0.01% < X < 0.1%) ===
"""
    for species, mole_frac in zip(gas.species_names, gas.X):
        if 0.0001 < mole_frac <= 0.001:
            result += f"  {species}: {mole_frac*100:.6f}%\n"
    
    return [{"type": "text", "text": result}]


async def get_species_properties(
    mechanism: str, species_name: str, temperature: float
) -> list[dict[str, Any]]:
    """Get detailed properties for a specific species.
    
    Args:
        mechanism: Cantera mechanism file or name
        species_name: Name of the species
        temperature: Temperature for property evaluation in Kelvin
        
    Returns:
        List containing text result with species properties
    """
    # Resolve custom mechanism path
    mechanism = resolve_mechanism(mechanism)
    
    # Create gas object
    gas = ct.Solution(mechanism)
    
    # Check if species exists
    if species_name not in gas.species_names:
        return [{"type": "text", "text": f"Error: Species '{species_name}' not found in mechanism '{mechanism}'. Use list_species_in_mechanism to see available species."}]
    
    # Get species index
    idx = gas.species_index(species_name)
    species = gas.species(species_name)
    
    # Set temperature for property evaluation
    gas.TPX = temperature, ct.one_atm, f"{species_name}:1"
    
    # Get thermodynamic data
    thermo = species.thermo
    
    result = f"""Species Properties for {species_name}:

=== Basic Information ===
Name:              {species.name}
Molecular weight:  {species.molecular_weight:.4f} g/mol
Composition:       {dict(species.composition)}

=== Thermodynamic Properties at {temperature:.2f} K ===
Cp (molar):        {gas.cp_mole:.4f} J/(mol·K)
Cv (molar):        {gas.cv_mole:.4f} J/(mol·K)
Enthalpy (molar):  {gas.enthalpy_mole/1000:.4f} kJ/mol
Entropy (molar):   {gas.entropy_mole:.4f} J/(mol·K)
Gibbs (molar):     {gas.gibbs_mole/1000:.4f} kJ/mol

=== Standard State Properties ===
Reference pressure: {thermo.reference_pressure:.2f} Pa
Temperature range:  {thermo.min_temp:.2f} - {thermo.max_temp:.2f} K
"""
    
    # Get standard formation enthalpy at 298.15 K if in range
    if thermo.min_temp <= 298.15 <= thermo.max_temp:
        gas.TP = 298.15, ct.one_atm
        result += f"H°f at 298.15 K:    {gas.enthalpy_mole/1000:.4f} kJ/mol\n"
        result += f"S° at 298.15 K:     {gas.entropy_mole:.4f} J/(mol·K)\n"
    
    return [{"type": "text", "text": result}]


async def list_available_mechanisms() -> list[dict[str, Any]]:
    """List commonly available Cantera mechanism files.
    
    Returns:
        List containing text result with available mechanisms
    """
    # Common mechanisms bundled with Cantera
    builtin_mechanisms = [
        ("gri30.yaml", "GRI-Mech 3.0: Natural gas combustion (53 species, 325 reactions)"),
        ("h2o2.yaml", "Hydrogen-oxygen combustion (9 species, 28 reactions)"),
        ("air.yaml", "Simple air model (N2, O2, Ar)"),
        ("nasa_gas.yaml", "NASA thermodynamic database for gases"),
        ("liquidvapor.yaml", "Pure substance liquid-vapor equilibrium"),
    ]
    
    result = """Available Cantera Mechanisms:

=== Built-in Mechanisms ===
"""
    
    for mech, description in builtin_mechanisms:
        # Check if mechanism is available
        try:
            gas = ct.Solution(mech)
            n_species = len(gas.species_names)
            n_reactions = gas.n_reactions
            result += f"\n• {mech}\n"
            result += f"  Description: {description}\n"
            result += f"  Species: {n_species}, Reactions: {n_reactions}\n"
        except Exception:
            result += f"\n• {mech} (not available in this installation)\n"
            result += f"  Description: {description}\n"
    
    # Discover custom mechanisms
    custom_mechs = discover_custom_mechanisms()
    if custom_mechs:
        result += "\n=== Custom Mechanisms ===\n"
        result += f"(Located in: {get_custom_mechanisms_dir()})\n"
        
        for mech_name, description, mech_path in custom_mechs:
            try:
                gas = ct.Solution(str(mech_path))
                n_species = len(gas.species_names)
                n_reactions = gas.n_reactions
                result += f"\n• {mech_name}\n"
                result += f"  Description: {description}\n"
                result += f"  Species: {n_species}, Reactions: {n_reactions}\n"
            except Exception as e:
                result += f"\n• {mech_name} (error loading: {e})\n"
    else:
        result += "\n=== Custom Mechanisms ===\n"
        result += f"No custom mechanisms found in: {get_custom_mechanisms_dir()}\n"
    
    result += """
=== Usage ===
Use a mechanism by passing its name to any tool, e.g.:
  mechanism: "gri30.yaml"      (built-in)
  mechanism: "JetSurf2.yaml"   (custom, auto-resolved)
"""
    
    return [{"type": "text", "text": result}]


async def list_species_in_mechanism(mechanism: str) -> list[dict[str, Any]]:
    """List all species in a Cantera mechanism.
    
    Args:
        mechanism: Cantera mechanism file or name
        
    Returns:
        List containing text result with species names
    """
    # Resolve custom mechanism path
    mechanism = resolve_mechanism(mechanism)
    
    # Create gas object
    gas = ct.Solution(mechanism)
    
    result = f"""Species in {mechanism}:

Total species: {len(gas.species_names)}
Total reactions: {gas.n_reactions}

=== Species List ===
"""
    
    # Group by element composition if possible
    species_by_element = {}
    for sp in gas.species():
        # Get primary element (most abundant in formula)
        if sp.composition:
            primary = max(sp.composition.items(), key=lambda x: x[1])[0]
        else:
            primary = "Other"
        
        if primary not in species_by_element:
            species_by_element[primary] = []
        species_by_element[primary].append((sp.name, sp.molecular_weight, sp.composition))
    
    for element in sorted(species_by_element.keys()):
        result += f"\n--- {element}-containing species ---\n"
        for name, mw, comp in sorted(species_by_element[element], key=lambda x: x[0]):
            formula = "".join(f"{el}{int(n) if n != 1 else ''}" for el, n in comp.items())
            result += f"  {name:12s}  MW={mw:8.3f} g/mol  ({formula})\n"
    
    return [{"type": "text", "text": result}]


# =============================================================================
# Server Entry Point
# =============================================================================

async def run_server() -> None:
    """Run the MCP server using stdio transport."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


def main() -> None:
    """Main entry point for the MCP server."""
    import asyncio
    
    logger.info("Starting MCP Server for Cantera")
    asyncio.run(run_server())


if __name__ == "__main__":
    main()
