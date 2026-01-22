#!/usr/bin/env python3
"""Test script to calculate adiabatic flame temperature for methane-air combustion."""

import cantera as ct
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from mcp_server_cantera.server import resolve_mechanism

# Parameters
mechanism = resolve_mechanism("gri30.yaml")
fuel = "CH4:1"
oxidizer = "O2:1, N2:3.76"
equivalence_ratio = 1.0
initial_temperature = 298.15  # K (25°C)
pressure = 101325  # Pa (1 atm)

# Calculate
gas = ct.Solution(mechanism)
gas.set_equivalence_ratio(equivalence_ratio, fuel, oxidizer)
gas.TP = initial_temperature, pressure

# Store initial state
initial_H = gas.enthalpy_mass

# Equilibrate at constant enthalpy and pressure (adiabatic)
gas.equilibrate('HP')

# Display results
print("=" * 70)
print("Adiabatic Flame Temperature Calculation")
print("=" * 70)
print(f"\n=== Combustion Setup ===")
print(f"Mechanism:          {mechanism}")
print(f"Fuel:               {fuel}")
print(f"Oxidizer:           {oxidizer}")
print(f"Equivalence ratio:  {equivalence_ratio:.3f} (stoichiometric)")
print(f"Initial temperature: {initial_temperature:.2f} K")
print(f"Pressure:           {pressure:.2f} Pa ({pressure/1e5:.4f} bar)")

print(f"\n=== Results ===")
print(f"Adiabatic flame temperature: {gas.T:.2f} K ({gas.T - 273.15:.2f} °C)")
print(f"Temperature rise:            {gas.T - initial_temperature:.2f} K")

print(f"\n=== Major Product Species (X > 0.1%) ===")
for species, mole_frac in zip(gas.species_names, gas.X):
    if mole_frac > 0.001:
        print(f"  {species:8s}: {mole_frac*100:.4f}%")

print(f"\n=== Minor Product Species (0.01% < X < 0.1%) ===")
for species, mole_frac in zip(gas.species_names, gas.X):
    if 0.0001 < mole_frac <= 0.001:
        print(f"  {species:8s}: {mole_frac*100:.6f}%")

print("=" * 70)

