from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.experiment.catalog import get_condition_catalog, save_condition_settings


class ConditionSettings(BaseModel):
    entry_path: str
    persona: str
    rag_enabled: bool


class SettingsUpdate(BaseModel):
    shared_rules: str = ""
    shared_rules_without_rag: str = ""
    conditions: list[ConditionSettings]


def create_settings_router() -> APIRouter:
    router = APIRouter(prefix="/api/v1/settings")

    @router.get("/conditions")
    def read_conditions() -> dict[str, Any]:
        return _public_settings()

    @router.put("/conditions")
    def write_conditions(payload: SettingsUpdate) -> dict[str, Any]:
        try:
            save_condition_settings(payload.model_dump())
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(error),
            ) from error
        return _public_settings()

    return router


def _public_settings() -> dict[str, Any]:
    catalog = get_condition_catalog()
    first = catalog.conditions[0]
    return {
        "shared_rules": first.shared_rules,
        "shared_rules_without_rag": first.shared_rules_no_rag,
        "conditions": [
            {
                "entry_path": condition.entry_path,
                "condition_id": condition.condition_id,
                "competence": condition.competence,
                "warmth": condition.warmth,
                "rag_enabled": condition.rag_enabled,
                "temperature": condition.temperature,
                "max_tokens": condition.max_tokens,
                "persona": condition.persona,
            }
            for condition in catalog.conditions
        ],
    }
