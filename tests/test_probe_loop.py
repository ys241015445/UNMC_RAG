import asyncio
from types import SimpleNamespace

from app.config import ProbeSettings, SmtpSettings
from app.healthcheck.loop import run_probe_loop, start_background_probe


def test_probe_loop_runs_after_startup_delay() -> None:
    calls: list[str] = []
    stop = asyncio.Event()

    def tick() -> None:
        calls.append("tick")
        stop.set()

    async def run() -> None:
        await run_probe_loop(
            tick=tick,
            startup_delay_seconds=0.05,
            interval_seconds=10,
            stop_event=stop,
        )

    asyncio.run(run())
    assert calls == ["tick"]


def test_probe_loop_repeats_after_interval() -> None:
    calls: list[str] = []
    stop = asyncio.Event()

    def tick() -> None:
        calls.append("tick")
        if len(calls) >= 2:
            stop.set()

    async def run() -> None:
        await run_probe_loop(
            tick=tick,
            startup_delay_seconds=0.01,
            interval_seconds=0.05,
            stop_event=stop,
        )

    asyncio.run(run())
    assert calls == ["tick", "tick"]


def test_probe_loop_stop_before_startup_skips_tick() -> None:
    calls: list[str] = []
    stop = asyncio.Event()
    stop.set()

    def tick() -> None:
        calls.append("tick")

    async def run() -> None:
        await run_probe_loop(
            tick=tick,
            startup_delay_seconds=1,
            interval_seconds=10,
            stop_event=stop,
        )

    asyncio.run(run())
    assert calls == []


def test_start_background_probe_skips_when_disabled() -> None:
    app = SimpleNamespace(state=SimpleNamespace())
    task = start_background_probe(
        app,
        chat_service=object(),  # type: ignore[arg-type]
        probe_settings=ProbeSettings(enabled=False),
        smtp_settings=SmtpSettings(host=""),
    )
    assert task is None
