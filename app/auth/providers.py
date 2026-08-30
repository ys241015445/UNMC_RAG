from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class Identity:
    subject: str
    email: str
    display_name: str


class IdentityProvider(Protocol):
    """邮箱魔法链接和后续学校 SSO 共用的身份接口。"""

    def resolve(self, credential: str) -> Identity: ...
