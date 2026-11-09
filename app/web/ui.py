from pathlib import Path
from urllib.parse import parse_qs

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.experiment.catalog import REQUIRED_ENTRY_PATHS, get_condition_catalog
from app.experiment.overrides import (
    PromptOverrideError,
    effective_system_prompt,
    reset_override,
    save_override,
)
from app.experiment.switches import is_path_enabled, set_path_enabled

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def create_ui_router(*, app_name: str, school_email_domain: str) -> APIRouter:
    router = APIRouter()

    @router.get("/prompts", response_class=HTMLResponse, include_in_schema=False)
    @router.get("/prompts/", response_class=HTMLResponse, include_in_schema=False)
    def prompt_editor(request: Request) -> HTMLResponse:
        return _render_prompt_editor(request, app_name=app_name)

    @router.post("/prompts/{entry_path}/enabled", include_in_schema=False, response_model=None)
    async def set_prompt_enabled(
        entry_path: str,
        request: Request,
    ) -> JSONResponse | RedirectResponse:
        if entry_path not in REQUIRED_ENTRY_PATHS:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
        enabled = await _enabled_from_request(request)
        set_path_enabled(entry_path, enabled)
        if _wants_json(request):
            return JSONResponse({"entry_path": entry_path, "enabled": enabled})
        return RedirectResponse("/prompts", status_code=status.HTTP_303_SEE_OTHER)

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
            if not is_path_enabled(condition.entry_path):
                return templates.TemplateResponse(
                    request,
                    "session_unavailable.html",
                    {"app_name": app_name},
                    headers={"Cache-Control": "no-store"},
                )
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

    @router.post("/prompts/{entry_path}", include_in_schema=False, response_model=None)
    async def save_prompt(entry_path: str, request: Request) -> HTMLResponse | RedirectResponse:
        if entry_path not in REQUIRED_ENTRY_PATHS:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
        form = parse_qs((await request.body()).decode("utf-8", errors="replace"))
        prompt = form.get("prompt", [""])[0]
        try:
            save_override(entry_path, prompt)
        except PromptOverrideError as error:
            return _render_prompt_editor(
                request,
                app_name=app_name,
                error=str(error),
                drafts={entry_path: prompt},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        return RedirectResponse(
            f"/prompts?saved={entry_path}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    @router.post("/prompts/{entry_path}/reset", include_in_schema=False, response_model=None)
    def restore_prompt(entry_path: str) -> RedirectResponse:
        if entry_path not in REQUIRED_ENTRY_PATHS:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
        reset_override(entry_path)
        return RedirectResponse(
            f"/prompts?restored={entry_path}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    return router


def _render_prompt_editor(
    request: Request,
    *,
    app_name: str,
    error: str = "",
    drafts: dict[str, str] | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    catalog = get_condition_catalog()
    rows: list[dict[str, str | bool]] = []
    for condition in catalog.conditions:
        default_prompt = condition.system_prompt
        if drafts and condition.entry_path in drafts:
            prompt = drafts[condition.entry_path]
        else:
            prompt = effective_system_prompt(condition)
        rows.append(
            {
                "entry_path": condition.entry_path,
                "prompt": prompt,
                "customized": prompt.strip() != default_prompt.strip(),
                "enabled": is_path_enabled(condition.entry_path),
            }
        )
    notice = _prompt_notice(request)
    return templates.TemplateResponse(
        request,
        "prompt_editor.html",
        {
            "app_name": app_name,
            "rows": rows,
            "notice": notice,
            "error": error,
        },
        status_code=status_code,
        headers={"Cache-Control": "no-store"},
    )


async def _enabled_from_request(request: Request) -> bool:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        payload = await request.json()
        if not isinstance(payload, dict) or "enabled" not in payload:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="enabled is required",
            )
        return bool(payload["enabled"])
    form = parse_qs((await request.body()).decode("utf-8", errors="replace"))
    raw = form.get("enabled", ["0"])[-1].strip().casefold()
    return raw in {"1", "true", "on", "yes"}


def _wants_json(request: Request) -> bool:
    return "application/json" in request.headers.get("content-type", "")


def _prompt_notice(request: Request) -> str:
    saved = request.query_params.get("saved", "")
    restored = request.query_params.get("restored", "")
    if saved in REQUIRED_ENTRY_PATHS:
        return f"Saved the prompt for /{saved}."
    if restored in REQUIRED_ENTRY_PATHS:
        return f"Restored the built-in prompt for /{restored}."
    return ""
