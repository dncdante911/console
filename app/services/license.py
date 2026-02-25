from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class LicenseConfig:
    server_url: str
    license_key: str
    machine_id: str


def build_machine_id(hostname: str, ip: str) -> str:
    return f"{hostname}:{ip}".strip()


def validate_license(config: LicenseConfig, timeout_s: float = 5.0) -> tuple[bool, str]:
    endpoint = config.server_url.rstrip("/") + "/api/v1/validate"
    payload: dict[str, Any] = {
        "license_key": config.license_key,
        "machine_id": config.machine_id,
    }
    try:
        response = httpx.post(endpoint, json=payload, timeout=timeout_s)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:  # noqa: BLE001
        return False, f"license server error: {exc}"

    if data.get("valid") is True:
        return True, data.get("message", "ok")
    return False, data.get("message", "license is not valid")
