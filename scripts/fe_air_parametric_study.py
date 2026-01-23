# Copyright Step Function, 2026
#!/usr/bin/env python3
"""
Parametric study of Fe/air combustion across equivalence ratios.

This script calculates the adiabatic flame temperature and product species
composition for iron-air combustion from lean to rich conditions.
"""

import sys
import os
import re
import tempfile
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
import cantera as ct
import yaml

# Add the src directory to path for imports
src_dir = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_dir))


def get_mechanisms_dir() -> Path:
    """Get path to mechanisms directory."""
    return Path(__file__).parent.parent / "mechanisms"


def load_nasa_species_data(yaml_path: Path) -> list[dict]:
    """Load species data from NASA thermodynamic database."""
    with open(yaml_path, 'r') as f:
        data = yaml.safe_load(f)
    return data.get('species', [])


def find_metal_species(species_list: list[dict], metal_symbol: str) -> list[dict]:
    """Find species containing a specific metal element."""
    metal_species = []
    for sp in species_list:
        composition = sp.get('composition', {})
        if metal_symbol in composition:
            metal_species.append(sp)
    return metal_species


def find_species_by_names(species_list: list[dict], names: list[str]) -> list[dict]:
    """Find species by exact name match."""
    found = []
    for sp in species_list:
        if sp.get('name') in names:
            found.append(sp)
    return found


def build_metal_combustion_mechanism(metal: str) -> tuple[str, list[str], list[str]]:
    """Build a temporary mechanism file for metal-air combustion."""
    mech_dir = get_mechanisms_dir()
    gas_yaml = mech_dir / "nasa_gas.yaml"
    condensed_yaml = mech_dir / "nasa_condensed.yaml"
    
    if not gas_yaml.exists():
        raise FileNotFoundError(f"NASA gas database not found: {gas_yaml}")
    if not condensed_yaml.exists():
        raise FileNotFoundError(f"NASA condensed database not found: {condensed_yaml}")
    
    gas_species_all = load_nasa_species_data(gas_yaml)
    condensed_species_all = load_nasa_species_data(condensed_yaml)
    
    metal_gas_species = find_metal_species(gas_species_all, metal)
    metal_condensed_species = find_metal_species(condensed_species_all, metal)
    
    air_species_names = ['O2', 'N2', 'Ar', 'O', 'N', 'NO', 'NO2', 'O3']
    air_species = find_species_by_names(gas_species_all, air_species_names)
    
    gas_species = []
    seen_names = set()
    for sp in metal_gas_species + air_species:
        if sp['name'] not in seen_names:
            gas_species.append(sp)
            seen_names.add(sp['name'])
    
    gas_species_names = [sp['name'] for sp in gas_species]
    condensed_species_names = [sp['name'] for sp in metal_condensed_species]
    
    all_elements = set()
    for sp in gas_species:
        all_elements.update(sp.get('composition', {}).keys())
    for sp in metal_condensed_species:
        all_elements.update(sp.get('composition', {}).keys())
    all_elements = sorted(list(all_elements))
    
    mechanism = {
        'description': f'Dynamic metal combustion mechanism for {metal}/air equilibrium.',
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
        'species': list(gas_species)
    }
    
    if metal_condensed_species:
        for sp in metal_condensed_species:
            sp_name = sp['name']
            phase_name = re.sub(r'[^a-zA-Z0-9_]', '_', sp_name)
            mechanism['phases'].append({
                'name': phase_name,
                'thermo': 'fixed-stoichiometry',
                'elements': all_elements,
                'species': [sp_name],
                'state': {'T': 300.0, 'P': '1 atm'}
            })
            mechanism['species'].append(sp)
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(mechanism, f, default_flow_style=False, sort_keys=False)
        temp_path = f.name
    
    return temp_path, gas_species_names, condensed_species_names


def calc_mixture_enthalpy(mix: ct.Mixture) -> float:
    """Calculate total enthalpy of mixture from all phases."""
    H_total = 0.0
    for i in range(mix.n_phases):
        phase = mix.phase(i)
        phase_moles = mix.phase_moles(i)
        if phase_moles > 0:
            H_total += phase.enthalpy_mole * phase_moles
    return H_total


