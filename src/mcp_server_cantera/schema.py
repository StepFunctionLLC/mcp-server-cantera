# Copyright Step Function, 2026
from typing import Literal
from pydantic import BaseModel, Field, field_validator

class LabBenchMeasurementInput(BaseModel):
    """Input model for measuring properties of a lab bench mixture."""
    
    name: str = Field(
        ...,
        description="The ID of the mixture on the lab bench",
        examples=["flame_1", "reactor"],
    )


class LabBenchEquilibriumInput(BaseModel):
    """Input model for equilibrating a lab bench mixture."""
    
    name: str = Field(
        ...,
        description="The ID of the mixture on the lab bench",
        examples=["flame_1", "reactor"],
    )
    basis: Literal["TP", "HP", "SP", "UV"] = Field(
        default="TP",
        description="Equilibration basis: 'TP' (constant T,P), 'HP' (adiabatic, constant P), 'SP' (isentropic), 'UV' (constant U,V)",
    )


class CombustionInput(BaseModel):
    """Input model for combustion calculations."""
    
    mechanism: str = Field(
        ...,
        description="Cantera mechanism file (e.g., 'gri30.yaml' for methane combustion)",
        examples=["gri30.yaml", "JetSurf2.yaml"],
    )
    fuel: str = Field(
        ...,
        description="Fuel composition (e.g., 'CH4:1' or 'H2:1' or 'CH4:0.9, C2H6:0.1')",
        examples=["CH4:1", "H2:1", "NC12H26:1"],
    )
    oxidizer: str = Field(
        ...,
        description="Oxidizer composition (e.g., 'O2:1, N2:3.76' for air)",
        examples=["O2:1, N2:3.76", "O2:1"],
    )
    equivalence_ratio: float = Field(
        ...,
        gt=0,
        le=10,
        description="Equivalence ratio (phi). phi=1 is stoichiometric, phi<1 is lean, phi>1 is rich",
        examples=[1.0, 0.8, 1.2],
    )
    initial_temperature: float = Field(
        ...,
        gt=0,
        description="Initial temperature in Kelvin (typically 298.15 K)",
        examples=[298.15, 300.0, 400.0],
    )
    pressure: float = Field(
        ...,
        gt=0,
        description="Pressure in Pascals",
        examples=[101325.0, 500000.0],
    )
    
    @field_validator("fuel", "oxidizer")
    @classmethod
    def validate_composition(cls, v: str) -> str:
        """Validate composition string format."""
        if not v or not v.strip():
            raise ValueError("Composition cannot be empty")
        if ":" not in v:
            raise ValueError("Composition must be in format 'Species:amount'")
        return v.strip()


class SpeciesInput(BaseModel):
    """Input model for species property lookup."""
    
    mechanism: str = Field(
        ...,
        description="Cantera mechanism file or mechanism name",
        examples=["gri30.yaml", "air.yaml"],
    )
    species_name: str = Field(
        ...,
        description="Name of the species (e.g., 'CH4', 'O2', 'H2O')",
        examples=["CH4", "O2", "H2O", "CO2"],
    )
    temperature: float = Field(
        ...,
        gt=0,
        description="Temperature in Kelvin for property evaluation",
        examples=[298.15, 500.0, 1000.0],
    )


class MechanismInput(BaseModel):
    """Input model for mechanism queries."""
    
    mechanism: str = Field(
        ...,
        description="Cantera mechanism file or mechanism name",
        examples=["gri30.yaml", "air.yaml", "JetSurf2.yaml"],
    )


class MetalCombustionInput(BaseModel):
    """Input model for metal-oxygen/air combustion equilibrium calculations."""
    
    metal: str = Field(
        ...,
        description="Metal element symbol (e.g., 'Fe', 'Al', 'Mg', 'Ti', 'Zn')",
        examples=["Fe", "Al", "Mg", "Ti", "Zn", "Cu"],
    )
    oxidizer: Literal["O2", "air"] = Field(
        default="air",
        description="Oxidizer type: 'O2' for pure oxygen or 'air' for N2:3.76, O2:1 mixture",
    )
    equivalence_ratio: float = Field(
        default=1.0,
        gt=0,
        le=10,
        description="Equivalence ratio (phi). phi=1 is stoichiometric, phi<1 is lean (excess oxidizer), phi>1 is rich (excess metal)",
    )
    initial_temperature: float = Field(
        default=298.15,
        gt=0,
        description="Initial temperature in Kelvin",
        examples=[298.15, 500.0, 1000.0],
    )
    pressure: float = Field(
        default=101325.0,
        gt=0,
        description="Pressure in Pascals",
        examples=[101325.0, 500000.0],
    )


