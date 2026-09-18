"""JSON schemas and definitions for LLM directive generation."""

from typing import Any, Dict, List
from gridwise.app.models import DirectiveInterpretation, OptimizeEnergyResponse

LLM_DIRECTIVE_JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "directives": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "note_index": {"type": "integer", "minimum": 0},
                    "applies": {"type": "boolean"},
                    "directive_type": {
                        "type": "string",
                        "enum": [
                            "solar_reduction",
                            "minimum_battery_reserve",
                            "no_charge_window",
                            "no_discharge_window",
                            "max_grid_window",
                            "no_op"
                        ]
                    },
                    "structured_adjustment": {
                        "type": ["object", "null"],
                        "properties": {
                            "hours": {
                                "type": "array",
                                "items": {"type": "integer", "minimum": 0, "maximum": 23}
                            },
                            "factor": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                            "minimum_energy_kwh": {"type": "number", "minimum": 0.0},
                            "max_grid_kwh": {"type": "number", "minimum": 0.0}
                        }
                    }
                },
                "required": ["note_index", "applies", "directive_type", "structured_adjustment"]
            }
        }
    },
    "required": ["directives"]
}
