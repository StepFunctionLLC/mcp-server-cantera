# mcp-server-cantera

An MCP server wrapped around Cantera to facilitate use by an LLM for accurate equilibrium and kinetics calculations.

## Overview

This MCP (Model Context Protocol) server provides an interface to Cantera, a powerful open-source software suite for problems involving chemical kinetics, thermodynamics, and transport processes. The server enables LLMs to perform accurate, science-based calculations for combustion, equilibrium, and reaction pathway analysis.

## Features

- **Thermodynamic Properties**: Get comprehensive properties including enthalpy, entropy, heat capacities, and Gibbs energy
- **Transport Properties**: Calculate viscosity, thermal conductivity, diffusion coefficients, and Prandtl number
- **Equilibrium Calculations**: Calculate equilibrium compositions for various thermodynamic bases (TP, HP, SP, UV)
- **Combustion Analysis**: Compute adiabatic flame temperatures for fuel-oxidizer systems
- **Metal Combustion**: Multi-phase equilibrium for metal-air/oxygen combustion (Fe, Al, Mg, Ti, Zn, and more)
- **Kinetic Analysis**: Stateful "lab bench" for reaction rate and pathway analysis
- **Mechanism Support**: Built-in and custom mechanism file support with automatic resolution
- **LLM-Friendly**: Designed to work seamlessly with language models through the MCP protocol

## Installation

### Prerequisites

