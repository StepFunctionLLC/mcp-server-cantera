<!-- Copyright Step Function, 2026 -->
# Example 1: Thermodynamic and Transport Properties

This example demonstrates how to use the Cantera MCP Server to retrieve comprehensive thermodynamic and transport properties for a gas mixture.

---

## Scenario

We want to obtain the thermodynamic and transport properties of **air at 50°C (323.15 K) and ambient pressure (101325 Pa)**.

---

## Step 1: Create a Mixture on the Lab Bench

**User Prompt:**
> Create an air mixture at 50°C and ambient pressure so I can analyze its properties.

**Server Response:**

```
Created mixture 'air_50C' on lab bench:

=== State ===
Mechanism:   gri30.yaml
Temperature: 323.15 K
Pressure:    101325.00 Pa (1.0132 bar)
Density:     1.092513 kg/m³

=== Composition (mole fractions > 0.1%) ===
  O2: 21.0000%
  N2: 78.0000%
  AR: 1.0000%

=== Kinetics ===
Number of species:   53
Number of reactions: 325
```

---

## Step 2: Get Full Thermodynamic and Transport Properties

**User Prompt:**
> What are the thermodynamic and transport properties of this air mixture?

**Server Response:**

```
Mixture Properties for 'air_50C':

=== Thermodynamic State ===
Temperature:           323.15 K
Pressure:              101325.00 Pa (1.0132 bar)
Density:               1.092513 kg/m³
Mean molecular weight: 28.9700 g/mol

=== Thermodynamic Properties ===
Specific enthalpy (mass):  25.1428 kJ/kg
Specific entropy (mass):   6.940613 kJ/(kg·K)
Specific Cp (mass):        1005.5216 J/(kg·K)
Specific Cv (mass):        718.5190 J/(kg·K)
Heat capacity ratio γ:     1.399436
Internal energy (mass):    -67.6020 kJ/kg
Gibbs free energy (mass):  -2217.7162 kJ/kg

=== Transport Properties ===
Dynamic viscosity:         1.976593e-05 Pa·s
Thermal conductivity:      0.027885 W/(m·K)
Prandtl number:            0.7128
Speed of sound (ideal):    360.26 m/s

=== Mole Fractions ===
  O2: 2.100000e-01
  N2: 7.800000e-01
  AR: 1.000000e-02
```

---

## Summary

| Property | Value | Units |
|----------|-------|-------|
| Temperature | 323.15 | K |
| Pressure | 101325 | Pa |
| Density | 1.0925 | kg/m³ |
| Mean MW | 28.97 | g/mol |
| Specific Cp | 1005.5 | J/(kg·K) |
| Specific Cv | 718.5 | J/(kg·K) |
| γ (Cp/Cv) | 1.399 | - |
| Specific Enthalpy | 25.14 | kJ/kg |
| Specific Entropy | 6.941 | kJ/(kg·K) |
| Dynamic Viscosity | 1.977×10⁻⁵ | Pa·s |
| Thermal Conductivity | 0.0279 | W/(m·K) |
| Prandtl Number | 0.713 | - |
| Speed of Sound | 360.3 | m/s |

---

## Tools Used

1. **`create_lab_mixture`** - Creates a named mixture on the lab bench with specified composition, temperature, and pressure
2. **`get_mixture_properties`** - Retrieves comprehensive thermodynamic and transport properties for a stored mixture

---

## Notes

- The GRI-Mech 3.0 mechanism (`gri30.yaml`) is used by default, which provides accurate transport properties
- Air is modeled as O₂ (21%), N₂ (78%), and Ar (1%) by mole fraction
- Properties are based on NIST-standard thermodynamic data
- The Prandtl number (~0.71) is characteristic of air and confirms accurate transport property calculations
