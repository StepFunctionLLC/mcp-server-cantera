# mcp-server-cantera Copilot Instructions

This repository implements a Model Context Protocol (MCP) server integration for Cantera, enabling LLMs to perform chemical kinetics and thermodynamic calculations.

## Architecture & Code Structure

- **Core Logic**: The entire server implementation resides in `src/mcp_server_cantera/server.py`.
- **Framework**: Uses FastMCP for clean, decorator-based tool definitions with Pydantic validation.
- **Mechanism Discovery**: The `mechanisms/` directory at the project root stores custom `.yaml` mechanism files.
  - The server dynamically locates this folder via `get_custom_mechanisms_dir()`.
  - `resolve_mechanism()` handles the logic to prefer custom mechanisms over built-ins.
- **Package Layout**: Standard `src/` layout with `pyproject.toml` configuration.

## Key Developer Workflows

### Environment & Installation
- **Package Manager**: Uses `uv` for fast dependency resolution.
- **Installation**: `uv pip install -e .` (Editable install is CRITICAL for mechanism discovery to work).
- **Python Version**: Requires Python 3.10+.

### Running the Server
```bash
# Run via CLI entry point
mcp-server-cantera

# Or via uv directly
uv run mcp-server-cantera
```

### Testing
- **Framework**: `pytest`
- **Location**: `tests/`
- Run tests: `uv run pytest`

## Coding Conventions

### Cantera Usage Support
- **Mechanism Loading**: Always use `resolve_mechanism(mech_name)` before passing to `ct.Solution()`.
- **State Setting**: Prefer `gas.TPX = T, P, X` or `gas.TP = T, P` for setting states.
- **Units**: 
  - Temperature: Kelvin
  - Pressure: Pascals (Code may output bar for readability, but inputs/internal are Pa)
  - Energy: J or kJ (be explicit in output strings)

### Pydantic Models for Tool Inputs
All tool inputs use Pydantic models for validation. Key models defined in `server.py`:
- `GasStateInput`: mechanism, temperature, pressure, composition
- `EquilibriumInput`: extends GasStateInput with equilibrium basis
- `CombustionInput`: fuel/oxidizer combustion setup
- `SpeciesInput`: species property lookup
- `MechanismInput`: single mechanism parameter

When adding new tools:
1. **Define a Pydantic model** with `Field()` for validation, descriptions, and examples
2. **Use validators** like `@field_validator` for custom validation (e.g., composition format)
3. **Constrain values** with `gt=0`, `le=10`, `Literal[...]` for enums

Example Pydantic model:
```python
class MyToolInput(BaseModel):
    temperature: float = Field(
        ...,
        gt=0,
        description="Temperature in Kelvin",
        examples=[298.15, 500.0],
    )
    basis: Literal["TP", "HP"] = Field(
        default="TP",
        description="Calculation basis",
    )
    
    @field_validator("composition")
    @classmethod
    def validate_composition(cls, v: str) -> str:
        if ":" not in v:
            raise ValueError("Must be in format 'Species:amount'")
        return v.strip()
```

### FastMCP Tool Implementation Patterns
When adding new tools:
1. **Create Pydantic model**: Define input validation model with Field descriptors
2. **Decorate**: Use `@mcp.tool()` decorator on a function
3. **Accept model**: Function takes single `params: MyModel` argument
4. **Return**: Return a `str` directly (FastMCP handles wrapping)

Example pattern:
```python
@mcp.tool()
def my_tool(params: MyToolInput) -> str:
    """Tool description for LLM."""
    mechanism = resolve_mechanism(params.mechanism)
    gas = ct.Solution(mechanism)
    gas.TPX = params.temperature, params.pressure, params.composition
    # ... calculation ...
    return "result string"
```

### Error Handling
- Pydantic validates inputs before tool execution—invalid inputs return clear error messages
- FastMCP handles exceptions automatically—they're returned as error responses
- Use `logger` for internal server logging

## Important Dependencies
- `cantera`: The physics engine (>=3.0.0)
- `fastmcp`: The MCP framework (>=2.0.0)
- `pydantic`: Input validation and schema generation (>=2.0.0)

## Important Dependencies
- `cantera`: The physics engine (>=3.0.0).
- `fastmcp`: The MCP framework (>=2.0.0).
