
import os
import re
import yaml
import tempfile
import numpy as np
import cantera as ct
import matplotlib.pyplot as plt
from pathlib import Path

# --- Configuration ---
MECHANISMS_DIR = Path("/Users/davidtew/Library/CloudStorage/GoogleDrive-davetew@step-function.com/My Drive/Github/mcp-server-cantera/mechanisms")
METAL = "Fe"
OXIDIZER = "air"
P = 101325.0  # Pa
T_INITIAL = 298.15 # K
PHI_RANGE = np.linspace(0.1, 2.0, 40) # 40 points from 0.1 to 2.0

# --- Helper Functions (Adapted from server.py) ---

def load_nasa_species_data(yaml_path):
    with open(yaml_path, 'r') as f:
        data = yaml.safe_load(f)
    return data.get('species', [])

def find_metal_species(species_list, metal_symbol):
    metal_species = []
    for sp in species_list:
        composition = sp.get('composition', {})
        if metal_symbol in composition:
            metal_species.append(sp)
    return metal_species

def find_species_by_names(species_list, names):
    found = []
    for sp in species_list:
        if sp.get('name') in names:
            found.append(sp)
    return found

def build_metal_combustion_mechanism(metal):
    gas_yaml = MECHANISMS_DIR / "nasa_gas.yaml"
    condensed_yaml = MECHANISMS_DIR / "nasa_condensed.yaml"
    
    gas_species_all = load_nasa_species_data(gas_yaml)
    condensed_species_all = load_nasa_species_data(condensed_yaml)
    
    metal_gas_species = find_metal_species(gas_species_all, metal)
    metal_condensed_species = find_metal_species(condensed_species_all, metal)
    
    air_species_names = ['O2', 'N2', 'Ar']
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

def calc_mixture_enthalpy(mix):
    H_total = 0.0
    for i in range(mix.n_phases):
        phase_moles = mix.phase_moles(i)
        if phase_moles > 0:
            H_total += mix.phase(i).enthalpy_mole * phase_moles
    return H_total

def calculate_point(mech_path, condensed_species, phi):
    # Load phases
    gas = ct.Solution(mech_path, 'gas')
    condensed_phases = []
    for sp_name in condensed_species:
        phase_name = re.sub(r'[^a-zA-Z0-9_]', '_', sp_name)
        try:
            condensed_phases.append(ct.Solution(mech_path, phase_name))
        except: pass
        
    # Setup initial state
    metal_gas_name = METAL
    if metal_gas_name not in gas.species_names:
        # Fallback logic if pure Fe gas isn't found exactly as "Fe"
        pass 

    o2_moles = 1.0
    n2_moles = 3.76
    metal_moles = phi * (2.0/3.0) * o2_moles * 2 # Wait, let's double check stoichiometry.
    # Fe + 0.75 O2 -> 0.5 Fe2O3.  Stoich Ref: Usually defined relative to max oxidation state?
    # Or simpler: 4Fe + 3O2 -> 2Fe2O3.
    # Stoich user request usually implies valency.
    # For Fe, common oxides are FeO, Fe3O4, Fe2O3. Fe2O3 is most stable at ambient, but high T varies.
    # Let's use the definition: phi = (Fuel/Oxidizer) / (Fuel/Oxidizer)_stoich
    # Base reaction: 2 Fe + 1.5 O2 -> Fe2O3  => Fe/O2 ratio = 2/1.5 = 4/3 = 1.333
    # Wait, the server code has generic logic:
    # metal_moles = params.equivalence_ratio * o2_moles
    # That assumes 1:1 stoichiometry? That seems wrong for metals.
    # Ah, the server code lines 876-880:
    # metal_moles = params.equivalence_ratio * o2_moles
    # This implies the code assumes a 1:1 reaction stoichiometry basis for the "equivalence ratio" input?
    # Or maybe it expects the user to know?
    # Actually, standard definition: Phi = (m_fuel/m_ox) / (m_fuel/m_ox)_st.
    # The server implementation: metal_moles = phi * o2_moles
    # implies (n_fuel/n_ox)_st = 1. This is definitely wrong for Fe.
    # I should try to improve this or stick to the server's logic but correct it?
    # The PROMPT requested "Fe/air adiabatic flame temperature".
    # I will assume "stoichiometric" means formation of complete oxide Fe2O3.
    # 4 Fe + 3 O2 -> 2 Fe2O3.
    # (n_Fe / n_O2)_st = 4/3.
    # So if we have 1 mol O2, we need 4/3 mol Fe for phi=1.
    # So metal_moles = phi * (4/3) * o2_moles.
    
    # Let's fix this in my script to be chemically correct for Fe -> Fe2O3.
    stoich_ratio = 4.0/3.0 
    metal_moles = phi * stoich_ratio * o2_moles
    
    gas.TPX = T_INITIAL, P, f"{METAL}:{metal_moles}, O2:{o2_moles}, N2:{n2_moles}"
    initial_H = gas.enthalpy_mass * (metal_moles * gas.molecular_weights[gas.species_index(METAL)]/1000.0 + \
                                     o2_moles * 32.0/1000.0 + n2_moles * 28.0/1000.0) 
    # Wait, enthalpy_mass is J/kg.
    # Better to work with Mixture directly for initial H.
    
    # Initial Mixture
    for cp in condensed_phases: cp.TP = T_INITIAL, P
    # All Fe is in gas phase initially? Or solid?
    # At 298K, Fe is solid.
    # Result depends heavily on this.
    # The server code puts metal in "gas" phase for initial state! 
    # "if metal_gas_name not in gas.species_names: ... return Error"
    # This assumes we start with GAS PHASE METAL? That's physically wrong for 298K combustion.
    # It must be calculating latent heat of vaporization implicitly? No, that would require negative enthalpy of formation used?
    # NO. Fe(ref) is solid. Fe(g) has Hf > 0.
    # If we put Fe(g) at 298K, we are adding huge extra energy (latent heat of sublimation).
    # We MUST put Fe in the condensed phase initially if we want accurate "Iron burning in air" results.
    
    # CORRECT APPROACH:
    # Initial state: Fe(s) (from condensed phases) + Air (gas).
    # gas: O2, N2.
    # solid: Fe(cr) (or similar name).
    
    pass

