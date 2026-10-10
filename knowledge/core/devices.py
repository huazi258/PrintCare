"""Server-owned device identifiers for the supported PrintCare V1 devices."""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SupportedDevice:
    """Canonical device data used by the upload and import pipeline."""

    device_id: str
    device_model: str
    item_name: str


DEFAULT_DEVICE_ID = "creality-k1"

_SUPPORTED_DEVICES = {
    DEFAULT_DEVICE_ID: SupportedDevice(
        device_id=DEFAULT_DEVICE_ID,
        device_model="Creality K1",
        item_name="Creality K1",
    )
}


class UnsupportedDeviceError(ValueError):
    """Raised when a client requests a device outside the V1 allowlist."""


def resolve_supported_device(device_id: Optional[str] = None) -> SupportedDevice:
    """Return the canonical V1 device, rejecting every non-allowlisted value.

    ``None`` represents the legacy upload request which did not include a
    device field.  It intentionally defaults to the only V1 device.  Empty
    strings and every explicit alternative (including K1 Max) are rejected.
    """
    requested_device_id = DEFAULT_DEVICE_ID if device_id is None else device_id
    device = _SUPPORTED_DEVICES.get(requested_device_id)
    if device is None:
        raise UnsupportedDeviceError(
            "不支持的设备标识。V1 仅支持 Creality K1（device_id=creality-k1）。"
        )
    return device
