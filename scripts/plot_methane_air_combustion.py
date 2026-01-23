# Copyright Step Function, 2026
"""
Plot methane/air adiabatic flame temperature and product composition vs equivalence ratio.
Data generated using Cantera MCP Server with GRI-Mech 3.0.
"""
import matplotlib.pyplot as plt
import numpy as np

# Data from Cantera MCP Server queries
phi = np.array([0.5, 0.7, 0.9, 1.0, 1.1, 1.3, 1.5, 1.8, 2.0])

# Adiabatic flame temperatures (K)
T_ad = np.array([1478.62, 1837.19, 2133.06, 2224.54, 2209.20, 2055.95, 1903.42, 1693.05, 1563.52])

# Major product species mole fractions
N2 = np.array([0.750117, 0.734422, 0.718357, 0.708611, 0.693594, 0.658226, 0.625536, 0.582028, 0.556209])
H2O = np.array([0.099772, 0.136542, 0.169992, 0.183495, 0.189553, 0.183150, 0.167284, 0.138717, 0.119519])
CO2 = np.array([0.049899, 0.068389, 0.083849, 0.085405, 0.075363, 0.052920, 0.040632, 0.031555, 0.028409])
O2 = np.array([0.099412, 0.057361, 0.018470, 0.004604, 0.000342, 0.0, 0.0, 0.0, 0.0])
CO = np.array([0.0, 0.0, 0.002309, 0.008951, 0.026129, 0.060872, 0.084143, 0.107760, 0.119519])
H2 = np.array([0.0, 0.0, 0.000927, 0.003591, 0.012387, 0.044073, 0.082129, 0.139884, 0.176326])
NO = np.array([0.000742, 0.002383, 0.003068, 0.001880, 0.000490, 0.0, 0.0, 0.0, 0.0])

# Create figure with two subplots
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

# Plot 1: Adiabatic Flame Temperature
ax1.plot(phi, T_ad, 'o-', color='#dc2626', linewidth=2.5, markersize=8, 
         markerfacecolor='white', markeredgewidth=2)
ax1.axvline(x=1.0, color='gray', linestyle='--', alpha=0.5, label='Stoichiometric')
ax1.set_xlabel('Equivalence Ratio (φ)', fontsize=12)
ax1.set_ylabel('Adiabatic Flame Temperature (K)', fontsize=12)
ax1.set_title('Methane/Air Adiabatic Flame Temperature', fontsize=14, fontweight='bold')
ax1.grid(True, alpha=0.3)
ax1.set_xlim(0.4, 2.1)
ax1.set_ylim(1400, 2400)
ax1.legend(loc='lower right')

# Add annotation for peak temperature
peak_idx = np.argmax(T_ad)
ax1.annotate(f'Peak: {T_ad[peak_idx]:.0f} K\n(φ = {phi[peak_idx]})', 
             xy=(phi[peak_idx], T_ad[peak_idx]),
             xytext=(phi[peak_idx] + 0.3, T_ad[peak_idx] + 50),
             fontsize=10, ha='left',
             arrowprops=dict(arrowstyle='->', color='gray'))

# Plot 2: Product Composition
ax2.plot(phi, H2O * 100, 'o-', label='H₂O', color='#2563eb', linewidth=2, markersize=6)
ax2.plot(phi, CO2 * 100, 's-', label='CO₂', color='#059669', linewidth=2, markersize=6)
ax2.plot(phi, O2 * 100, '^-', label='O₂', color='#7c3aed', linewidth=2, markersize=6)
ax2.plot(phi, CO * 100, 'D-', label='CO', color='#ea580c', linewidth=2, markersize=6)
ax2.plot(phi, H2 * 100, 'v-', label='H₂', color='#0891b2', linewidth=2, markersize=6)
ax2.plot(phi, NO * 100, 'p-', label='NO', color='#be185d', linewidth=2, markersize=6)

ax2.axvline(x=1.0, color='gray', linestyle='--', alpha=0.5)
ax2.set_xlabel('Equivalence Ratio (φ)', fontsize=12)
ax2.set_ylabel('Mole Fraction (%)', fontsize=12)
ax2.set_title('Product Gas Composition (excluding N₂)', fontsize=14, fontweight='bold')
ax2.grid(True, alpha=0.3)
ax2.set_xlim(0.4, 2.1)
ax2.set_ylim(0, 20)
ax2.legend(loc='upper right', ncol=2)

# Add lean/rich annotations
ax2.text(0.6, 18.5, 'Lean', fontsize=11, ha='center', style='italic', color='gray')
ax2.text(1.6, 18.5, 'Rich', fontsize=11, ha='center', style='italic', color='gray')

plt.tight_layout()

# Save figure
output_path = '../output/methane_air_combustion.png'
plt.savefig(output_path, dpi=150, bbox_inches='tight')
print(f"Figure saved as '{output_path}'")

plt.show()
