# Copyright Step Function, 2026

import pytest
import cantera as ct
from mcp_server_cantera.server import (
    create_lab_mixture,
    get_mixture_properties,
    calculate_adiabatic_flame_temperature,
    calculate_metal_combustion_equilibrium,
    run_batch_reactor,
    compute_ignition_delay,
    check_species_availability,
    get_species_thermo,
    equilibrate
)
from mcp_server_cantera.schema import (
    LabBenchMixtureInput,
    LabBenchMeasurementInput,
    CombustionInput,
    MetalCombustionInput,
    BatchReactorInput,
    IgnitionDelayInput,
    SpeciesAvailabilityInput,
    SpeciesThermoInput,
    LabBenchEquilibriumInput
)

# --- Lab Bench Tests ---

def test_lab_bench_lifecycle():
    """Test creating a mixture, getting properties, and running a reactor."""
    # 1. Create Mixture
    create_input = LabBenchMixtureInput(
        name="test_mix_1",
        mechanism="gri30.yaml",
        composition="CH4:1, O2:2, N2:7.52",
        temperature=300,
        pressure=101325
    )
    result_create = create_lab_mixture(create_input)
    assert "Created mixture 'test_mix_1'" in result_create

    # 2. Get Properties
    prop_input = LabBenchMeasurementInput(name="test_mix_1")
    result_props = get_mixture_properties(prop_input)
    assert "Temperature:           300.00 K" in result_props
    assert "Pressure:              101325.00 Pa" in result_props

    # 3. Equilibrate (HP) - Adiabatic
    eq_input = LabBenchEquilibriumInput(name="test_mix_1", basis="HP")
    result_eq = equilibrate(eq_input)
    assert "Equilibrium Calculation" in result_eq
    assert "Temperature:" in result_eq
    
    # 4. Check Properties again (should be hot now)
    result_props_2 = get_mixture_properties(prop_input)
    assert "300.00 K" not in result_props_2

def test_run_batch_reactor():
    """Test batch reactor simulation."""
    create_input = LabBenchMixtureInput(
        name="reactor_mix",
        mechanism="gri30.yaml",
        composition="H2:2, O2:1, N2:3.76",
        temperature=1000,
        pressure=101325
    )
    create_lab_mixture(create_input)

    reactor_input = BatchReactorInput(
        name="reactor_mix",
        duration=0.001, # 1ms
        steps=5
    )
    result_reactor = run_batch_reactor(reactor_input)
    assert "Batch Reactor Simulation" in result_reactor
    assert "Final T:" in result_reactor

def test_ignition_delay():
    """Test ignition delay calculation."""
    create_input = LabBenchMixtureInput(
        name="ignition_mix",
        mechanism="gri30.yaml",
        composition="H2:2, O2:1, N2:3.76",
        temperature=1000,
        pressure=101325
    )
    create_lab_mixture(create_input)

    delay_input = IgnitionDelayInput(name="ignition_mix", max_time=0.1)
    result_delay = compute_ignition_delay(delay_input)
    
    assert "Ignition Delay Time:" in result_delay
    assert "seconds" in result_delay

# --- Combustion Tests ---

def test_adiabatic_flame_temp_methane():
    """Test basic gas phase flame temperature."""
    input_data = CombustionInput(
        mechanism="gri30.yaml",
        fuel="CH4:1",
        oxidizer="O2:2, N2:7.52",
        equivalence_ratio=1.0,
        initial_temperature=300,
        pressure=101325
    )
    result = calculate_adiabatic_flame_temperature(input_data)
    assert "Adiabatic flame temperature:" in result
    assert "222" in result or "223" in result # T ~ 2225K
    assert "(stoichiometric)" in result

def test_metal_combustion_fe():
    """Test iron combustion (multi-phase)."""
    input_data = MetalCombustionInput(
        metal="Fe",
        oxidizer="air",
        equivalence_ratio=1.0
    )
    result = calculate_metal_combustion_equilibrium(input_data)
    
    assert "Metal Combustion Equilibrium Calculation (Multi-Phase)" in result
    assert "Adiabatic flame temperature:" in result
    assert "Equilibrium Condensed Phase Composition" in result
    assert "Fe3O4" in result or "Fe2O3" in result or "FeO" in result

# --- Database Fallback Tests ---

def test_check_species_availability():
    """Test checking for species in GRI vs NASA."""
    input_data = SpeciesAvailabilityInput(species_list=["CH4", "He", "NonExistentSpecies123"])
    result = check_species_availability(input_data)
    
    assert "CH4: ✓ Available (GRI-Mech 3.0)" in result
    assert "He: ✓ Available" in result
    assert "NonExistentSpecies123: ✗ NOT FOUND" in result

def test_get_species_thermo_fallback():
    """Test getting properties for species not in GRI30."""
    input_data = SpeciesThermoInput(
        species="Xe", 
        temperature_k=300,
        pressure_bar=1.0
    )
    result = get_species_thermo(input_data)
    
    assert "Source: NASA Gas Database" in result or "Source: GRI-Mech 3.0" in result
    assert "Molar Mass:" in result
