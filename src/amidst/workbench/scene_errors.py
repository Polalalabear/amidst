"""Separate integrity rejection from optional scene/quality availability."""

import re


class DataIntegrityError(ValueError):
    """Must never be downgraded to unavailable or not evaluated."""


def integrity_error(error: Exception) -> bool:
    code = str(error)
    return isinstance(error, DataIntegrityError) or any(
        marker in code
        for marker in (
            "HASH_MISMATCH",
            "BINDING_MISMATCH",
            "BLENDER_SCENE_STALE",
            "INVALID_CONTACT_CONTROL_PIN",
            "FIXTURE_FIXED_SCOPE_MISMATCH",
            "FIXTURE_CAMERA_MISMATCH",
            "PRESET_FIXTURE_SCENE_MISMATCH",
        )
    )


def public_reason(error: Exception, fallback: str) -> str:
    # Never publish exception paths, credentials or arbitrary diagnostic text.
    code = str(error)
    return code if re.fullmatch(r"[A-Z][A-Z0-9_]{0,99}", code) else fallback
