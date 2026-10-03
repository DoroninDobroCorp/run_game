"""Pinned technical audio releases per route, independent of human field approval.

Changing a voice, script or encoding requires an explicit new fingerprint here;
reading an arbitrary manifest must never implicitly accept a new master.
"""

PINNED_MASTERS = {
    "el_bolson_patagonia_argentina_m01_v1": "4b9572d6807902f053da756a36448cd2277da38622b01d6457f83fdc4eee864e",
}


def expected_master(binding_id: object, legacy_sha256: str) -> str:
    return PINNED_MASTERS.get(binding_id, legacy_sha256) if isinstance(binding_id, str) else legacy_sha256
