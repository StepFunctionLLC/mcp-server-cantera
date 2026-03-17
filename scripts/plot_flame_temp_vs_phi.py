# Copyright Step Function, 2026
#!/usr/bin/env python3
"""Plot adiabatic flame temperature vs equivalence ratio for jet fuel/air combustion."""

import numpy as np
import matplotlib.pyplot as plt
import cantera as ct
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))
from mcp_server_cantera.server import resolve_mechanism

# Parameters
mechanism = resolve_mechanism("JetSurf2.yaml")  # Jet fuel surrogate mechanism
fuel = "NC12H26:1"  # n-Dodecane as jet fuel surrogate (Jet-A surrogate)
oxidizer = "O2:1, N2:3.76"  # Air
initial_temperature = 298.15  # K (25°C)
pressure = 101325  # Pa (1 atm)

# Equivalence ratio range
phi_values = np.linspace(0.1, 2.0, 50)
T_flame = []

print("Calculating adiabatic flame temperatures...")
print(f"Mechanism: {mechanism}")
print(f"Fuel: {fuel}")
print(f"Oxidizer: {oxidizer}")
print(f"Initial T: {initial_temperature} K, P: {pressure/1e5:.2f} bar")
print("\nCalculating for equivalence ratios from 0.1 to 2.0...")

for i, phi in enumerate(phi_values):
    try:
        gas = ct.Solution(mechanism)
        gas.set_equivalence_ratio(phi, fuel, oxidizer)
        gas.TP = initial_temperature, pressure
        
        # Equilibrate at constant enthalpy and pressure
        gas.equilibrate('HP')
        
        T_flame.append(gas.T)
        
        if (i + 1) % 10 == 0:
            print(f"  φ = {phi:.2f}: T_flame = {gas.T:.2f} K")
            
    except Exception as e:
        print(f"  Error at φ = {phi:.2f}: {e}")
        T_flame.append(np.nan)

# Create the plot
plt.figure(figsize=(10, 6))
plt.plot(phi_values, T_flame, 'b-', linewidth=2)
plt.axvline(x=1.0, color='r', linestyle='--', alpha=0.7, label='Stoichiometric (φ=1)')
plt.grid(True, alpha=0.3)
plt.xlabel('Equivalence Ratio (φ)', fontsize=12)
plt.ylabel('Adiabatic Flame Temperature (K)', fontsize=12)
plt.title('Adiabatic Flame Temperature vs Equivalence Ratio\nJet Fuel/Air Combustion', fontsize=14)
plt.legend(fontsize=10)

# Add secondary axis for Celsius
ax1 = plt.gca()
ax2 = ax1.twinx()
ax2.set_ylabel('Temperature (°C)', fontsize=12)
y1, y2 = ax1.get_ylim()
ax2.set_ylim(y1 - 273.15, y2 - 273.15)

# Find and annotate peak temperature
max_idx = np.nanargmax(T_flame)
max_phi = phi_values[max_idx]
max_temp = T_flame[max_idx]
plt.sca(ax1)
plt.plot(max_phi, max_temp, 'ro', markersize=8)
plt.annotate(f'Peak: φ={max_phi:.2f}\nT={max_temp:.0f} K ({max_temp-273.15:.0f}°C)',
             xy=(max_phi, max_temp),
             xytext=(max_phi + 0.3, max_temp - 200),
             fontsize=10,
             bbox=dict(boxstyle='round,pad=0.5', facecolor='yellow', alpha=0.7),
             arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0.3'))

plt.tight_layout()
plt.savefig('adiabatic_flame_temp_vs_phi.png', dpi=300, bbox_inches='tight')
print(f"\nPlot saved as 'adiabatic_flame_temp_vs_phi.png'")
print(f"\nPeak temperature: {max_temp:.2f} K ({max_temp-273.15:.2f}°C) at φ={max_phi:.2f}")
plt.show()
