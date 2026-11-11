from app.config import SmtpSettings
from app.healthcheck.mailer import SmtpMailer
from app.healthcheck.probe import ProbeOutcome


class FakeSMTP:
    def __init__(self, host: str, port: int, timeout: float = 30) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.tls = False
        self.login_args: tuple[str, str] | None = None
        self.message = None

    def __enter__(self) -> "FakeSMTP":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def starttls(self) -> None:
        self.tls = True

    def login(self, username: str, password: str) -> None:
        self.login_args = (username, password)

    def send_message(self, message) -> None:
        self.message = message


def test_smtp_settings_disabled_without_host() -> None:
    settings = SmtpSettings(
        host="",
        to_address="yellow.sea@live.cn",
        username="user",
        password="secret",
    )
    assert settings.enabled is False


def test_smtp_settings_enabled_with_host_and_recipient() -> None:
    settings = SmtpSettings(host="smtp.example.com", to_address="yellow.sea@live.cn")
    assert settings.enabled is True


def test_smtp_mailer_sends_failure_email() -> None:
    settings = SmtpSettings(
        host="smtp.example.com",
        port=587,
        username="user@example.com",
        password="secret",
        from_address="alerts@example.com",
        to_address="yellow.sea@live.cn",
        use_tls=True,
    )
    client = FakeSMTP(settings.host, settings.port)
    mailer = SmtpMailer(settings, smtp_client_factory=lambda host, port, timeout=30: client)
    outcome = ProbeOutcome(
        ok=False,
        question="When is the next graduation ceremony?",
        reason="insufficient_evidence",
        status="refused",
        layer="evidence",
        detail="",
    )

    mailer.send_failure(outcome)

    assert client.tls is True
    assert client.login_args == ("user@example.com", "secret")
    assert client.message["To"] == "yellow.sea@live.cn"
    assert client.message["From"] == "alerts@example.com"
    assert "failed" in client.message["Subject"].casefold()
    body = client.message.get_content()
    assert "When is the next graduation ceremony?" in body
    assert "insufficient_evidence" in body
