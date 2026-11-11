from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.experiment.catalog import get_condition_catalog

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def create_ui_router(*, app_name: str, school_email_domain: str) -> APIRouter:
    router = APIRouter()

    @router.get("/setting", response_class=HTMLResponse)
    def settings_page(request: Request) -> HTMLResponse:
        catalog = get_condition_catalog()
        first = catalog.conditions[0]
        return templates.TemplateResponse(
            request,
            "settings.html",
            {
                "app_name": app_name,
                "shared_rules": first.shared_rules,
                "shared_rules_without_rag": first.shared_rules_no_rag,
                "conditions": catalog.conditions,
            },
            headers={"Cache-Control": "no-store"},
        )

    @router.get("/", response_class=HTMLResponse)
    def chat_page(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "chat.html",
            {
                "app_name": app_name,
                "school_email_domain": school_email_domain,
            },
        )

    def _page(entry_path: str):
        def experiment_page(request: Request) -> HTMLResponse:
            condition = get_condition_catalog().get(entry_path)
            if condition is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
            return templates.TemplateResponse(
                request,
                "session_chat.html",
                {
                    "app_name": app_name,
                    "school_email_domain": school_email_domain,
                    "entry_path": condition.entry_path,
                    "opening_message": condition.opening_message,
                },
                headers={"Cache-Control": "no-store"},
            )

        experiment_page.__name__ = f"session_chat_{entry_path}"
        return experiment_page

    for condition in get_condition_catalog().conditions:
        router.add_api_route(
            f"/{condition.entry_path}",
            _page(condition.entry_path),
            methods=["GET"],
            response_class=HTMLResponse,
            include_in_schema=False,
        )

    return router