# --- Main Logic ---

def main():
    try:
        mech_path, gas_species, condensed_species = build_metal_combustion_mechanism(METAL)
        print(f"Mechanism built at {mech_path}")
        
        # Load phases
        gas_phase = ct.Solution(mech_path, 'gas')
        condensed_phases = []
        fe_solid_phase = None
        
        for sp_name in condensed_species:
            phase_name = re.sub(r'[^a-zA-Z0-9_]', '_', sp_name)
            try:
                p = ct.Solution(mech_path, phase_name)
                condensed_phases.append(p)
                if sp_name == "Fe(cr)" or sp_name == "Fe(s)" or sp_name == "Fe": # Check names
                     fe_solid_phase = p
            except: pass
            
        print(f"Loaded {len(condensed_phases)} condensed phases.")
        print("Condensed phase names:", [p.name for p in condensed_phases])
        
        # Identify Iron solid phase for initial reactants
        # From nasas_condensed.yaml, Fe is likely "Fe(cr)" or similar.
        # Let's search for it.
        fe_reactant_phase = None
        for p in condensed_phases:
            # Fe_a_ is the sanitized name for Fe(a)
            if p.name == "Fe_a_":
                fe_reactant_phase = p
                break
        
        if not fe_reactant_phase:
             # Fallback
             for p in condensed_phases: 
                if p.name.startswith("Fe_") and "O" not in p.name and "S" not in p.name:
                     # This avoids FeO, FeS, but matches Fe_c_, Fe_d_, Fe_L_
                    fe_reactant_phase = p
                    break
        
        results_T = []
        results_phi = []
        results_prod_gas = {} # species -> list of fractions
        results_prod_cond = {} # species -> list of moles
        
        for phi in PHI_RANGE:
            # 1. Define Initial State
            stoich_ratio = 4.0/3.0 # Fe + 0.75 O2 -> 0.5 Fe2O3 => 1 Fe : 0.75 O2 => 1.333 Fe : 1 O2
            n_o2 = 1.0
            n_n2 = 3.76
            n_fe = phi * stoich_ratio * n_o2
            
            # Reset phases
            gas_phase.TPX = T_INITIAL, P, f"O2:{n_o2}, N2:{n_n2}"
            for cp in condensed_phases: cp.TP = T_INITIAL, P
            
            # Initial Mixture
            # Air in gas phase, Fe in solid phase
            phase_data = [(gas_phase, n_o2 + n_n2)] # Gas moles
            
            if fe_reactant_phase:
                phase_data.append((fe_reactant_phase, n_fe)) # Add solid Fe
                # Add other condensed phases with 0 moles
                for cp in condensed_phases:
                    if cp != fe_reactant_phase:
                        phase_data.append((cp, 0.0))
            else:
                 # Fallback: use gas phase Fe (incorrect but robustness check)
                 print("Warning: Fe(solid) not found, using gas phase Fe if available")
                 gas_phase.TPX = T_INITIAL, P, f"Fe:{n_fe}, O2:{n_o2}, N2:{n_n2}"
                 phase_data = [(gas_phase, n_fe + n_o2 + n_n2)] + [(cp, 0.0) for cp in condensed_phases]

            mix = ct.Mixture(phase_data)
            
            # Get H_initial
            H_target = calc_mixture_enthalpy(mix)
            
            # 2. Equilibration Loop (Adiabatic)
            # Use bisection on T, since 'HP' solver in Mixture can be flaky with phase appearance/disappearance
            t_min = 300.0
            t_max = 4000.0
            
            final_T = t_min
            best_diff = 1e9
            
            # Bisection
            for i in range(50):
                t_guess = 0.5 * (t_min + t_max)
                
                # Update T of all underlying phases
                # Note: Mix.equilibrate('TP') handles phase distribution.
                # But we need to update our guess? No, equilibrate does it.
                # However, for manual enthalpy matching we loop 'TP' steps.
                
                # We need to re-initialize the composition distribution? 
                # No, equilibrate(TP) finds the lowest G state at that T.
                # It redistributes atoms among phases.
                # We just need to make sure the ATOM AMOUNTS are preserved.
                # ct.Mixture preserves elements.
                
                # Set T guess
                mix.T = t_guess
                mix.P = P
                
                try:
                    mix.equilibrate('TP', max_steps=5000)
                    h_curr = calc_mixture_enthalpy(mix)
                    diff = h_curr - H_target
                    
                    if abs(diff) < best_diff:
                        best_diff = abs(diff)
                        final_T = t_guess
                    
                    if abs(diff) < 1.0: # Good enough
                        break
                        
                    if diff > 0: # Too hot
                        t_max = t_guess
                    else: # Too cold
                        t_min = t_guess
                except Exception as e:
                    # If equilibration fails, usually means crazy T step. Shrink range?
                    # Keep safe
                    pass
            
            # Store results
            results_phi.append(phi)
            results_T.append(final_T)
            
            # Product Composition (Gas)
            gas_p = mix.phase(0)
            # Get major species (> 1%)
            for k in range(gas_p.n_species):
                name = gas_p.species_name(k)
                x = gas_p.X[k]
                if name not in results_prod_gas: results_prod_gas[name] = np.zeros(len(PHI_RANGE))
                results_prod_gas[name][len(results_phi)-1] = x
                
            # Product Composition (Condensed)
            for i in range(1, mix.n_phases):
                p = mix.phase(i)
                moles = mix.phase_moles(i)
                if moles > 1e-10:
                    name = p.name  # Phase name, e.g. Fe3O4(s)
                    if name not in results_prod_cond: results_prod_cond[name] = np.zeros(len(PHI_RANGE))
                    results_prod_cond[name][len(results_phi)-1] = moles

        # --- Plotting ---
        plt.figure(figsize=(10, 6))
        plt.plot(results_phi, results_T, 'r-', linewidth=2)
        plt.xlabel('Equivalence Ratio (ϕ)')
        plt.ylabel('Adiabatic Flame Temperature (K)')
        plt.title('Fe-Air Adiabatic Flame Temperature vs Equivalence Ratio')
        plt.grid(True)
        plt.savefig('fe_air_flame_temp.png')
        
        plt.figure(figsize=(10, 6))
        # Plot Gas Majors
        for params_name, vals in results_prod_gas.items():
            if np.max(vals) > 0.01:
                plt.plot(results_phi, vals, label=f"{params_name}(g)")
        
        # Plot Condensed (Normalized? Just moles?)
        # Let's plot moles per mole of O2 input (which is 1.0)
        for params_name, vals in results_prod_cond.items():
            if np.max(vals) > 1e-3:
                plt.plot(results_phi, vals, '--', label=f"{params_name}")
                
        plt.xlabel('Equivalence Ratio (ϕ)')
        plt.ylabel('Molar Amount / Mole Fraction')
        plt.title('Product Composition vs Equivalence Ratio')
        plt.legend()
        plt.grid(True)
        plt.savefig('fe_air_composition.png')
        
        print("Done. Saved fe_air_flame_temp.png and fe_air_composition.png")

    finally:
        if 'mech_path' in locals():
            os.remove(mech_path)

if __name__ == "__main__":
    main()
