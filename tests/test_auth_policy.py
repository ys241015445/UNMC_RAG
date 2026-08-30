import pytest

from app.auth.policy import SchoolEmailPolicy


def test_accepts_configured_school_email_domain() -> None:
    policy = SchoolEmailPolicy(allowed_domain="unmc.edu")

    assert policy.normalize_and_validate(" Student@UNMC.EDU ") == "student@unmc.edu"


@pytest.mark.parametrize(
    "email",
    ["student@gmail.com", "attacker@unmc.edu.example", "not-an-email", ""],
)
def test_rejects_non_school_email(email: str) -> None:
    policy = SchoolEmailPolicy(allowed_domain="unmc.edu")

    with pytest.raises(ValueError, match="学校邮箱"):
        policy.normalize_and_validate(email)