class LabBenchMixtureInput(BaseModel):
    """Input model for creating a named mixture on the lab bench."""
    
    name: str = Field(
        ...,
        description="Unique identifier for this mixture on the lab bench (e.g., 'combustor_1', 'test_mixture')",
        examples=["flame_1", "reactor_inlet", "exhaust_gas"],
    )
    mechanism: str = Field(
        ...,
        description="Cantera mechanism file (e.g., 'gri30.yaml' for natural gas combustion)",
        examples=["gri30.yaml", "h2o2.yaml", "JetSurf2.yaml"],
    )
    temperature: float = Field(
        ...,
        gt=0,
        description="Temperature in Kelvin",
        examples=[298.15, 1500.0, 2000.0],
    )
    pressure: float = Field(
        ...,
        gt=0,
        description="Pressure in Pascals",
        examples=[101325.0, 500000.0],
    )
    composition: str = Field(
        ...,
        description="Mixture composition in Cantera format (e.g., 'CH4:1, O2:2, N2:7.52')",
        examples=["CH4:1, O2:2, N2:7.52", "H2:2, O2:1, N2:3.76"],
    )


class ReactionRatesInput(BaseModel):
    """Input model for getting reaction rates from a lab bench mixture."""
    
    name: str = Field(
        ...,
        description="The ID of the mixture on the lab bench",
        examples=["flame_1", "reactor"],
    )
    threshold: float = Field(
        default=1e-6,
        description="Minimum net rate of progress (kmol/m³/s) to report. Use lower values (e.g., 1e-9) to see slow initiation steps.",
        examples=[1e-6, 1e-9, 1e-3],
    )


class SpeciesProductionInput(BaseModel):
    """Input model for species production/consumption pathway analysis."""
    
    name: str = Field(
        ...,
        description="The ID of the mixture on the lab bench",
        examples=["flame_1", "reactor"],
    )
    species: str = Field(
        ...,
        description="Species name to analyze (e.g., 'OH', 'NO', 'CO2')",
        examples=["OH", "NO", "CO2", "H2O"],
    )
    limit: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of top reactions to show for production and consumption",
    )


class BatchReactorInput(BaseModel):
    """Input model for batch reactor simulation."""
    
    name: str = Field(
        ...,
        description="The ID of the mixture on the lab bench",
        examples=["flame_1", "reactor"],
    )
    duration: float = Field(
        ...,
        gt=0,
        description="Integration time in seconds (e.g., 0.01 for 10ms)",
        examples=[0.001, 0.01, 0.1],
    )
    steps: int = Field(
        default=10,
        ge=2,
        le=100,
        description="Number of time-points to report in the output summary",
    )


class IgnitionDelayInput(BaseModel):
    """Input model for ignition delay calculation."""
    
    name: str = Field(
        ...,
        description="The ID of the mixture on the lab bench",
        examples=["flame_1", "reactor"],
    )
    max_time: float = Field(
        default=1.0,
        gt=0,
        description="Maximum time to simulate before giving up (seconds)",
        examples=[0.1, 1.0, 10.0],
    )


class SpeciesThermoInput(BaseModel):
    """Input model for species thermodynamic property lookup with database fallback."""
    
    species: str = Field(
        ...,
        description="Chemical formula or species name (e.g., 'CH4', 'CO2', 'He', 'Xe')",
        examples=["CH4", "CO2", "He", "Xe", "Fe"],
    )
    temperature_k: float = Field(
        ...,
        gt=0,
        description="Temperature in Kelvin",
        examples=[298.15, 500.0, 1000.0],
    )
    pressure_bar: float = Field(
        default=1.0,
        gt=0,
        description="Pressure in bar (default 1.0 bar = 1 atm)",
        examples=[1.0, 10.0, 50.0],
    )


class SpeciesAvailabilityInput(BaseModel):
    """Input model for checking species availability across databases."""
    
    species_list: list[str] = Field(
        ...,
        description="List of species names to check (e.g., ['CH4', 'He', 'Xe'])",
        examples=[["CH4", "O2", "He"], ["Fe", "Al", "Mg"]],
    )
