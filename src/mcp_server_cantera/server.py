"""Main MCP server module for Cantera integration.

This module provides an MCP server that wraps Cantera functionality to enable
LLMs to perform accurate equilibrium, thermodynamic, and transport calculations.

Uses FastMCP for a clean, decorator-based API with Pydantic models for validation.
"""

import logging
import os
from pathlib import Path
from typing import Literal

import cantera as ct
from fastmcp import FastMCP
from pydantic import BaseModel, Field, field_validator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create the FastMCP server instance
mcp = FastMCP("mcp-server-cantera")


# =============================================================================
# Pydantic Models for Input Validation
# =============================================================================

class GasStateInput(BaseModel):
    """Input model for specifying a gas state."""
    
    mechanism: str = Field(
        ...,
        description="Cantera mechanism file or name (e.g., 'gri30.yaml' for combustion, 'air.yaml' for simple air)",
        examples=["gri30.yaml", "air.yaml", "JetSurf2.yaml"],
    )
    temperature: float = Field(
        ...,
        gt=0,
        description="Temperature in Kelvin",
        examples=[298.15, 500.0, 1000.0],
    )
    pressure: float = Field(
        ...,
        gt=0,
        description="Pressure in Pascals",
        examples=[101325.0, 500000.0],
    )
    composition: str = Field(
        ...,
        description="Gas composition in Cantera format (e.g., 'CH4:1, O2:2, N2:7.52')",
        examples=["CH4:1, O2:2, N2:7.52", "N2:0.79, O2:0.21", "H2:1"],
    )
    
    @field_validator("composition")
    @classmethod
    def validate_composition(cls, v: str) -> str:
        """Validate composition string format."""
        if not v or not v.strip():
            raise ValueError("Composition cannot be empty")
        # Basic validation - should contain at least one colon
        if ":" not in v:
            raise ValueError("Composition must be in format 'Species:amount' (e.g., 'CH4:1, O2:2')")
        return v.strip()


class EquilibriumInput(GasStateInput):
    """Input model for equilibrium calculations."""
    
    basis: Literal["TP", "HP", "SP", "UV"] = Field(
        default="TP",
        description="Equilibration basis: 'TP' (constant T,P), 'HP' (adiabatic, constant P), 'SP' (isentropic), 'UV' (constant U,V)",
    )


class CombustionInput(BaseModel):
    """Input model for combustion calculations."""
    
    mechanism: str = Field(
        ...,
        description="Cantera mechanism file (e.g., 'gri30.yaml' for methane combustion)",
        examples=["gri30.yaml", "JetSurf2.yaml"],
    )
    fuel: str = Field(
        ...,
        description="Fuel composition (e.g., 'CH4:1' or 'H2:1' or 'CH4:0.9, C2H6:0.1')",
        examples=["CH4:1", "H2:1", "NC12H26:1"],
    )
    oxidizer: str = Field(
        ...,
        description="Oxidizer composition (e.g., 'O2:1, N2:3.76' for air)",
        examples=["O2:1, N2:3.76", "O2:1"],
    )
    equivalence_ratio: float = Field(
        ...,
        gt=0,
        le=10,
        description="Equivalence ratio (phi). phi=1 is stoichiometric, phi<1 is lean, phi>1 is rich",
        examples=[1.0, 0.8, 1.2],
    )
    initial_temperature: float = Field(
        ...,
        gt=0,
        description="Initial temperature in Kelvin (typically 298.15 K)",
        examples=[298.15, 300.0, 400.0],
    )
    pressure: float = Field(
        ...,
        gt=0,
        description="Pressure in Pascals",
        examples=[101325.0, 500000.0],
    )
    
    @field_validator("fuel", "oxidizer")
    @classmethod
    def validate_composition(cls, v: str) -> str:
        """Validate composition string format."""
        if not v or not v.strip():
            raise ValueError("Composition cannot be empty")
        if ":" not in v:
            raise ValueError("Composition must be in format 'Species:amount'")
        return v.strip()


