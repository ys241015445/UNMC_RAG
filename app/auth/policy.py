from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SchoolEmailPolicy:
    """MVP email-domain gate; replace with an SSO identity provider in production."""

    allowed_domain: str

    def normalize_and_validate(self, email: str) -> str:
        normalized = email.strip().casefold()
        local_part, separator, domain = normalized.rpartition("@")
        expected_domain = self.allowed_domain.strip().casefold().lstrip("@")

        if not separator or not local_part or domain != expected_domain:
            raise ValueError("Use a valid school email address")

        return normalized
