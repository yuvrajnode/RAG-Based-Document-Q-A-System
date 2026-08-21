from __future__ import annotations

from verbatim.config import Settings, get_settings
from verbatim.service import RagService, get_service


def service_dependency() -> RagService:
    return get_service()


def settings_dependency() -> Settings:
    return get_settings()
