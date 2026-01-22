"""Main MCP server module for Cantera integration.

This module provides an MCP server that wraps Cantera functionality to enable
LLMs to perform accurate equilibrium and kinetic analyses while also providing
thermodynamic and transport properties.

Uses FastMCP for a clean, decorator-based API with Pydantic models for validation.
"""

import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Literal

import cantera as ct
import numpy as np
import yaml
from fastmcp import FastMCP
from .schema import (
    LabBenchMeasurementInput,
    LabBenchEquilibriumInput,
    CombustionInput,
    SpeciesInput,
    MechanismInput,
    MetalCombustionInput,
    LabBenchMixtureInput,
    ReactionRatesInput,
    SpeciesProductionInput,
    BatchReactorInput,
    IgnitionDelayInput,
    SpeciesThermoInput,
    SpeciesAvailabilityInput,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SYSTEM_INSTRUCTIONS = """
You are an expert Chemical Equilibrium and Kinetics Assistant using the Cantera library.

CRITICAL RULES:
1. **Persistence:** The 'lab bench' is persistent. Objects like 'mixture1' stay in memory between turns. Do not recreate them unless asked.
2. **Units:** All inputs must be in SI units unless specified:
   - Temperature: Kelvin (K)
   - Pressure: Pascals (Pa). Note: 1 atm = 101,325 Pa.
   - Composition: Mole fractions (e.g., 'CH4:1, O2:2').
3. **State Management:** When running reactor simulations (time-integration), the state of the gas object is UPDATED to the final time. 
   - If the user wants to run a second test from the *original* conditions, you must explicitly reset the state using 'set_state' first.
4. **Safety:** If a user asks for a detonation simulation or hazardous mixture, provide the scientific results but add a standard safety disclaimer.
5. **Ambient Conditions:** If the user asks for a reaction at ambient conditions, use 298 K and 1 atm (101,325 Pa).
6. **Temperature:** If the user asks for a reaction at a specific temperature, use that temperature. Otherwise, use 298 K.
7. **Generated Data:** If data or figures are generated, save it in the output directory.
8. **Generated Scripts:** If python scripts are generated to complete a user request, save them in the scripts directory.
"""

# Create the FastMCP server instance
mcp = FastMCP("mcp-server-cantera")

# =============================================================================
# Stateful Lab Bench - Named Solutions Storage
# =============================================================================
# Dictionary to store named Cantera Solution objects for kinetic analysis
_lab_bench: dict[str, ct.Solution] = {}

def get_solution(name: str) -> ct.Solution:
    """Retrieve a named solution from the lab bench.
    
    Args:
        name: The unique identifier for the solution
        
    Returns:
        The Cantera Solution object
        
    Raises:
        KeyError: If the solution name is not found
    """
    if name not in _lab_bench:
        available = list(_lab_bench.keys()) if _lab_bench else "(none)"
        raise KeyError(f"Solution '{name}' not found on lab bench. Available: {available}")
    return _lab_bench[name]


def store_solution(name: str, gas: ct.Solution) -> None:
    """Store a solution on the lab bench with a unique name."""
    _lab_bench[name] = gas
    logger.info(f"Stored solution '{name}' on lab bench (T={gas.T:.1f}K, P={gas.P:.0f}Pa)")


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
# Species Thermodynamic Lookup with Database Fallback
# =============================================================================

def _get_thermo_state(species_name: str, temp_k: float, pressure_pa: float) -> tuple[ct.Solution | None, str]:
    """
    Create a Cantera Solution object for a single species with database fallback.
    
    Fallback order:
    1. GRI-Mech 3.0 (fast, pre-compiled, common combustion species)
    2. NASA Gas Database (covers ~1000+ species including noble gases, metals, etc.)
    
    Args:
        species_name: Chemical formula or species name (e.g., 'CH4', 'He', 'Xe')
        temp_k: Temperature in Kelvin
        pressure_pa: Pressure in Pascals
        
    Returns:
        Tuple of (Solution object or None, source description or error message)
    """
    # 1. Try GRI-Mech 3.0 first (fast lookup for common combustion species)
    try:
        gas = ct.Solution('gri30.yaml')
        gas.species_index(species_name)  # Raises ValueError if not found
        gas.TPX = temp_k, pressure_pa, {species_name: 1.0}
        return gas, "GRI-Mech 3.0"
    except (ValueError, RuntimeError, ct.CanteraError):
        pass  # Species not in GRI 3.0, proceed to fallback
    
    # 2. Fallback to NASA Gas Database
    nasa_gas_path = get_custom_mechanisms_dir() / "nasa_gas.yaml"
    
    if not nasa_gas_path.exists():
        return None, f"NASA gas database not found at {nasa_gas_path}"
    
    try:
        # Load all species definitions from NASA database
        found_species = ct.Species.list_from_file(str(nasa_gas_path))
        
        # Case-insensitive search for the target species
        target_species = next(
            (s for s in found_species if s.name.upper() == species_name.upper()), 
            None
        )
        
        if target_species:
            # Dynamically construct a phase with just this one species
            gas = ct.Solution(thermo='ideal-gas', species=[target_species])
            gas.TPX = temp_k, pressure_pa, {target_species.name: 1.0}
            return gas, "NASA Gas Database (nasa_gas.yaml)"
            
    except Exception as e:
        return None, f"Error loading from NASA database: {e}"
    
    return None, f"Species '{species_name}' not found in GRI 3.0 or NASA Gas databases."


# =============================================================================
# Metal Combustion Mechanism Builder
# =============================================================================

def load_nasa_species_data(yaml_path: Path) -> list[dict]:
    """Load species data from a NASA thermodynamic database YAML file.
    
    Args:
        yaml_path: Path to the YAML file (nasa_gas.yaml or nasa_condensed.yaml)
        
    Returns:
        List of species dictionaries from the file
    """
    with open(yaml_path, 'r') as f:
        data = yaml.safe_load(f)
    return data.get('species', [])


def find_metal_species(species_list: list[dict], metal_symbol: str) -> list[dict]:
    """Find species containing a specific metal element.
    
    Args:
        species_list: List of species dictionaries from NASA database
        metal_symbol: Metal element symbol (e.g., 'Fe', 'Al')
        
    Returns:
        Filtered list of species containing the metal
    """
    metal_species = []
    for sp in species_list:
        composition = sp.get('composition', {})
        if metal_symbol in composition:
            metal_species.append(sp)
    return metal_species


def find_species_by_names(species_list: list[dict], names: list[str]) -> list[dict]:
    """Find species by exact name match.
    
    Args:
        species_list: List of species dictionaries
        names: List of species names to find
        
    Returns:
        List of matching species dictionaries
    """
    found = []
    for sp in species_list:
        if sp.get('name') in names:
            found.append(sp)
    return found


def build_metal_combustion_mechanism(metal: str) -> tuple[str, list[str], list[str]]:
    """Build a temporary mechanism file for metal-air combustion.
    
    Extracts metal and metal oxide species from NASA databases and creates
    a complete mechanism with gas and condensed phases for multi-phase equilibrium.

    Please note that in the NASA condensed database, the phase is noted in a suffix to the species name, e.g. Fe(a), Fe(c), Fe(L)
    (L) denotes a liquid, and (s), (cr), (a), (b),(c) or (d) denote a solid.
    
    Args:
        metal: Metal element symbol (e.g., 'Fe', 'Al', 'Mg')
        
    Returns:
        Tuple of (temp_file_path, gas_species_names, condensed_species_names)
    """
    mech_dir = get_custom_mechanisms_dir()
    gas_yaml = mech_dir / "nasa_gas.yaml"
    condensed_yaml = mech_dir / "nasa_condensed.yaml"
    
    if not gas_yaml.exists():
        raise FileNotFoundError(f"NASA gas database not found: {gas_yaml}")
    if not condensed_yaml.exists():
        raise FileNotFoundError(f"NASA condensed database not found: {condensed_yaml}")
    
    # Load species from NASA databases
    gas_species_all = load_nasa_species_data(gas_yaml)
    condensed_species_all = load_nasa_species_data(condensed_yaml)
    
    # Find metal-containing species
    metal_gas_species = find_metal_species(gas_species_all, metal)
    metal_condensed_species = find_metal_species(condensed_species_all, metal)
    
    # Find air/oxidizer species (O2, N2, Ar, O, N, NO, NO2, etc.)
    air_species_names = ['O2', 'N2', 'Ar', 'O', 'N', 'NO', 'NO2', 'O3']
    air_species = find_species_by_names(gas_species_all, air_species_names)
    
    # Combine gas phase species (avoid duplicates)
    gas_species = []
    seen_names = set()
    for sp in metal_gas_species + air_species:
        if sp['name'] not in seen_names:
            gas_species.append(sp)
            seen_names.add(sp['name'])
    
    if not gas_species:
        raise ValueError(f"No gas phase species found for metal '{metal}'")
    
    gas_species_names = [sp['name'] for sp in gas_species]
    condensed_species_names = [sp['name'] for sp in metal_condensed_species]
    
    # Collect all elements needed across gas and condensed phases
    all_elements = set()
    for sp in gas_species:
        all_elements.update(sp.get('composition', {}).keys())
    for sp in metal_condensed_species:
        all_elements.update(sp.get('composition', {}).keys())
    all_elements = sorted(list(all_elements))
    
    # Build the mechanism YAML structure with multi-phase support
    mechanism = {
        'description': f'Dynamic metal combustion mechanism for {metal}/air equilibrium. '
                      f'Generated from NASA thermodynamic databases. '
                      f'Includes both gas and condensed phases for multi-phase equilibrium.',
        'units': {'length': 'cm', 'time': 's', 'quantity': 'mol', 'activation-energy': 'cal/mol'},
        'phases': [
            {
                'name': 'gas',
                'thermo': 'ideal-gas',
                'elements': all_elements,
                'species': gas_species_names,
                'kinetics': 'none',
                'state': {'T': 300.0, 'P': '1 atm'}
            }
        ],
        'species': list(gas_species)  # Copy to avoid mutation
    }
    
    # Add condensed phases - each condensed species becomes its own stoichiometric phase
    # This is required for multi-phase equilibrium with Cantera's Mixture class
    if metal_condensed_species:
        for sp in metal_condensed_species:
            sp_name = sp['name']
            # Create a valid phase name from species name
            phase_name = re.sub(r'[^a-zA-Z0-9_]', '_', sp_name)
            
            mechanism['phases'].append({
                'name': phase_name,
                'thermo': 'fixed-stoichiometry',
                'elements': all_elements,  # Include all elements for phase compatibility
                'species': [sp_name],
                'state': {'T': 300.0, 'P': '1 atm'}
            })
            mechanism['species'].append(sp)
    
    # Write to temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(mechanism, f, default_flow_style=False, sort_keys=False)
        temp_path = f.name
    
    logger.info(f"Built metal combustion mechanism: {len(gas_species_names)} gas species, "
                f"{len(condensed_species_names)} condensed species in {len(mechanism['phases'])} phases")
    
    return temp_path, gas_species_names, condensed_species_names


def create_multiphase_mixture(mech_path: str, gas_species_names: list[str], 
                               condensed_species_names: list[str]) -> tuple:
    """Create a Cantera Mixture object for multi-phase equilibrium.
    
    Args:
        mech_path: Path to the mechanism YAML file
        gas_species_names: List of gas phase species names
        condensed_species_names: List of condensed phase species names
        
    Returns:
        Tuple of (gas_phase, condensed_phases_list, mixture)
    """
    # Load the gas phase
    gas = ct.Solution(mech_path, 'gas')
    
    # Load all condensed phases
    condensed_phases = []
    for sp_name in condensed_species_names:
        phase_name = re.sub(r'[^a-zA-Z0-9_]', '_', sp_name)
        try:
            phase = ct.Solution(mech_path, phase_name)
            condensed_phases.append(phase)
        except Exception as e:
            logger.warning(f"Could not load condensed phase '{phase_name}': {e}")
    
    # Create the mixture for multi-phase equilibrium
    # The mixture contains the gas phase plus all condensed phases
    all_phases = [gas] + condensed_phases
    
    # Create quantities for mixture (moles of each phase)
    # Start with 1 mole of gas phase, 0 moles of condensed phases
    quantities = [1.0] + [0.0] * len(condensed_phases)
    
    mixture = ct.Mixture([(phase, qty) for phase, qty in zip(all_phases, quantities)])
    
    return gas, condensed_phases, mixture


# =============================================================================
# Tool Implementations
# =============================================================================

@mcp.tool()
def get_mixture_properties(params: LabBenchMeasurementInput) -> str:
    """Get comprehensive thermodynamic and transport properties of a lab bench mixture.
    
    Returns temperature, pressure, density, enthalpy, entropy, heat capacities,
    viscosity, thermal conductivity, speed of sound, and mole fractions.
    """
    try:
        mix = get_solution(params.name)
        
        gamma = mix.cp / mix.cv
        speed_of_sound = (gamma * ct.gas_constant * mix.T / mix.mean_molecular_weight) ** 0.5
        
        # Calculate transport properties
        # Note: Some specialized phases (like metal combustion) might not support all transport props
        # We handle this gracefully
        try:
            viscosity = f"{mix.viscosity:.6e} Pa·s"
            thermal_cond = f"{mix.thermal_conductivity:.6f} W/(m·K)"
            prandtl = f"{mix.cp * mix.viscosity / mix.thermal_conductivity:.4f}"
        except NotImplementedError:
            viscosity = "N/A"
            thermal_cond = "N/A"
            prandtl = "N/A"

        result = f"""Mixture Properties for '{params.name}':

=== Thermodynamic State ===
Temperature:           {mix.T:.2f} K
Pressure:              {mix.P:.2f} Pa ({mix.P/1e5:.4f} bar)
Density:               {mix.density:.6f} kg/m³
Mean molecular weight: {mix.mean_molecular_weight:.4f} g/mol

=== Thermodynamic Properties ===
Specific enthalpy (mass):  {mix.enthalpy_mass/1000:.4f} kJ/kg
Specific entropy (mass):   {mix.entropy_mass/1000:.6f} kJ/(kg·K)
Specific Cp (mass):        {mix.cp_mass:.4f} J/(kg·K)
Specific Cv (mass):        {mix.cv_mass:.4f} J/(kg·K)
Heat capacity ratio γ:     {gamma:.6f}
Internal energy (mass):    {mix.int_energy_mass/1000:.4f} kJ/kg
Gibbs free energy (mass):  {mix.gibbs_mass/1000:.4f} kJ/kg

=== Transport Properties ===
Dynamic viscosity:         {viscosity}
Thermal conductivity:      {thermal_cond}
Prandtl number:            {prandtl}
Speed of sound (ideal):    {speed_of_sound:.2f} m/s

=== Mole Fractions ===
"""
        
        for species, mole_frac in zip(mix.species_names, mix.X):
            if mole_frac > 1e-10:
                result += f"  {species}: {mole_frac:.6e}\n"
        
        return result
    except KeyError as e:
        return str(e)
    except Exception as e:
        return f"Error calculating properties: {e}"


@mcp.tool()
def equilibrate(params: LabBenchEquilibriumInput) -> str:
    """Equilibrate a lab bench mixture to a state of chemical equilibrium.
    
    This simulation updates the state of the mixture on the lab bench.
    Returns the final state, heat release, and Gibbs free energy change.
    """
    try:
        mix = get_solution(params.name)
        
        initial_T = mix.T
        initial_P = mix.P
        initial_H = mix.enthalpy_mass
        initial_G = mix.gibbs_mass
        
        mix.equilibrate(params.basis)
        
        delta_H = mix.enthalpy_mass - initial_H
        delta_G = mix.gibbs_mass - initial_G
        
        result = f"""Equilibrium Calculation (basis: {params.basis}) for '{params.name}':

=== Initial State ===
Temperature: {initial_T:.2f} K
Pressure:    {initial_P:.2f} Pa

=== Equilibrium State ===
Temperature: {mix.T:.2f} K
Pressure:    {mix.P:.2f} Pa
Density:     {mix.density:.6f} kg/m³

=== Thermodynamic Changes ===
ΔH (enthalpy change): {delta_H/1000:.4f} kJ/kg {"(exothermic)" if delta_H < 0 else "(endothermic)"}
ΔG (Gibbs change):    {delta_G/1000:.4f} kJ/kg

=== Equilibrium Mole Fractions ===
"""
        
        for species, mole_frac in zip(mix.species_names, mix.X):
            if mole_frac > 1e-10:
                result += f"  {species}: {mole_frac:.6e}\n"
        
        return result
    except KeyError as e:
        return str(e)
    except Exception as e:
        return f"Equilibration failed: {e}"


@mcp.tool()
def calculate_adiabatic_flame_temperature(params: CombustionInput) -> str:
    """Calculate the adiabatic flame temperature for combustion of a fuel with an oxidizer."""
    mechanism = resolve_mechanism(params.mechanism)
    mix = ct.Solution(mechanism)
    
    mix.set_equivalence_ratio(params.equivalence_ratio, params.fuel, params.oxidizer)
    mix.TP = params.initial_temperature, params.pressure
    
    initial_H = mix.enthalpy_mass
    
    mix.equilibrate('HP')
    
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
Adiabatic flame temperature: {mix.T:.2f} K ({mix.T - 273.15:.2f} °C)
Temperature rise:            {mix.T - params.initial_temperature:.2f} K

=== Major Product Species (X > 0.1%) ===
"""
    
    for species, mole_frac in zip(mix.species_names, mix.X):
        if mole_frac > 0.001:
            result += f"  {species}: {mole_frac*100:.4f}%\n"
    
    result += """
=== Minor Product Species (0.01% < X < 0.1%) ===
"""
    for species, mole_frac in zip(mix.species_names, mix.X):
        if 0.0001 < mole_frac <= 0.001:
            result += f"  {species}: {mole_frac*100:.6f}%\n"
    
    return result


@mcp.tool()
def get_species_properties(params: SpeciesInput) -> str:
    """Get detailed thermodynamic properties for a specific species from a mechanism file."""
    mechanism = resolve_mechanism(params.mechanism)
    mix = ct.Solution(mechanism)
    
    if params.species_name not in mix.species_names:
        return f"Error: Species '{params.species_name}' not found in mechanism '{mechanism}'. Use list_species_in_mechanism to see available species."
    
    species = mix.species(params.species_name)
    mix.TPX = params.temperature, ct.one_atm, f"{params.species_name}:1"
    
    thermo = species.thermo
    
    result = f"""Species Properties for {params.species_name}:

=== Basic Information ===
Name:              {species.name}
Molecular weight:  {species.molecular_weight:.4f} g/mol
Composition:       {dict(species.composition)}

=== Thermodynamic Properties at {params.temperature:.2f} K ===
Cp (molar):        {mix.cp_mole:.4f} J/(mol·K)
Cv (molar):        {mix.cv_mole:.4f} J/(mol·K)
Enthalpy (molar):  {mix.enthalpy_mole/1000:.4f} kJ/mol
Entropy (molar):   {mix.entropy_mole:.4f} J/(mol·K)
Gibbs (molar):     {mix.gibbs_mole/1000:.4f} kJ/mol

=== Standard State Properties ===
Reference pressure: {thermo.reference_pressure:.2f} Pa
Temperature range:  {thermo.min_temp:.2f} - {thermo.max_temp:.2f} K
"""
    
    if thermo.min_temp <= 298.15 <= thermo.max_temp:
        mix.TP = 298.15, ct.one_atm
        result += f"H°f at 298.15 K:    {mix.enthalpy_mole/1000:.4f} kJ/mol\n"
        result += f"S° at 298.15 K:     {mix.entropy_mole:.4f} J/(mol·K)\n"
    
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
            mix = ct.Solution(mech)
            n_species = len(mix.species_names)
            n_reactions = mix.n_reactions
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
                mix = ct.Solution(str(mech_path))
                n_species = len(mix.species_names)
                n_reactions = mix.n_reactions
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
    mix = ct.Solution(mechanism)
    
    result = f"""Species in {mechanism}:

Total species: {len(mix.species_names)}
Total reactions: {mix.n_reactions}

=== Species List ===
"""
    
    species_by_element: dict[str, list[tuple[str, float, dict]]] = {}
    for sp in mix.species():
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


@mcp.tool()
def get_species_thermo(params: SpeciesThermoInput) -> str:
    """Calculate thermodynamic properties for a specific species with automatic database fallback.
    
    Searches GRI-Mech 3.0 first (fast, common combustion species), then falls back to
    the NASA Gas Database for broader coverage (~1000+ species including noble gases, metals, etc.).
    """
    # Convert bar to Pascals
    pressure_pa = params.pressure_bar * 100000.0
    
    # Get the phase object using fallback logic
    gas, source = _get_thermo_state(params.species, params.temperature_k, pressure_pa)
    
    if gas is None:
        return f"Error: Could not find thermodynamic data for species '{params.species}'. {source}"
    
    # Extract properties (molar and mass-based)
    h_mole = gas.enthalpy_mole / 1000.0   # J/kmol -> kJ/kmol
    s_mole = gas.entropy_mole / 1000.0    # J/kmol/K -> kJ/kmol/K
    cp_mole = gas.cp_mole / 1000.0        # J/kmol/K -> kJ/kmol/K
    
    mw = gas.mean_molecular_weight        # g/mol
    h_mass = gas.enthalpy_mass / 1000.0   # kJ/kg
    cp_mass = gas.cp_mass / 1000.0        # kJ/kg/K
    
    return f"""
=== Thermodynamic Properties for {params.species} ===
Source: {source}
State: {params.temperature_k:.2f} K, {params.pressure_bar:.4f} bar

Molar Mass: {mw:.4f} g/mol

Molar Properties:
  • Enthalpy (h):       {h_mole:.2f} kJ/kmol
  • Entropy (s):        {s_mole:.2f} kJ/kmol·K
  • Specific Heat (Cp): {cp_mole:.2f} kJ/kmol·K

Mass Properties:
  • Enthalpy (h):       {h_mass:.2f} kJ/kg
  • Specific Heat (Cp): {cp_mass:.4f} kJ/kg·K
"""


@mcp.tool()
def check_species_availability(params: SpeciesAvailabilityInput) -> str:
    """Check which database contains specific species.
    
    Useful for planning simulations and verifying species availability before calculations.
    Searches GRI-Mech 3.0 and NASA Gas Database.
    """
    results = []
    
    # Load species name sets once for efficiency
    try:
        gri_names = {s.name.upper() for s in ct.Species.list_from_file('gri30.yaml')}
    except Exception:
        gri_names = set()
    
    nasa_gas_path = get_custom_mechanisms_dir() / "nasa_gas.yaml"
    try:
        nasa_names = {s.name.upper() for s in ct.Species.list_from_file(str(nasa_gas_path))}
    except Exception:
        nasa_names = set()
    
    for sp in params.species_list:
        sp_upper = sp.upper()
        if sp_upper in gri_names:
            results.append(f"  {sp}: ✓ Available (GRI-Mech 3.0)")
        elif sp_upper in nasa_names:
            results.append(f"  {sp}: ✓ Available (NASA Gas Database)")
        else:
            results.append(f"  {sp}: ✗ NOT FOUND")
    
    header = f"""Species Availability Check:

Searched databases:
  • GRI-Mech 3.0: {len(gri_names)} species
  • NASA Gas Database: {len(nasa_names)} species

Results:
"""
    return header + "\n".join(results)


@mcp.tool()
def calculate_metal_combustion_equilibrium(params: MetalCombustionInput) -> str:
    """Calculate equilibrium temperature and products for metal-oxygen/air combustion.
    
    Builds a dynamic mechanism by extracting species from NASA thermodynamic databases
    (nasa_gas.yaml and nasa_condensed.yaml) and calculates the equilibrium state including
    both gas and condensed (solid/liquid) phases.
    
    Supported metals include: Fe, Al, Mg, Ti, Zn, Cu, Cr, Mn, Ni, Co, and more.
    """
    import os as os_module  # Local import to avoid shadowing
    
    def calc_mixture_enthalpy(mix: ct.Mixture) -> float:
        """Calculate total enthalpy of mixture from all phases."""
        H_total = 0.0
        for i in range(mix.n_phases):
            phase = mix.phase(i)
            phase_moles = mix.phase_moles(i)
            if phase_moles > 0:
                H_total += phase.enthalpy_mole * phase_moles
        return H_total
    
    try:
        # Build the dynamic mechanism
        mech_path, gas_species, condensed_species = build_metal_combustion_mechanism(params.metal)
        
        try:
            # Load gas phase
            gas = ct.Solution(mech_path, 'gas')
            
            # Load all condensed phases
            condensed_phases = []
            for sp_name in condensed_species:
                phase_name = re.sub(r'[^a-zA-Z0-9_]', '_', sp_name)
                try:
                    phase = ct.Solution(mech_path, phase_name)
                    condensed_phases.append(phase)
                except Exception:
                    pass  # Silently skip phases that can't be loaded
            
            # Set up the initial mixture based on oxidizer choice
            metal_symbol = params.metal
            
            # Find the base metal species (gas phase, no charge)
            metal_gas_name = metal_symbol
            if metal_gas_name not in gas.species_names:
                # Try to find any gas-phase metal species
                for sp in gas_species:
                    if sp == metal_symbol or (sp.startswith(metal_symbol) and not any(c in sp for c in '+-()[]')):
                        metal_gas_name = sp
                        break
            
            if metal_gas_name not in gas.species_names:
                return f"Error: Could not find base metal species '{metal_symbol}' in gas phase. Available species: {gas_species[:10]}..."
            
            # Determine stoichiometry for metal oxidation
            if params.oxidizer == "air":
                o2_moles = 1.0
                n2_moles = 3.76
                metal_moles = params.equivalence_ratio * o2_moles
                
                if 'N2' in gas.species_names:
                    composition = f"{metal_gas_name}:{metal_moles}, O2:{o2_moles}, N2:{n2_moles}"
                else:
                    composition = f"{metal_gas_name}:{metal_moles}, O2:{o2_moles}"
            else:  # Pure O2
                o2_moles = 1.0
                metal_moles = params.equivalence_ratio * o2_moles
                composition = f"{metal_gas_name}:{metal_moles}, O2:{o2_moles}"
            
            # Set initial state on gas phase
            gas.TPX = params.initial_temperature, params.pressure, composition
            initial_T = gas.T
            
            # Set condensed phases to initial conditions
            for cp in condensed_phases:
                cp.TP = params.initial_temperature, params.pressure
            
            # Create initial mixture: 1 mole of gas, 0 moles of condensed phases
            phase_list = [(gas, 1.0)] + [(cp, 0.0) for cp in condensed_phases]
            mixture = ct.Mixture(phase_list)
            
            # Record initial enthalpy (target for adiabatic equilibrium)
            target_H = calc_mixture_enthalpy(mixture)
            
            # Adiabatic equilibrium via bisection on temperature
            T_low = params.initial_temperature
            T_high = 5000.0  # Upper bound for flame temperature
            tolerance = 2.0  # K - slightly relaxed for better convergence
            
            final_mixture = None
            best_mixture = None
            best_H_diff = float('inf')
            
            for iteration in range(60):  # More iterations for difficult cases
                T_guess = (T_low + T_high) / 2
                
                # Reset gas phase to initial composition at new temperature
                gas.TPX = T_guess, params.pressure, composition
                for cp in condensed_phases:
                    cp.TP = T_guess, params.pressure
                
                # Recreate mixture at this temperature
                phase_list = [(gas, 1.0)] + [(cp, 0.0) for cp in condensed_phases]
                mixture = ct.Mixture(phase_list)
                
                # Equilibrate at constant T, P with error handling
                try:
                    mixture.equilibrate('TP', max_steps=1000, log_level=0)
                    equilibrated = True
                except Exception as eq_err:
                    logger.warning(f"Equilibration failed at T={T_guess:.1f} K: {eq_err}")
                    equilibrated = False
                
                if equilibrated:
                    current_H = calc_mixture_enthalpy(mixture)
                    H_diff = abs(current_H - target_H)
                    
                    # Track best result
                    if H_diff < best_H_diff:
                        best_H_diff = H_diff
                        best_mixture = mixture
                else:
                    # If equilibration failed, just continue bisection
                    current_H = target_H  # Neutral value to continue
                
                if abs(T_high - T_low) < tolerance:
                    final_mixture = mixture
                    break
                
                # If current enthalpy < target, temperature is too low → raise T_low
                # If current enthalpy > target, temperature is too high → lower T_high
                if current_H < target_H:
                    T_low = T_guess
                else:
                    T_high = T_guess
            
            if final_mixture is None:
                # Use best mixture found during iterations
                final_mixture = best_mixture if best_mixture is not None else mixture
            
            final_T = final_mixture.T
            delta_T = final_T - initial_T
            
            # Build result
            result = f"""Metal Combustion Equilibrium Calculation (Multi-Phase):

=== Setup ===
Metal:               {params.metal}
Oxidizer:            {params.oxidizer}
Equivalence ratio:   {params.equivalence_ratio:.3f}
Initial temperature: {initial_T:.2f} K
Pressure:            {params.pressure:.2f} Pa ({params.pressure/1e5:.4f} bar)

=== Phases in Calculation ===
Gas phase:           {len(gas_species)} species
Condensed phases:    {len(condensed_phases)} phases

=== Results (Adiabatic Multi-Phase Equilibrium) ===
Adiabatic flame temperature: {final_T:.2f} K ({final_T - 273.15:.2f} °C)
Temperature rise:            {delta_T:.2f} K

=== Equilibrium Gas Phase Composition ===
"""
            
            # Report gas phase composition from mixture
            gas_phase = final_mixture.phase(0)  # Gas is always first phase
            for i, sp_name in enumerate(gas_phase.species_names):
                mole_frac = gas_phase.X[i]
                if mole_frac > 1e-6:
                    result += f"  {sp_name}: {mole_frac*100:.4f}%\n"
            
            # Report condensed phases with non-negligible amounts
            result += "\n=== Equilibrium Condensed Phase Composition ===\n"
            condensed_results = []
            total_condensed_moles = 0.0
            
            for i in range(1, final_mixture.n_phases):  # Skip gas phase (index 0)
                phase_moles = final_mixture.phase_moles(i)
                if phase_moles > 1e-10:
                    phase = final_mixture.phase(i)
                    sp_name = phase.species_names[0] if len(phase.species_names) == 1 else phase.name
                    condensed_results.append((sp_name, phase_moles))
                    total_condensed_moles += phase_moles
            
            if condensed_results:
                for sp_name, moles in sorted(condensed_results, key=lambda x: -x[1]):
                    fraction = moles / total_condensed_moles * 100 if total_condensed_moles > 0 else 0
                    result += f"  {sp_name}: {moles:.6f} mol ({fraction:.2f}% of condensed)\n"
            else:
                result += "  No significant condensed phase products\n"
            
            result += f"""
=== Notes ===
- This calculation includes multi-phase equilibrium (gas + condensed phases)
- {len(condensed_phases)} condensed phases were included in the equilibrium calculation
- Metal oxide formation enthalpies are from NASA thermodynamic polynomials
- Adiabatic temperature found via bisection iteration to constant enthalpy
"""
            
            return result
            
        finally:
            # Clean up temporary file
            try:
                os_module.unlink(mech_path)
            except Exception:
                pass
                
    except FileNotFoundError as e:
        return f"Error: {e}. Please ensure nasa_gas.yaml and nasa_condensed.yaml are in the mechanisms/ folder."
    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        import traceback
        return f"Error calculating metal combustion equilibrium: {e}\n\nTraceback:\n{traceback.format_exc()}"


# =============================================================================
# Lab Bench Tools - Stateful Mixture Management
# =============================================================================

@mcp.tool()
def create_lab_mixture(params: LabBenchMixtureInput) -> str:
    """Create a named mixture on the lab bench for kinetic analysis.
    
    This stores a Cantera Solution object that can be used for subsequent
    reaction rate and pathway analysis. The mixture retains its state until
    modified or replaced.
    """
    try:
        mechanism = resolve_mechanism(params.mechanism)
        gas = ct.Solution(mechanism)
        gas.TPX = params.temperature, params.pressure, params.composition
        
        store_solution(params.name, gas)
        
        result = f"""Created mixture '{params.name}' on lab bench:

=== State ===
Mechanism:   {mechanism}
Temperature: {gas.T:.2f} K
Pressure:    {gas.P:.2f} Pa ({gas.P/1e5:.4f} bar)
Density:     {gas.density:.6f} kg/m³

=== Composition (mole fractions > 0.1%) ===
"""
        for sp, x in zip(gas.species_names, gas.X):
            if x > 0.001:
                result += f"  {sp}: {x*100:.4f}%\n"
        
        result += f"\n=== Kinetics ===\n"
        result += f"Number of species:   {gas.n_species}\n"
        result += f"Number of reactions: {gas.n_reactions}\n"
        
        return result
    except Exception as e:
        return f"Error creating mixture: {str(e)}"


@mcp.tool()
def list_lab_mixtures() -> str:
    """List all mixtures currently stored on the lab bench."""
    if not _lab_bench:
        return "Lab bench is empty. Use create_lab_mixture to add mixtures."
    
    result = "### Mixtures on Lab Bench\n\n"
    for name, gas in _lab_bench.items():
        result += f"- **{name}**: T={gas.T:.1f} K, P={gas.P/1e5:.3f} bar, {gas.n_species} species\n"
    
    return result


# =============================================================================
# Kinetics & Rates Tools
# =============================================================================

@mcp.tool()
def get_reaction_rates(params: ReactionRatesInput) -> str:
    """Get a list of the fastest reactions currently occurring in a mixture.
    
    Use this to understand which reactions dominate under current conditions.
    The mixture must first be created on the lab bench using create_lab_mixture.
    """
    try:
        gas = get_solution(params.name)
        net_rates = gas.net_rates_of_progress
        
        # Filter reactions exceeding the threshold
        active_indices = np.where(np.abs(net_rates) > params.threshold)[0]
        
        # Sort by magnitude (fastest first)
        sorted_indices = sorted(active_indices, key=lambda i: abs(net_rates[i]), reverse=True)
        
        if not sorted_indices:
            return f"No reactions exceed rate threshold {params.threshold} kmol/m³/s.\n\nTip: Try lowering the threshold (e.g., 1e-9) or check mixture temperature."

        result = f"### Top Reactions in '{params.name}' (Rate > {params.threshold} kmol/m³/s)\n"
        result += f"Conditions: T={gas.T:.1f} K, P={gas.P/1e5:.3f} bar\n\n"
        
        for i in sorted_indices[:20]:  # Limit to top 20
            eqn = gas.reaction_equation(i)
            rate = net_rates[i]
            direction = "→" if rate > 0 else "←"
            result += f"- [Rxn {i}] {eqn}: {rate:.4e} kmol/m³/s {direction}\n"
        
        if len(sorted_indices) > 20:
            result += f"\n... and {len(sorted_indices) - 20} more reactions above threshold.\n"
            
        return result
    except KeyError as e:
        return str(e)
    except Exception as e:
        return f"Error calculating rates: {str(e)}"


@mcp.tool()
def get_species_production_contributors(params: SpeciesProductionInput) -> str:
    """Identify which reactions are creating or consuming a specific species.
    
    Critical for pathway analysis (e.g., 'Where is the NO coming from?' or
    'What reactions consume OH?'). The mixture must first be created on the
    lab bench using create_lab_mixture.
    """
    try:
        gas = get_solution(params.name)
        
        if params.species not in gas.species_names:
            available = [s for s in gas.species_names if params.species.upper() in s.upper()][:10]
            return f"Species '{params.species}' not found in mixture.\n\nSimilar species: {available if available else 'none'}"
            
        k = gas.species_index(params.species)
        net_rates = gas.net_rates_of_progress
        
        # Calculate contribution of each reaction to this species: 
        # Contribution = (ProductStoich - ReactantStoich) * Rate
        prod_stoich = gas.product_stoich_coeffs()[:, k]
        react_stoich = gas.reactant_stoich_coeffs()[:, k]
        contributions = (prod_stoich - react_stoich) * net_rates
        
        # Sort contributors
        creation_indices = np.argsort(contributions)[::-1]  # Largest positive first
        consumption_indices = np.argsort(contributions)      # Most negative first
        
        result = f"### Pathway Analysis for {params.species} in '{params.name}'\n"
        result += f"Conditions: T={gas.T:.1f} K, P={gas.P/1e5:.3f} bar\n\n"
        
        # Net production rate
        net_prod = gas.net_production_rates[k]
        result += f"**Net production rate:** {net_prod:.4e} kmol/m³/s\n\n"
        
        result += f"**Top Sources (Production):**\n"
        count = 0
        for i in creation_indices:
            if contributions[i] <= 0 or count >= params.limit:
                break
            eqn = gas.reaction_equation(i)
            result += f"- [Rxn {i}] {eqn}: +{contributions[i]:.2e} kmol/m³/s\n"
            count += 1
        if count == 0:
            result += "- No significant production reactions\n"
            
        result += f"\n**Top Sinks (Consumption):**\n"
        count = 0
        for i in consumption_indices:
            if contributions[i] >= 0 or count >= params.limit:
                break
            eqn = gas.reaction_equation(i)
            result += f"- [Rxn {i}] {eqn}: {contributions[i]:.2e} kmol/m³/s\n"
            count += 1
        if count == 0:
            result += "- No significant consumption reactions\n"
            
        return result
    except KeyError as e:
        return str(e)
    except Exception as e:
        return f"Error in pathway analysis: {str(e)}"


# =============================================================================
# Reactor Network Tools
# =============================================================================

@mcp.tool()
def run_batch_reactor(params: BatchReactorInput) -> str:
    """Simulate a Constant Pressure (Ideal Gas) Batch Reactor over time.
    
    Use this to see how temperature and composition evolve during combustion
    or other chemical reactions. The mixture state on the lab bench is updated
    to the final reacted state after simulation.
    """
    try:
        gas = get_solution(params.name)
        
        # Create a temporary reactor environment
        r = ct.IdealGasReactor(gas, clone=False)
        sim = ct.ReactorNet([r])
        
        times = np.linspace(0, params.duration, params.steps)
        # Track T and top 3 species for the report
        top_species_indices = np.argsort(gas.X)[::-1][:3]
        top_species_names = [gas.species_name(i) for i in top_species_indices]
        
        report = [f"### Batch Reactor Simulation ({params.duration}s)"]
        report.append(f"Initial T: {gas.T:.1f} K, P: {gas.P/1e5:.3f} bar\n")
        header = f"| Time (s) | Temp (K) | {' | '.join(top_species_names)} |"
        report.append(header)
        report.append("|---" * (2 + len(top_species_names)) + "|")
        
        for t in times:
            sim.advance(t)
            # Format mole fractions
            concs = [f"{r.phase.X[i]:.2e}" for i in top_species_indices]
            row = f"| {t:.2e} | {r.T:.1f} | {' | '.join(concs)} |"
            report.append(row)
        
        # IMPORTANT: Sync the lab bench object to the final state
        # so subsequent tools see the "reacted" mixture.
        gas.TPX = r.phase.TPX
        
        report.append(f"\nFinal T: {gas.T:.1f} K (ΔT = {gas.T - times[0]:.1f} K)")
        
        return "\n".join(report)
    except KeyError as e:
        return str(e)
    except Exception as e:
        return f"Reactor simulation failed: {str(e)}"


@mcp.tool()
def compute_ignition_delay(params: IgnitionDelayInput) -> str:
    """Calculate the auto-ignition delay time of the mixture.
    
    Defined as the time point where the temperature rise is steepest (dT/dt is max).
    This is commonly used for characterizing fuel reactivity and validating
    chemical kinetic mechanisms.
    
    Note: This tool does NOT update the lab bench mixture state to preserve
    the original mixture for other tests.
    """
    try:
        gas = get_solution(params.name)
        initial_T = gas.T
        initial_P = gas.P
        initial_X = gas.X.copy()
        
        # Create a copy for simulation (don't modify original)
        # Use gas.source to get the full mechanism file path (gas.name only returns the phase name)
        gas_copy = ct.Solution(gas.source)
        gas_copy.TPX = initial_T, initial_P, initial_X
        
        # Setup reactor
        r = ct.IdealGasReactor(gas_copy, clone=False)
        sim = ct.ReactorNet([r])
        
        previous_T = initial_T
        previous_time = 0.0
        max_dT_dt = 0.0
        ignition_time = -1.0
        
        while sim.time < params.max_time:
            current_time = sim.step()  # Let Cantera determine the internal time step
            current_T = r.T
            
            # Calculate temperature derivative
            dt = current_time - previous_time
            if dt > 0:
                dT_dt = (current_T - previous_T) / dt
                
                # Update max derivative
                if dT_dt > max_dT_dt:
                    max_dT_dt = dT_dt
                    ignition_time = current_time
            
            # If Temperature jumps significantly (e.g., 400K), we likely ignited
            if current_T > initial_T + 400:
                break
            
            previous_T = current_T
            previous_time = current_time
        
        final_T = r.T
        
        if ignition_time < 0 or final_T < initial_T + 50:
            return f"No ignition detected within {params.max_time} seconds.\nFinal temperature: {final_T:.1f} K (ΔT = {final_T - initial_T:.1f} K)"
        
        return (f"### Auto-Ignition Analysis\n\n"
                f"**Ignition Delay Time:** {ignition_time:.4e} seconds ({ignition_time*1000:.3f} ms)\n\n"
                f"- Initial Temperature: {initial_T:.1f} K\n"
                f"- Final Temperature: {final_T:.1f} K\n"
                f"- Temperature Rise: {final_T - initial_T:.1f} K\n"
                f"- Max dT/dt: {max_dT_dt:.2e} K/s\n\n"
                f"*Note: Lab bench mixture preserved at initial state.*")
        
    except KeyError as e:
        return str(e)
    except Exception as e:
        return f"Ignition calculation failed: {str(e)}"

# =============================================================================
# Prompts
# =============================================================================

@mcp.prompt()
def setup_combustion_lab(mechanism: str = "gri30.yaml", fuel: str = "CH4") -> str:
    """
    Sets up a standard combustion environment. 
    Loads the mechanism, creates a 'gas' object, and sets ambient conditions.
    """
    return f"""
    Please initialize the laboratory for combustion analysis:
    1. Call create_lab_mixture(mechanism='{mechanism}', name='gas', temperature=300, pressure=101325, composition='{fuel}:1, O2:1, N2:3.76').
    2. This sets the 'gas' to ambient conditions at the specified stoichiometry.
    3. Use get_mixture_properties(name='gas') to verify the initial state.
    """

@mcp.prompt()
def calculate_adiabatic_flame(fuel: str = "CH4", oxidizer: str = "O2:1, N2:3.76") -> str:
    """
    Workflow to find the Adiabatic Flame Temperature (AFT) using the lab bench.
    """
    return f"""
    Please calculate the Adiabatic Flame Temperature for {fuel} with {oxidizer} using the lab bench:
    1. Create a mixture named 'combustion_mix' using gri30.yaml with {fuel} and {oxidizer} at 300K, 1 atm.
       (Note: You may need to guess stoichiometry or use 1:1 if not specified, but usually providing composition string is best. Alternatively use calculate_adiabatic_flame_temperature tool which is a shortcut).
    2. If using the lab bench manually:
       a. Call create_lab_mixture(...) with the reagents.
       b. Call equilibrate(name='combustion_mix', basis='HP').
    3. Report the final Temperature (this is the AFT) and the mole fractions of major products.
    """

@mcp.prompt()
def analyze_pollutant_pathways(pollutant: str = "NO") -> str:
    """
    Investigate how a specific pollutant is forming.
    """
    return f"""
    I need to understand the formation of {pollutant} in the current mixture:
    1. Check if '{pollutant}' exists in the current mechanism.
    2. Run 'get_species_production_contributors' for {pollutant}.
    3. Based on the output, explain which reactions are the primary sources (production) and sinks (consumption).
    4. Suggest one experimental change (e.g., lowering Temp, changing Equivalence Ratio) that might reduce {pollutant} formation.
    """

@mcp.prompt()
def run_equilibrium_sweep(
    parameter: str = "equivalence_ratio", 
    start: float = 0.5, 
    end: float = 1.5, 
    steps: int = 6, 
    fuel: str = "CH4"
) -> str:
    """
    Generates a plan to vary one parameter (phi, P, or T) and track equilibrium results.
    Useful for generating T-phi curves or analyzing pressure effects.
    """
    
    # We construct a specific instruction based on what parameter is being swept
    param_instruction = ""
    if parameter.lower() in ["phi", "equivalence_ratio", "equivalence ratio"]:
        param_instruction = (
            f"Vary the Equivalence Ratio (phi) of {fuel}/Air from {start} to {end} "
            f"in {steps} even steps. For each step, calculate the corresponding "
            f"mole fractions (X) for the fuel/air mix."
        )
    elif parameter.lower() in ["p", "pressure"]:
        param_instruction = (
            f"Vary the Pressure (P) from {start} Pa to {end} Pa in {steps} even steps "
            f"while keeping composition stoichiometric."
        )
    elif parameter.lower() in ["t", "temperature"]:
        param_instruction = (
            f"Vary the Initial Temperature (T) from {start} K to {end} K in {steps} "
            f"even steps before equilibration."
        )
    else:
        # Fallback for generic composition sweeps
        param_instruction = (
            f"Vary the parameter '{parameter}' from {start} to {end} in {steps} steps."
        )

    return f"""
    Please perform a 1-D Equilibrium Sensitivity Study for {fuel} combustion.
    
    **Goal:** Determine how varying **{parameter}** affects the Adiabatic Flame Temperature and NO formation.
    
    **Plan:**
    1. Initialize a mixture named 'sweep_mix' using 'gri30.yaml'.
    2. {param_instruction}
    3. For EACH step in the sweep:
       a. If varying Phi/Comp, create/update 'sweep_mix' with new composition.
       b. If varying T or P, update 'sweep_mix' state.
       c. Call equilibrate(name='sweep_mix', basis='HP').
       d. Record the final Temperature (T_ad) and the mole fraction of NO.
    
    **Output Format:**
    Present your findings in a single Markdown table with these columns:
    | {parameter} | T_adiabatic (K) | X_NO (ppm) |
    
    **Analysis:**
    After the table, briefly summarize the trend. Does increasing {parameter} raise or lower the temperature?
    """

# =============================================================================
# Resources
# =============================================================================

@mcp.resource("cantera://nasa_gas")
def nasa_gas():
    """
    Load the NASA gas thermodynamics database.
    """
    return CanteraGas("nasa_gas.yaml")
    

# =============================================================================
# Server Entry Point
# =============================================================================

def main() -> None:
    """Main entry point for the MCP server."""
    logger.info("Starting MCP Server for Cantera (FastMCP)")
    mcp.run()


if __name__ == "__main__":
    main()
