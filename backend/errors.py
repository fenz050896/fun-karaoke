from dataclasses import dataclass
from typing import Optional


DETAIL_LIMIT = 500


def truncate_detail(detail: Optional[str], limit: int = DETAIL_LIMIT) -> Optional[str]:
    if not detail:
        return None
    clean = str(detail).strip()
    if not clean:
        return None
    if len(clean) <= limit:
        return clean
    return clean[: limit - 3].rstrip() + "..."


def error_payload(code: str, message: str, detail: Optional[str] = None) -> dict:
    payload = {
        "code": code,
        "message": message,
    }
    short_detail = truncate_detail(detail)
    if short_detail:
        payload["detail"] = short_detail
    return payload


@dataclass
class AppError(Exception):
    code: str
    message: str
    detail: Optional[str] = None

    def __str__(self) -> str:
        return self.message

    def as_dict(self) -> dict:
        return error_payload(self.code, self.message, self.detail)