- Python 3.10 or higher
- [uv](https://docs.astral.sh/uv/) package manager

If you don't have uv installed, you can install it with:

```bash
# On macOS and Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# On Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### From Source

```bash
# Clone the repository
git clone https://github.com/davetew/mcp-server-cantera.git
cd mcp-server-cantera

# Install the package
uv pip install -e .
```

### With Development Dependencies

```bash
uv pip install -e ".[dev]"
```

## Requirements

- Python 3.10 or higher
- Cantera 3.0.0 or higher
- MCP 0.9.0 or higher

## Usage

### Running the Server

The server can be started using the command-line interface:

```bash
mcp-server-cantera
```

### Configuring Claude Desktop

To use this MCP server with Claude Desktop, you need to add it to your Claude configuration file:

#### macOS

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "cantera": {
      "command": "uv",
      "args": [
        "--directory",
        "/ABSOLUTE/PATH/TO/mcp-server-cantera",
        "run",
        "mcp-server-cantera"
      ]
    }
  }
}
```

#### Windows

Edit `%APPDATA%\Claude\claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "cantera": {
      "command": "uv",
      "args": [
        "--directory",
        "C:\\ABSOLUTE\\PATH\\TO\\mcp-server-cantera",
        "run",
        "mcp-server-cantera"
      ]
    }
  }
}
```

**Important:** Replace `/ABSOLUTE/PATH/TO/mcp-server-cantera` (or `C:\ABSOLUTE\PATH\TO\mcp-server-cantera` on Windows) with the actual absolute path to your cloned repository.

After updating the configuration file, restart Claude Desktop for the changes to take effect.

---

## Available Tools

### Thermodynamic & Transport Properties

#### `get_mix_properties`
Get comprehensive thermodynamic and transport properties of a gas mixture.

**Returns:** Temperature, pressure, density, enthalpy, entropy, Cp, Cv, γ, viscosity, thermal conductivity, speed of sound, and mole fractions.

#### `get_transport_properties`
Get detailed transport properties including viscosity, thermal conductivity, thermal diffusivity, Prandtl number, and species diffusion coefficients.

#### `get_species_properties`
Get detailed thermodynamic properties for a specific species from a mechanism file. Includes molecular weight, composition, Cp, Cv, enthalpy, entropy, and Gibbs energy.

---

### Equilibrium Calculations

#### `equilibrate`
Calculate equilibrium composition of a gas mixture.

**Bases:**
- `TP` — Constant temperature and pressure
- `HP` — Constant enthalpy and pressure (adiabatic)
- `SP` — Constant entropy and pressure (isentropic)
- `UV` — Constant internal energy and volume

**Returns:** Equilibrium state, thermodynamic changes (ΔH, ΔG), and equilibrium mole fractions.

---

### Combustion Analysis

#### `calculate_adiabatic_flame_temperature`
Calculate the adiabatic flame temperature for combustion of a fuel with an oxidizer.

**Parameters:**
- `mechanism` — Cantera mechanism file (e.g., `gri30.yaml`)
- `fuel` — Fuel composition (e.g., `CH4:1` or `H2:1`)
- `oxidizer` — Oxidizer composition (e.g., `O2:1, N2:3.76` for air)
- `equivalence_ratio` — φ=1 stoichiometric, φ<1 lean, φ>1 rich
- `initial_temperature` — Initial temperature in Kelvin
- `pressure` — Pressure in Pascals

#### `calculate_metal_combustion_equilibrium`
Calculate equilibrium temperature and products for metal-oxygen/air combustion using multi-phase equilibrium.

**Supported metals:** Fe, Al, Mg, Ti, Zn, Cu, Cr, Mn, Ni, Co, and more.

This tool dynamically builds a mechanism from NASA thermodynamic databases (`nasa_gas.yaml` and `nasa_condensed.yaml`) and performs multi-phase equilibrium to determine:
- Adiabatic flame temperature
- Gas phase equilibrium composition
- Condensed phase (solid/liquid oxide) products

**Parameters:**
- `metal` — Metal element symbol (e.g., `Fe`, `Al`, `Mg`)
- `oxidizer` — `O2` (pure oxygen) or `air`
- `equivalence_ratio` — Ratio of metal to stoichiometric (default: 1.0)
- `initial_temperature` — Initial temperature in Kelvin (default: 298.15)
- `pressure` — Pressure in Pascals (default: 101325)

---

### Lab Bench (Stateful Kinetic Analysis)

The "lab bench" provides stateful storage for mixtures, enabling multi-step kinetic and pathway analysis.

#### `create_lab_mixture`
Create a named mixture on the lab bench for subsequent analysis.

```json
{
  "name": "flame_1",
  "mechanism": "gri30.yaml",
  "temperature": 1500,
  "pressure": 101325,
  "composition": "CH4:0.05, O2:0.1, N2:0.85"
}
```

#### `list_lab_mixtures`
List all mixtures currently stored on the lab bench with their states.

#### `get_reaction_rates`
Get the fastest reactions occurring in a named mixture. Useful for understanding which reactions dominate under current conditions.

**Parameters:**
- `name` — Lab bench mixture identifier
- `threshold` — Minimum net rate of progress to report (kmol/m³/s)

#### `get_species_production_contributors`
Identify which reactions are creating or consuming a specific species. Critical for pathway analysis.

**Example questions:**
- "Where is the NO coming from?"
- "What reactions consume OH?"

**Parameters:**
- `name` — Lab bench mixture identifier
- `species` — Species to analyze (e.g., `OH`, `NO`, `CO2`)
- `limit` — Number of top reactions to show (default: 5)

---

### Reactor Network Tools

#### `run_batch_reactor`
Simulate a Constant Pressure (Ideal Gas) Batch Reactor over time. Use this to see how temperature and composition evolve during combustion or other chemical reactions.

**Parameters:**
- `name` — Lab bench mixture identifier
- `duration` — Integration time in seconds (e.g., 0.01 for 10ms)
- `steps` — Number of time-points to report (default: 10)

**Note:** The mixture state on the lab bench is updated to the final reacted state after simulation.

#### `compute_ignition_delay`
Calculate the auto-ignition delay time of the mixture. Defined as the time point where the temperature rise is steepest (dT/dt is max). This is commonly used for characterizing fuel reactivity and validating chemical kinetic mechanisms.

**Parameters:**
- `name` — Lab bench mixture identifier
- `max_time` — Maximum simulation time before giving up (default: 1.0 seconds)

**Note:** This tool does NOT update the lab bench mixture state to preserve the original mixture for other tests.

---

### Mechanism Management

#### `list_available_mechanisms`
List all available Cantera mechanism files, including both built-in and custom mechanisms.

**Built-in mechanisms:**
- `gri30.yaml` — GRI-Mech 3.0 for natural gas combustion (53 species, 325 reactions)
- `h2o2.yaml` — Hydrogen-oxygen combustion (9 species, 28 reactions)
- `air.yaml` — Simple air model (N2, O2, Ar)
- `nasa_gas.yaml` — NASA thermodynamic database for gases
- `liquidvapor.yaml` — Pure substance liquid-vapor equilibrium

**Custom mechanisms:** Place YAML mechanism files in the `mechanisms/` folder at the repository root for automatic discovery.

#### `list_species_in_mechanism`
List all species defined in a mechanism file, organized by primary element.

---

## Example Use Cases

### 1. Hydrogen-Air Combustion Analysis

Calculate the adiabatic flame temperature for stoichiometric hydrogen combustion in air:

```json
{
  "tool": "calculate_adiabatic_flame_temperature",
  "arguments": {
    "mechanism": "h2o2.yaml",
    "fuel": "H2:1",
    "oxidizer": "O2:1, N2:3.76",
    "equivalence_ratio": 1.0,
    "initial_temperature": 298.15,
    "pressure": 101325
  }
}
```

### 2. Iron-Air Combustion (Metal Fuel)

Calculate the adiabatic flame temperature for stoichiometric iron combustion in air, including solid oxide products:

```json
{
  "tool": "calculate_metal_combustion_equilibrium",
  "arguments": {
    "metal": "Fe",
    "oxidizer": "air",
    "equivalence_ratio": 1.0,
    "initial_temperature": 298.15,
    "pressure": 101325
  }
}
```

This returns:
- Adiabatic flame temperature (~1800-2000 K for Fe/air)
- Gas phase products (N2, excess O2, trace oxides)
- Condensed phase products (Fe2O3, Fe3O4, FeO)

### 3. Aluminum-Oxygen Combustion

High-energy aluminum combustion in pure oxygen:

```json
{
  "tool": "calculate_metal_combustion_equilibrium",
  "arguments": {
    "metal": "Al",
    "oxidizer": "O2",
    "equivalence_ratio": 1.0
  }
}
```

### 4. Methane-Air Properties and Equilibrium

Get transport properties of a methane-air mixture:

```json
{
  "tool": "get_transport_properties",
  "arguments": {
    "mechanism": "gri30.yaml",
    "temperature": 500,
    "pressure": 101325,
    "composition": "CH4:1, O2:2, N2:7.52"
  }
}
```

### 5. Reaction Pathway Analysis

Analyze NO formation in a combustion mixture:

```python
# Step 1: Create mixture on lab bench
{
  "tool": "create_lab_mixture",
  "arguments": {
    "name": "combustor",
    "mechanism": "gri30.yaml",
    "temperature": 1800,
    "pressure": 101325,
    "composition": "CH4:0.05, O2:0.1, N2:0.85"
  }
}

# Step 2: Analyze NO production pathways
{
  "tool": "get_species_production_contributors",
  "arguments": {
    "name": "combustor",
    "species": "NO",
    "limit": 5
  }
}
```

### 6. Equilibrium at Different Conditions

Calculate equilibrium at constant enthalpy and pressure (adiabatic):

```json
{
  "tool": "equilibrate",
  "arguments": {
    "mechanism": "gri30.yaml",
    "temperature": 1500,
    "pressure": 101325,
    "composition": "CH4:1, O2:2, N2:7.52",
    "basis": "HP"
  }
}
```

### 7. Batch Reactor Simulation

Simulate how a fuel-air mixture evolves over time in a batch reactor:

```python
# Step 1: Create mixture on lab bench
{
  "tool": "create_lab_mixture",
  "arguments": {
    "name": "reactor",
    "mechanism": "gri30.yaml",
    "temperature": 1200,
    "pressure": 101325,
    "composition": "CH4:1, O2:2, N2:7.52"
  }
}

# Step 2: Run batch reactor simulation
{
  "tool": "run_batch_reactor",
  "arguments": {
    "name": "reactor",
    "duration": 0.001,
    "steps": 10
  }
}
```

### 8. Ignition Delay Calculation

Calculate the auto-ignition delay time — critical for engine knock and safety analysis:

```python
# Step 1: Create stoichiometric H2/air mixture at elevated temperature
{
  "tool": "create_lab_mixture",
  "arguments": {
    "name": "ignition_test",
    "mechanism": "h2o2.yaml",
    "temperature": 1000,
    "pressure": 101325,
    "composition": "H2:2, O2:1, N2:3.76"
  }
}

# Step 2: Compute ignition delay
{
  "tool": "compute_ignition_delay",
  "arguments": {
    "name": "ignition_test",
    "max_time": 0.1
  }
}
```

---

## Custom Mechanisms

To use custom mechanism files:

1. Place YAML mechanism files in the `mechanisms/` folder at the repository root
2. Reference them by filename in any tool (e.g., `"mechanism": "JetSurf2.yaml"`)
3. The server automatically resolves the full path

The `mechanisms/` folder should contain:
- `nasa_gas.yaml` — Required for metal combustion (gas phase species)
- `nasa_condensed.yaml` — Required for metal combustion (solid/liquid species)
- Any additional custom mechanisms

---

## Development

### Running Tests

```bash
uv run pytest
```

### Code Formatting

```bash
uv run black src/
```

### Linting

```bash
uv run ruff check src/
```

### Type Checking

```bash
uv run mypy src/
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## About Cantera

Cantera is an open-source suite of tools for problems involving chemical kinetics, thermodynamics, and transport processes. For more information, visit [cantera.org](https://cantera.org/).

## Acknowledgments

This MCP server is built on top of:
- [Cantera](https://cantera.org/) — Chemical kinetics and thermodynamics library
- [MCP](https://modelcontextprotocol.io/) — Model Context Protocol for LLM integration
- [FastMCP](https://github.com/jlowin/fastmcp) — Clean, decorator-based MCP server framework
- NASA Thermodynamic Databases — For metal combustion species data
