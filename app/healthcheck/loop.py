import asyncio
from collections.abc import Callable
from logging import getLogger
from typing import Any

from app.config import ProbeSettings, SmtpSettings
from app.healthcheck.mailer import SmtpMailer
from app.healthcheck.probe import notify_if_failed, run_probe
from app.rag.service import ChatService

logger = getLogger(__name__)


async def run_probe_loop(
    *,
    tick: Callable[[], None],
    startup_delay_seconds: float,
    interval_seconds: float,
    stop_event: asyncio.Event,
) -> None:
    if await _stopped(stop_event, startup_delay_seconds):
        return
    while not stop_event.is_set():
        try:
            await asyncio.to_thread(tick)
        except Exception:
            logger.exception("Simulated query probe raised unexpectedly")
        if await _stopped(stop_event, interval_seconds):
            return


def start_background_probe(
    app: Any,
    *,
    chat_service: ChatService,
    probe_settings: ProbeSettings,
    smtp_settings: SmtpSettings,
) -> asyncio.Task[None] | None:
    if not probe_settings.enabled:
        logger.info("Simulated query probe is disabled")
        return None

    mailer = SmtpMailer(smtp_settings) if smtp_settings.enabled else None
    if mailer is None:
        logger.warning("Simulated query probe will not email: SMTP is not configured")

    stop_event = asyncio.Event()
    task = asyncio.create_task(
        run_probe_loop(
            tick=_make_tick(chat_service, probe_settings.question, mailer),
            startup_delay_seconds=probe_settings.startup_delay_seconds,
            interval_seconds=probe_settings.interval_hours * 3600,
            stop_event=stop_event,
        ),
        name="unmc-rag-probe",
    )
    app.state.probe_stop = stop_event
    app.state.probe_task = task
    logger.info(
        "Simulated query probe started delay=%ss interval=%sh question=%r",
        probe_settings.startup_delay_seconds,
        probe_settings.interval_hours,
        probe_settings.question,
    )
    return task


async def stop_background_probe(app: Any) -> None:
    stop = getattr(app.state, "probe_stop", None)
    task = getattr(app.state, "probe_task", None)
    if stop is not None:
        stop.set()
    if task is not None:
        await task


def _make_tick(
    chat_service: ChatService,
    question: str,
    mailer: SmtpMailer | None,
) -> Callable[[], None]:
    def tick() -> None:
        outcome = run_probe(chat_service, question)
        if outcome.ok:
            logger.info("Simulated query succeeded status=%s", outcome.status)
        else:
            logger.warning(
                "Simulated query failed status=%s reason=%s detail=%s",
                outcome.status,
                outcome.reason,
                outcome.detail,
            )
        notify_if_failed(outcome, mailer)

    return tick


async def _stopped(stop_event: asyncio.Event, timeout: float) -> bool:
    if stop_event.is_set():
        return True
    if timeout <= 0:
        return False
    try:
        await asyncio.wait_for(stop_event.wait(), timeout=timeout)
        return True
    except TimeoutError:
        return False
