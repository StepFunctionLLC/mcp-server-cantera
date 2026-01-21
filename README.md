# mcp-server-cantera

An MCP server wrapped around Cantera to facilitate use by an LLM for accurate equilibrium and kinetics calculations.

## Overview

This MCP (Model Context Protocol) server provides an interface to Cantera, a powerful open-source software suite for problems involving chemical kinetics, thermodynamics, and transport processes. The server enables LLMs to perform accurate chemical equilibrium calculations and kinetics simulations through a standardized API.

## Features

- **Gas Properties**: Get thermodynamic properties of gas mixtures at specified conditions
- **Equilibrium Calculations**: Calculate equilibrium compositions for various thermodynamic bases (TP, HP, SP, UV)
- **Cantera Integration**: Full access to Cantera's extensive mechanism library
- **LLM-Friendly**: Designed to work seamlessly with language models through the MCP protocol

## Installation

### From Source

```bash
# Clone the repository
git clone https://github.com/davetew/mcp-server-cantera.git
cd mcp-server-cantera

# Install the package
pip install -e .
```

### With Development Dependencies

```bash
pip install -e ".[dev]"
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

### Available Tools

#### 1. get_gas_properties

Get thermodynamic properties of a gas mixture at specified conditions.

**Parameters:**
- `mechanism`: Cantera mechanism file or name (e.g., 'gri30.yaml')
- `temperature`: Temperature in Kelvin
- `pressure`: Pressure in Pascals
- `composition`: Gas composition in Cantera format (e.g., 'CH4:1, O2:2, N2:7.52')

#### 2. equilibrate_gas

Calculate equilibrium composition of a gas mixture.

**Parameters:**
- `mechanism`: Cantera mechanism file or name
- `temperature`: Temperature in Kelvin
- `pressure`: Pressure in Pascals
- `composition`: Initial gas composition in Cantera format
- `basis`: Equilibration basis - 'TP', 'HP', 'SP', or 'UV' (default: 'TP')

### Example Usage with MCP Client

```python
# Example: Get properties of a methane-air mixture
{
    "tool": "get_gas_properties",
    "arguments": {
        "mechanism": "gri30.yaml",
        "temperature": 300,
        "pressure": 101325,
        "composition": "CH4:1, O2:2, N2:7.52"
    }
}

# Example: Calculate equilibrium composition
{
    "tool": "equilibrate_gas",
    "arguments": {
        "mechanism": "gri30.yaml",
        "temperature": 1500,
        "pressure": 101325,
        "composition": "CH4:1, O2:2, N2:7.52",
        "basis": "TP"
    }
}
```

## Development

### Running Tests

```bash
pytest
```

### Code Formatting

```bash
black src/
```

### Linting

```bash
ruff check src/
```

### Type Checking

```bash
mypy src/
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## About Cantera

Cantera is an open-source suite of tools for problems involving chemical kinetics, thermodynamics, and transport processes. For more information, visit [cantera.org](https://cantera.org/).

## Acknowledgments

This MCP server is built on top of:
- [Cantera](https://cantera.org/) - Chemical kinetics and thermodynamics library
- [MCP](https://modelcontextprotocol.io/) - Model Context Protocol for LLM integration
