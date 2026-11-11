import smtplib
from collections.abc import Callable
from email.message import EmailMessage

from app.config import SmtpSettings
from app.healthcheck.probe import ProbeOutcome

SmtpClientFactory = Callable[..., smtplib.SMTP]


class SmtpMailer:
    def __init__(
        self,
        settings: SmtpSettings,
        smtp_client_factory: SmtpClientFactory | None = None,
    ) -> None:
        self._settings = settings
        self._smtp_client_factory = smtp_client_factory or smtplib.SMTP

    def send_failure(self, outcome: ProbeOutcome) -> None:
        if not self._settings.enabled:
            return
        message = EmailMessage()
        message["From"] = self._settings.sender
        message["To"] = self._settings.to_address
        message["Subject"] = "[UNMC RAG] Simulated query failed"
        message.set_content(_failure_body(outcome))

        with self._smtp_client_factory(
            self._settings.host,
            self._settings.port,
            timeout=30,
        ) as client:
            if self._settings.use_tls:
                client.starttls()
            if self._settings.username.strip():
                client.login(self._settings.username, self._settings.password)
            client.send_message(message)


def _failure_body(outcome: ProbeOutcome) -> str:
    lines = [
        "The UNMC Course Assistant simulated query did not return an answered result.",
        "",
        f"Question: {outcome.question}",
        f"Status: {outcome.status or 'n/a'}",
        f"Reason: {outcome.reason}",
        f"Layer: {outcome.layer or 'n/a'}",
    ]
    if outcome.detail:
        lines.append(f"Detail: {outcome.detail}")
    return "\n".join(lines) + "\n"
