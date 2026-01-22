#!/usr/bin/env python3
"""Calculate transport properties of air at standard conditions."""

import sys
from pathlib import Path
import cantera as ct

sys.path.insert(0, str(Path(__file__).parent / 'src'))
from mcp_server_cantera.server import resolve_mechanism

# Standard conditions: 25°C (298.15 K), 1 atm (101325 Pa)
mechanism = resolve_mechanism("air.yaml")
temperature = 298.15  # K
pressure = 101325.0   # Pa
composition = "N2:0.79, O2:0.21"

gas = ct.Solution(mechanism)
gas.TPX = temperature, pressure, composition

mix_diff_coeffs = gas.mix_diff_coeffs
Pr = gas.cp * gas.viscosity / gas.thermal_conductivity

result = f"""Transport Properties of Air at Standard Conditions:

=== Conditions ===
Temperature: {gas.T:.2f} K ({gas.T - 273.15:.2f} °C)
Pressure:    {gas.P:.2f} Pa ({gas.P/1e5:.4f} bar)

=== Mixture Transport Properties ===
Dynamic viscosity (μ):     {gas.viscosity:.6e} Pa·s
Kinematic viscosity (ν):   {gas.viscosity/gas.density:.6e} m²/s
Thermal conductivity (k):  {gas.thermal_conductivity:.6f} W/(m·K)
Thermal diffusivity (α):   {gas.thermal_conductivity/(gas.density*gas.cp):.6e} m²/s
Prandtl number (Pr):       {Pr:.4f}
Density:                   {gas.density:.6f} kg/m³

=== Species Mixture-Averaged Diffusion Coefficients ===
"""

for species, D, X in zip(gas.species_names, mix_diff_coeffs, gas.X):
    if X > 1e-10:
        result += f"  {species}: D = {D:.6e} m²/s (mole fraction: {X:.4f})\n"

print(result)
