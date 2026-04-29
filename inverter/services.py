"""Service layer for MQTT inverter message processing.

This module contains pure functions for validating and normalising data
received from the MQTT broker before it is persisted to the database.
Keeping this logic here makes the MQTT callbacks thin and easy to reason about.
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, Optional

from django.utils import timezone

logger = logging.getLogger(__name__)


INVERTER_TOPIC_REGEX = re.compile(r"inverter/([^/]+)/data")


@dataclass
class NormalizedInverterData:
    """Strongly-typed representation of a single inverter reading."""

    inverter_id: str
    voltage: Decimal
    current: Decimal
    power: Decimal
    temperature: float
    grid_connected: bool
    timestamp: Any  # Django-aware datetime


def generate_message_id() -> str:
    """Return a unique identifier for correlating logs and tasks."""
    return str(uuid.uuid4())


def extract_inverter_id(topic: str, payload: Dict[str, Any]) -> Optional[str]:
    """Extract the inverter identifier from the MQTT topic or payload."""
    match = INVERTER_TOPIC_REGEX.search(topic or "")
    if match:
        return match.group(1)
    inverter_id = payload.get("inverter_id")
    if isinstance(inverter_id, str) and inverter_id:
        return inverter_id
    return None


from typing import Dict, Any


def validate_inverter_message(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and normalize raw 
    MQTT payload from ESP32.

    Ensures:
    - Numeric coercion
    - Case-insensitive power handling
    - Stable internal field names
    """

    cleaned: Dict[str, Any] = {}

    # ---- Electrical values ----
    for field in ["VG", "IG", "VPV", "IPV"]:
        raw = data.get(field, 0)
        try:
            cleaned[field] = float(raw)
        except (TypeError, ValueError):
            cleaned[field] = 0.0

    # ---- POWER (ESP sends `power`) ----
    raw_power = (
        data.get("POWER")
        or data.get("Power")
        or data.get("power")
        or 0
    )

    try:
        cleaned["POWER"] = float(raw_power)
    except (TypeError, ValueError):
        cleaned["POWER"] = 0.0

    # ---- Temperature ----
    try:
        temp = float(data.get("temp", 0))
    except (TypeError, ValueError):
        temp = 0.0

    cleaned["TEMP1"] = temp
    cleaned["TEMP2"] = temp

    # ---- Timestamp (optional, backend time used anyway) ----
    cleaned["timestamp"] = data.get("timestamp")

    return cleaned




def normalize_inverter_data(
    inverter_id: str,
    cleaned: dict,
) -> NormalizedInverterData:
    """
    Normalize validated inverter telemetry.

    RULES:
    - voltage/current = GRID (VG / IG)
    - power = ESP POWER if present
    - fallback power = VG × IG
    """

    # ---- GRID (AC) ----
    vg = cleaned.get("VG", 0.0)   # ~230V
    ig = cleaned.get("IG", 0.0)   # ~12–13A

    # ---- PV (DC) ----
    vpv = cleaned.get("VPV", 0.0)
    ipv = cleaned.get("IPV", 0.0)

    # ---- POWER ----
    incoming_power = cleaned.get("POWER", 0.0)

    if incoming_power > 0:
        power = incoming_power
    else:
        power = vg * ig

    temperature = (cleaned["TEMP1"] + cleaned["TEMP2"]) / 2.0

    logger.warning(
        "NORMALIZED SAVE | VG=%.2f IG=%.2f VPV=%.2f IPV=%.2f "
        "POWER_IN=%.2f FINAL_POWER=%.2f",
        vg, ig, vpv, ipv, incoming_power, power
    )

    return NormalizedInverterData(
        inverter_id=inverter_id,
        voltage=Decimal(f"{vg:.2f}"),
        current=Decimal(f"{ig:.2f}"),
        power=Decimal(f"{power:.2f}"),
        temperature=temperature,
        grid_connected=vg > 200,
        timestamp=timezone.now(),
    )


def should_save_message(_: Dict[str, Any]) -> bool:
    """Determine whether this message should be persisted.

    Hook for adding filtering, deduplication or rate limiting in future.
    Currently always returns True.
    """
    return True


def build_inverter_data_kwargs(
    normalized: NormalizedInverterData, inverter_obj
) -> Dict[str, Any]:
    """Prepare keyword arguments for creating an InverterData instance."""
    return {
        "inverter": inverter_obj,
        # "manufacturer": getattr(inverter_obj, "manufacturer", None),
        "voltage": normalized.voltage,
        "current": normalized.current,
        "power": normalized.power,
        "temperature": normalized.temperature,
        "grid_connected": normalized.grid_connected,
        "timestamp": normalized.timestamp,
    }

