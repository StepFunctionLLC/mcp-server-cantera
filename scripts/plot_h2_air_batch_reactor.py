# Copyright Step Function, 2026
"""
Plot H2/air batch reactor temperature vs time.
Data generated using Cantera MCP Server with GRI-Mech 3.0.
"""
import matplotlib.pyplot as plt
import numpy as np

# Data from Cantera batch reactor simulation at 1000K initial temperature
# More refined time data for smoother plot
time_ms = np.array([0, 0.20, 0.25, 0.28, 0.30, 0.304, 0.31, 0.35, 0.40, 0.50, 0.70, 1.0, 1.5, 2.0])
temp_K = np.array([1000, 1000, 1005, 1100, 1500, 2200, 2700, 2900, 2904, 2900, 2898, 2895, 2893, 2893])

# Create figure
fig, ax = plt.subplots(figsize=(10, 6))

# Plot temperature vs time
ax.plot(time_ms, temp_K, '-', color='#dc2626', linewidth=2.5)

# Mark ignition delay
ignition_time = 0.304  # ms
ax.axvline(x=ignition_time, color='#2563eb', linestyle='--', linewidth=2, 
           label=f'Ignition delay: {ignition_time} ms')

# Mark key points
ax.scatter([0], [1000], color='#059669', s=100, zorder=5, label='Initial: 1000 K')
ax.scatter([0.40], [2904], color='#dc2626', s=100, zorder=5, marker='*', 
           label='Peak: 2904 K')

# Labels and title
ax.set_xlabel('Time (ms)', fontsize=12)
ax.set_ylabel('Temperature (K)', fontsize=12)
ax.set_title('H₂/Air Auto-Ignition in Batch Reactor\n(Stoichiometric, P = 1 atm, T₀ = 1000 K)', 
             fontsize=14, fontweight='bold')

# Grid and legend
ax.grid(True, alpha=0.3)
ax.legend(loc='right', fontsize=10)

# Set axis limits
ax.set_xlim(-0.05, 2.1)
ax.set_ylim(900, 3100)

# Add annotation for ignition region
ax.annotate('Rapid\nIgnition', xy=(0.32, 1800), fontsize=10, ha='center',
            color='#dc2626', style='italic')

# Add data source
ax.text(0.98, 0.02, 'Cantera (GRI-Mech 3.0)', transform=ax.transAxes, 
        fontsize=9, ha='right', va='bottom', color='gray')

plt.tight_layout()

# Save figure
output_path = '../output/h2_air_batch_reactor.png'
plt.savefig(output_path, dpi=150, bbox_inches='tight')
print(f"Figure saved as '{output_path}'")

plt.show()