class SpeciesInput(BaseModel):
    """Input model for species property lookup."""
    
    mechanism: str = Field(
        ...,
        description="Cantera mechanism file or mechanism name",
        examples=["gri30.yaml", "air.yaml"],
    )
    species_name: str = Field(
        ...,
        description="Name of the species (e.g., 'CH4', 'O2', 'H2O')",
        examples=["CH4", "O2", "H2O", "CO2"],
    )
    temperature: float = Field(
        ...,
        gt=0,
        description="Temperature in Kelvin for property evaluation",
        examples=[298.15, 500.0, 1000.0],
    )


class MechanismInput(BaseModel):
    """Input model for mechanism queries."""
    
    mechanism: str = Field(
        ...,
        description="Cantera mechanism file or mechanism name",
        examples=["gri30.yaml", "air.yaml", "JetSurf2.yaml"],
    )


# =============================================================================
# Custom Mechanism Discovery
# =============================================================================

def get_custom_mechanisms_dir() -> Path:
    """Get path to custom mechanisms directory.
    
    Returns the mechanisms/ folder at the package root level.
    Path: server.py -> mcp_server_cantera -> src -> mcp-server-cantera -> mechanisms
    """
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
    if os.path.isabs(mechanism) or os.path.exists(mechanism):
        return mechanism
    
    custom_dir = get_custom_mechanisms_dir()
    custom_path = custom_dir / mechanism
    if custom_path.exists():
        logger.info(f"Resolved mechanism '{mechanism}' to custom path: {custom_path}")
        return str(custom_path)
    
    return mechanism


# =============================================================================
# Tool Implementations
# =============================================================================

@mcp.tool()
def get_gas_properties(params: GasStateInput) -> str:
    """Get comprehensive thermodynamic and transport properties of a gas mixture.
    
    Returns temperature, pressure, density, enthalpy, entropy, heat capacities,
    viscosity, thermal conductivity, speed of sound, and mole fractions.
    """
    mechanism = resolve_mechanism(params.mechanism)
    gas = ct.Solution(mechanism)
    gas.TPX = params.temperature, params.pressure, params.composition
    
    gamma = gas.cp / gas.cv
    speed_of_sound = (gamma * ct.gas_constant * params.temperature / gas.mean_molecular_weight) ** 0.5
    
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
    
    return result


@mcp.tool()
def get_transport_properties(params: GasStateInput) -> str:
    """Get detailed transport properties of a gas mixture.
    
    Includes viscosity, thermal conductivity, and species diffusion coefficients.
    """
    mechanism = resolve_mechanism(params.mechanism)
    gas = ct.Solution(mechanism)
    gas.TPX = params.temperature, params.pressure, params.composition
    
    mix_diff_coeffs = gas.mix_diff_coeffs
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
    
    return result


@mcp.tool()
def equilibrate_gas(params: EquilibriumInput) -> str:
    """Calculate equilibrium composition of a gas mixture.
    
    Returns equilibrium state, heat release, and Gibbs free energy change.
    """
    mechanism = resolve_mechanism(params.mechanism)
    gas = ct.Solution(mechanism)
    gas.TPX = params.temperature, params.pressure, params.composition
    
    initial_T = gas.T
    initial_P = gas.P
    initial_H = gas.enthalpy_mass
    initial_G = gas.gibbs_mass
    
    gas.equilibrate(params.basis)
    
    delta_H = gas.enthalpy_mass - initial_H
    delta_G = gas.gibbs_mass - initial_G
    
    result = f"""Equilibrium Calculation (basis: {params.basis}):

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
    
    return result


@mcp.tool()
def calculate_adiabatic_flame_temperature(params: CombustionInput) -> str:
    """Calculate the adiabatic flame temperature for combustion of a fuel with an oxidizer."""
    mechanism = resolve_mechanism(params.mechanism)
    gas = ct.Solution(mechanism)
    
    gas.set_equivalence_ratio(params.equivalence_ratio, params.fuel, params.oxidizer)
    gas.TP = params.initial_temperature, params.pressure
    
    initial_H = gas.enthalpy_mass
    
    gas.equilibrate('HP')
    
    phi = params.equivalence_ratio
    result = f"""Adiabatic Flame Temperature Calculation:

