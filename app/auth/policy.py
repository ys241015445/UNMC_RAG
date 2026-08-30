from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SchoolEmailPolicy:
    """MVP 邮箱域名门禁；正式环境由 SSO 身份提供方替换。"""

    allowed_domain: str

    def normalize_and_validate(self, email: str) -> str:
        normalized = email.strip().casefold()
        local_part, separator, domain = normalized.rpartition("@")
        expected_domain = self.allowed_domain.strip().casefold().lstrip("@")

        if not separator or not local_part or domain != expected_domain:
            raise ValueError("请使用有效的学校邮箱")

        return normalized
