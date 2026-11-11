from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class Identity:
    subject: str
    email: str
    display_name: str


class IdentityProvider(Protocol):
    """Shared identity interface for email magic links and later campus SSO."""

    def resolve(self, credential: str) -> Identity: ...