=== Combustion Setup ===
Mechanism:          {mechanism}
Fuel:               {params.fuel}
Oxidizer:           {params.oxidizer}
Equivalence ratio:  {phi:.3f} {"(stoichiometric)" if abs(phi - 1.0) < 0.01 else "(lean)" if phi < 1 else "(rich)"}
Initial temperature: {params.initial_temperature:.2f} K
Pressure:           {params.pressure:.2f} Pa ({params.pressure/1e5:.4f} bar)

=== Results ===
Adiabatic flame temperature: {gas.T:.2f} K ({gas.T - 273.15:.2f} °C)
Temperature rise:            {gas.T - params.initial_temperature:.2f} K

=== Major Product Species (X > 0.1%) ===
"""
    
    for species, mole_frac in zip(gas.species_names, gas.X):
        if mole_frac > 0.001:
            result += f"  {species}: {mole_frac*100:.4f}%\n"
    
    result += """
=== Minor Product Species (0.01% < X < 0.1%) ===
"""
    for species, mole_frac in zip(gas.species_names, gas.X):
        if 0.0001 < mole_frac <= 0.001:
            result += f"  {species}: {mole_frac*100:.6f}%\n"
    
    return result


@mcp.tool()
def get_species_properties(params: SpeciesInput) -> str:
    """Get detailed thermodynamic properties for a specific species from a mechanism file."""
    mechanism = resolve_mechanism(params.mechanism)
    gas = ct.Solution(mechanism)
    
    if params.species_name not in gas.species_names:
        return f"Error: Species '{params.species_name}' not found in mechanism '{mechanism}'. Use list_species_in_mechanism to see available species."
    
    species = gas.species(params.species_name)
    gas.TPX = params.temperature, ct.one_atm, f"{params.species_name}:1"
    
    thermo = species.thermo
    
    result = f"""Species Properties for {params.species_name}:

=== Basic Information ===
Name:              {species.name}
Molecular weight:  {species.molecular_weight:.4f} g/mol
Composition:       {dict(species.composition)}

=== Thermodynamic Properties at {params.temperature:.2f} K ===
Cp (molar):        {gas.cp_mole:.4f} J/(mol·K)
Cv (molar):        {gas.cv_mole:.4f} J/(mol·K)
Enthalpy (molar):  {gas.enthalpy_mole/1000:.4f} kJ/mol
Entropy (molar):   {gas.entropy_mole:.4f} J/(mol·K)
Gibbs (molar):     {gas.gibbs_mole/1000:.4f} kJ/mol

=== Standard State Properties ===
Reference pressure: {thermo.reference_pressure:.2f} Pa
Temperature range:  {thermo.min_temp:.2f} - {thermo.max_temp:.2f} K
"""
    
    if thermo.min_temp <= 298.15 <= thermo.max_temp:
        gas.TP = 298.15, ct.one_atm
        result += f"H°f at 298.15 K:    {gas.enthalpy_mole/1000:.4f} kJ/mol\n"
        result += f"S° at 298.15 K:     {gas.entropy_mole:.4f} J/(mol·K)\n"
    
    return result


@mcp.tool()
def list_available_mechanisms() -> str:
    """List commonly available Cantera mechanism files with descriptions."""
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
    
    return result


@mcp.tool()
def list_species_in_mechanism(params: MechanismInput) -> str:
    """List all species defined in a Cantera mechanism file."""
    mechanism = resolve_mechanism(params.mechanism)
    gas = ct.Solution(mechanism)
    
    result = f"""Species in {mechanism}:

Total species: {len(gas.species_names)}
Total reactions: {gas.n_reactions}

=== Species List ===
"""
    
    species_by_element: dict[str, list[tuple[str, float, dict]]] = {}
    for sp in gas.species():
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
    
    return result


# =============================================================================
# Server Entry Point
# =============================================================================

def main() -> None:
    """Main entry point for the MCP server."""
    logger.info("Starting MCP Server for Cantera (FastMCP)")
    mcp.run()


if __name__ == "__main__":
    main()