def calculate_equilibrium_at_phi(
    gas: ct.Solution,
    condensed_phases: list,
    phi: float,
    initial_T: float = 298.15,
    pressure: float = 101325.0
) -> dict:
    """
    Calculate adiabatic flame temperature and products at a given equivalence ratio.
    
    Returns dict with temperature and species compositions.
    """
    metal_symbol = "Fe"
    o2_moles = 1.0
    n2_moles = 3.76
    metal_moles = phi * o2_moles
    
    composition = f"{metal_symbol}:{metal_moles}, O2:{o2_moles}, N2:{n2_moles}"
    
    # Set initial state
    gas.TPX = initial_T, pressure, composition
    for cp in condensed_phases:
        cp.TP = initial_T, pressure
    
    # Create initial mixture
    phase_list = [(gas, 1.0)] + [(cp, 0.0) for cp in condensed_phases]
    mixture = ct.Mixture(phase_list)
    target_H = calc_mixture_enthalpy(mixture)
    
    # Bisection for adiabatic temperature
    T_low = initial_T
    T_high = 5000.0
    tolerance = 2.0
    
    best_mixture = None
    best_H_diff = float('inf')
    
    for iteration in range(60):
        T_guess = (T_low + T_high) / 2
        
        gas.TPX = T_guess, pressure, composition
        for cp in condensed_phases:
            cp.TP = T_guess, pressure
        
        phase_list = [(gas, 1.0)] + [(cp, 0.0) for cp in condensed_phases]
        mixture = ct.Mixture(phase_list)
        
        try:
            mixture.equilibrate('TP', max_steps=1000, log_level=0)
            equilibrated = True
        except Exception:
            equilibrated = False
        
        if equilibrated:
            current_H = calc_mixture_enthalpy(mixture)
            H_diff = abs(current_H - target_H)
            
            if H_diff < best_H_diff:
                best_H_diff = H_diff
                best_mixture = mixture
        else:
            current_H = target_H
        
        if abs(T_high - T_low) < tolerance:
            break
        
        if current_H < target_H:
            T_low = T_guess
        else:
            T_high = T_guess
    
    if best_mixture is None:
        best_mixture = mixture
    
    # Extract results
    result = {
        'T_ad': best_mixture.T,
        'gas_species': {},
        'condensed_species': {}
    }
    
    # Gas phase composition
    gas_phase = best_mixture.phase(0)
    for i, sp_name in enumerate(gas_phase.species_names):
        if gas_phase.X[i] > 1e-8:
            result['gas_species'][sp_name] = gas_phase.X[i]
    
    # Condensed phase composition
    total_condensed = 0.0
    for i in range(1, best_mixture.n_phases):
        phase_moles = best_mixture.phase_moles(i)
        if phase_moles > 1e-10:
            total_condensed += phase_moles
    
    for i in range(1, best_mixture.n_phases):
        phase_moles = best_mixture.phase_moles(i)
        if phase_moles > 1e-10:
            phase = best_mixture.phase(i)
            sp_name = phase.species_names[0] if len(phase.species_names) == 1 else phase.name
            result['condensed_species'][sp_name] = phase_moles / total_condensed if total_condensed > 0 else 0
    
    return result


