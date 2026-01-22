
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
    result_create = create_lab_mixture.fn(create_input)
    assert "Created mixture 'test_mix_1'" in result_create

    # 2. Get Properties
    prop_input = LabBenchMeasurementInput(name="test_mix_1")
    result_props = get_mixture_properties.fn(prop_input)
    assert "Temperature:           300.00 K" in result_props
    assert "Pressure:              101325.00 Pa" in result_props

    # 3. Equilibrate (HP) - Adiabatic
    eq_input = LabBenchEquilibriumInput(name="test_mix_1", basis="HP")
    result_eq = equilibrate.fn(eq_input)
    assert "Equilibrium Calculation" in result_eq
    assert "Temperature:" in result_eq
    # Expect temperature rise for combustion
    # Parse output or just check it's higher than 300
    # Ideally we'd access the lab bench state to verify, but checking output string is okay for integration test
    
    # 4. Check Properties again (should be hot now)
    result_props_2 = get_mixture_properties.fn(prop_input)
    # The temperature should be >> 300K
    assert "300.00 K" not in result_props_2

def test_run_batch_reactor():
    """Test batch reactor simulation."""
    # Create reactive mixture
    create_input = LabBenchMixtureInput(
        name="reactor_mix",
        mechanism="gri30.yaml",
        composition="H2:2, O2:1, N2:3.76",
        temperature=1000,
        pressure=101325
    )
    create_lab_mixture.fn(create_input)

    # Run reactor
    reactor_input = BatchReactorInput(
        name="reactor_mix",
        duration=0.001, # 1ms
        steps=5
    )
    result_reactor = run_batch_reactor.fn(reactor_input)
    assert "Batch Reactor Simulation" in result_reactor
    assert "Final T:" in result_reactor
    
    # Check if temperature changed (H2 at 1000K should react fast)
    # Note: Ignition delay is ~0.3ms at 1000K, so 1ms should be enough for significant reaction

def test_ignition_delay():
    """Test ignition delay calculation."""
    # Create reactive mixture (H2/Air at 1000K)
    create_input = LabBenchMixtureInput(
        name="ignition_mix",
        mechanism="gri30.yaml",
        composition="H2:2, O2:1, N2:3.76",
        temperature=1000,
        pressure=101325
    )
    create_lab_mixture.fn(create_input)

    # Compute delay
    delay_input = IgnitionDelayInput(name="ignition_mix", max_time=0.1)
    result_delay = compute_ignition_delay.fn(delay_input)
    
    assert "Ignition Delay Time:" in result_delay
    # Should be around 3e-4 seconds
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
    result = calculate_adiabatic_flame_temperature.fn(input_data)
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
    result = calculate_metal_combustion_equilibrium.fn(input_data)
    
    assert "Metal Combustion Equilibrium Calculation (Multi-Phase)" in result
    assert "Adiabatic flame temperature:" in result
    assert "Equilibrium Condensed Phase Composition" in result
    # We expect iron oxides like Fe3O4 or Fe2O3
    assert "Fe3O4" in result or "Fe2O3" in result or "FeO" in result


# --- Database Fallback Tests ---

def test_check_species_availability():
    """Test checking for species in GRI vs NASA."""
    input_data = SpeciesAvailabilityInput(species_list=["CH4", "He", "NonExistentSpecies123"])
    result = check_species_availability.fn(input_data)
    
    assert "CH4: ✓ Available (GRI-Mech 3.0)" in result
    assert "He: ✓ Available" in result # Should be in one of them (actually in both usually, but code checks GRI first)
    assert "NonExistentSpecies123: ✗ NOT FOUND" in result

def test_get_species_thermo_fallback():
    """Test getting properties for species not in GRI30."""
    # 'Xe' is typically not in gri30 but is in nasa_gas
    input_data = SpeciesThermoInput(
        species="Xe", 
        temperature_k=300,
        pressure_bar=1.0
    )
    result = get_species_thermo.fn(input_data)
    
    assert "Source: NASA Gas Database" in result or "Source: GRI-Mech 3.0" in result # In case GRI has Xe
    assert "Molar Mass:" in result