def run_parametric_study():
    """Run the parametric study across equivalence ratios."""
    print("Building Fe/air combustion mechanism...")
    mech_path, gas_species_names, condensed_species_names = build_metal_combustion_mechanism("Fe")
    
    try:
        # Load phases
        gas = ct.Solution(mech_path, 'gas')
        condensed_phases = []
        for sp_name in condensed_species_names:
            phase_name = re.sub(r'[^a-zA-Z0-9_]', '_', sp_name)
            try:
                phase = ct.Solution(mech_path, phase_name)
                condensed_phases.append(phase)
            except Exception:
                pass
        
        print(f"Loaded {len(gas_species_names)} gas species, {len(condensed_phases)} condensed phases")
        
        # Define equivalence ratio range
        phi_values = np.linspace(0.1, 2.0, 40)
        
        # Storage for results
        T_ad_values = []
        all_gas_species = set()
        all_condensed_species = set()
        gas_compositions = []
        condensed_compositions = []
        
        print(f"\nRunning equilibrium calculations for {len(phi_values)} equivalence ratios...")
        for i, phi in enumerate(phi_values):
            print(f"  φ = {phi:.2f} ({i+1}/{len(phi_values)})", end='\r')
            result = calculate_equilibrium_at_phi(gas, condensed_phases, phi)
            T_ad_values.append(result['T_ad'])
            gas_compositions.append(result['gas_species'])
            condensed_compositions.append(result['condensed_species'])
            all_gas_species.update(result['gas_species'].keys())
            all_condensed_species.update(result['condensed_species'].keys())
        
        print("\n\nGenerating plots...")
        
        # Create figure with subplots
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle('Fe/Air Combustion Parametric Study', fontsize=14, fontweight='bold')
        
        # Plot 1: Adiabatic Flame Temperature
        ax1 = axes[0, 0]
        ax1.plot(phi_values, T_ad_values, 'b-', linewidth=2, marker='o', markersize=4)
        ax1.axvline(x=1.0, color='k', linestyle='--', alpha=0.5, label='Stoichiometric')
        ax1.set_xlabel('Equivalence Ratio (φ)', fontsize=11)
        ax1.set_ylabel('Adiabatic Flame Temperature (K)', fontsize=11)
        ax1.set_title('Adiabatic Flame Temperature vs Equivalence Ratio', fontsize=12)
        ax1.grid(True, alpha=0.3)
        ax1.legend()
        
        # Find and annotate max temperature
        max_idx = np.argmax(T_ad_values)
        max_T = T_ad_values[max_idx]
        max_phi = phi_values[max_idx]
        ax1.annotate(f'Max: {max_T:.0f} K at φ={max_phi:.2f}',
                     xy=(max_phi, max_T), xytext=(max_phi + 0.3, max_T - 200),
                     arrowprops=dict(arrowstyle='->', color='red'),
                     fontsize=10, color='red')
        
        # Plot 2: Major Gas Phase Species
        ax2 = axes[0, 1]
        major_gas_species = ['N2', 'O2', 'Fe', 'FeO', 'O']
        colors = plt.cm.tab10(np.linspace(0, 1, len(major_gas_species)))
        
        for sp_name, color in zip(major_gas_species, colors):
            if sp_name in all_gas_species:
                y_values = [gc.get(sp_name, 0) * 100 for gc in gas_compositions]
                if max(y_values) > 0.1:  # Only plot if > 0.1%
                    ax2.plot(phi_values, y_values, '-', linewidth=2, label=sp_name, color=color)
        
        ax2.axvline(x=1.0, color='k', linestyle='--', alpha=0.5)
        ax2.set_xlabel('Equivalence Ratio (φ)', fontsize=11)
        ax2.set_ylabel('Mole Fraction (%)', fontsize=11)
        ax2.set_title('Major Gas Phase Species', fontsize=12)
        ax2.grid(True, alpha=0.3)
        ax2.legend(loc='best')
        ax2.set_ylim(bottom=0)
        
        # Plot 3: Minor Gas Phase Species (Fe species)
        ax3 = axes[1, 0]
        minor_gas_species = [sp for sp in all_gas_species if 'Fe' in sp]
        colors = plt.cm.Set2(np.linspace(0, 1, max(len(minor_gas_species), 1)))
        
        for sp_name, color in zip(minor_gas_species, colors):
            y_values = [gc.get(sp_name, 0) * 100 for gc in gas_compositions]
            if max(y_values) > 0.01:  # Only plot if > 0.01%
                ax3.plot(phi_values, y_values, '-', linewidth=2, label=sp_name, color=color)
        
        ax3.axvline(x=1.0, color='k', linestyle='--', alpha=0.5)
        ax3.set_xlabel('Equivalence Ratio (φ)', fontsize=11)
        ax3.set_ylabel('Mole Fraction (%)', fontsize=11)
        ax3.set_title('Fe-containing Gas Phase Species', fontsize=12)
        ax3.grid(True, alpha=0.3)
        ax3.legend(loc='best')
        ax3.set_ylim(bottom=0)
        
        # Plot 4: Condensed Phase Products
        ax4 = axes[1, 1]
        colors = plt.cm.Paired(np.linspace(0, 1, max(len(all_condensed_species), 1)))
        
        for sp_name, color in zip(sorted(all_condensed_species), colors):
            y_values = [cc.get(sp_name, 0) * 100 for cc in condensed_compositions]
            if max(y_values) > 1:  # Only plot if > 1%
                ax4.plot(phi_values, y_values, '-', linewidth=2, label=sp_name, color=color)
        
        ax4.axvline(x=1.0, color='k', linestyle='--', alpha=0.5)
        ax4.set_xlabel('Equivalence Ratio (φ)', fontsize=11)
        ax4.set_ylabel('Fraction of Condensed Phase (%)', fontsize=11)
        ax4.set_title('Condensed Phase Products', fontsize=12)
        ax4.grid(True, alpha=0.3)
        ax4.legend(loc='best')
        ax4.set_ylim(0, 105)
        
        plt.tight_layout()
        
        # Save figure
        output_dir = Path(__file__).parent.parent / "output"
        output_dir.mkdir(exist_ok=True)
        output_path = output_dir / "fe_air_parametric_study.png"
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f"\nPlot saved to: {output_path}")
        
        plt.show()
        
        # Print summary
        print("\n" + "="*60)
        print("SUMMARY")
        print("="*60)
        print(f"Equivalence ratio range: {phi_values[0]:.2f} to {phi_values[-1]:.2f}")
        print(f"Maximum flame temperature: {max_T:.0f} K at φ = {max_phi:.2f}")
        print(f"Flame temperature at stoichiometric (φ=1): {T_ad_values[np.argmin(np.abs(phi_values - 1.0))]:.0f} K")
        print(f"\nCondensed phase products found: {sorted(all_condensed_species)}")
        print(f"Fe-containing gas species: {sorted([s for s in all_gas_species if 'Fe' in s])}")
        
    finally:
        # Cleanup
        try:
            os.unlink(mech_path)
        except Exception:
            pass


if __name__ == "__main__":
    run_parametric_study()
