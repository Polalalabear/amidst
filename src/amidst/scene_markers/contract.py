"""Constants taken from the controlled-scene contract v1.1 draft (0e51c53) and the CS-B design.

Section numbers refer to ``docs/contracts/OFFICE_CONTROLLED_SCENE_V1.md`` (v1.1 draft) unless a
constant says "design" (``CONTROLLED_SCENE_B_DESIGN_20261018.md`` @ f2afa3f).  Where the contract
is silent the constant is deliberately absent (see ``unknowns`` in the marker template).
"""

from __future__ import annotations

import re

CONTRACT_REF = "OFFICE_CONTROLLED_SCENE_V1 v1.1 draft @ 0e51c53"
DESIGN_REF = "CONTROLLED_SCENE_B_DESIGN_20261018 (D50) @ f2afa3f"

STATIC_SCHEMA_VERSION = "controlled-scene.static.v1"  # §3.1
HEX64 = re.compile(r"^[0-9a-f]{64}$")
ID_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")  # §3.2
SCHEMA_VERSION_PATTERN = re.compile(r"^controlled-scene\.[a-z0-9_.-]+\.v[0-9]+$")
RUN_ID_PATTERN = re.compile(
    r"^ctrl-lcorr-s(?P<scene_version>[0-9]+)-(?P<event>a|b1|b2)-(?P<sampling>[a-z0-9]+)"
    r"-v(?P<sv>[0-9]+)-r(?P<revision>[0-9]{3})$"
)  # §4 (the sampling label is "5fps-v1": 5fps + -v1)
PREVIEW_RUN_ID_PATTERN = re.compile(
    r"^ctrl-lcorr-s[0-9]+-preview-[a-z0-9]+-v[0-9]+-r[0-9]{3}$"
)  # §4
RGB_REF_PATTERN = re.compile(
    r"^rgb/(?P<camera>[A-Z][A-Z0-9_]{2,63})/frame_(?P<index>[0-9]{6})\.png$"
)  # §4

OBJECT_CLASSES = (
    "WALKABLE",
    "WALL",
    "OBSTACLE",
    "PORTAL",
    "STAIR",
    "ROOM",
    "CORRIDOR",
    "AREA",
    "DISPLAY_ONLY",
)
PREFIX_BY_CLASS: dict[str, str | None] = {
    "WALKABLE": "WALK_",
    "WALL": "WALL_",
    "OBSTACLE": "OBSTACLE_",
    "PORTAL": "PORTAL_",
    "STAIR": "STAIR_",
    "ROOM": "ROOM_",
    "CORRIDOR": "CORR_",
    "AREA": "AREA_",
    "DISPLAY_ONLY": None,
}
PURPOSES = ("WALKABILITY", "OCCLUSION", "COLLISION", "VISIBILITY_INDEX", "DISPLAY")
DISPLAY_ONLY_FORBIDS = ("WALKABILITY", "OCCLUSION", "COLLISION")
SOURCE_METHODS = ("ANNOTATED_AT_CREATION", "UNKNOWN")
APPROVAL_STATUSES = ("APPROVED", "NOT_EVALUATED", "REJECTED")
WALK_STATUSES = ("WALKABLE", "BLOCKED", "UNKNOWN")
SOLID_ROLES = ("PHYSICAL", "DISPLAY")
COLLISION_SCOPES = ("EXACT_MESH", "FOOTPRINT_EXTRUDED", "UNKNOWN")
SOLID_CLASSES = ("WALL", "OBSTACLE")

STATIC_REQUIRED = (
    "schema_version",
    "scene_id",
    "scene_version",
    "frame_id",
    "length_unit",
    "time_unit",
    "world_axes",
    "floors",
    "source_static_sha256",
    "objects",
    "walkable",
    "portals",
    "stairs",
)
FLOOR_REQUIRED = (
    "floor_id",
    "support_plane",
    "support_surface_ids",
    "source_static_sha256",
    "approved_scope_ref",
)
OBJECT_REQUIRED = (
    "id",
    "class",
    "source_mesh",
    "source_object_id",
    "geometry_ref",
    "geometry_sha256",
    "geometry_version",
    "geometry_encoding_version",
    "transform_applied",
    "bounds_m",
    "source_method",
    "allowed_purposes",
    "approval_status",
    "scope_ref",
    "approval_ref",
    "approval_sha256",
    "display_only",
)
SOLID_REQUIRED = (
    "floor_id",
    "footprint_m",
    "base_z_m",
    "height_m",
    "role",
    "collision_scope",
    "body_policy_ref",
    "body_policy_sha256",
)
WALK_REQUIRED = (
    "id",
    "floor_id",
    "support_surface_id",
    "polygon_m",
    "holes_m",
    "geometry_ref",
    "geometry_sha256",
    "status",
    "connections",
    "approval",
)
WALK_APPROVAL_REQUIRED = ("status", "verified_by", "verification_sha256")
PORTAL_REQUIRED = (
    "id",
    "floor_id",
    "opening_m",
    "geometry_ref",
    "geometry_sha256",
    "geometry_version",
    "connects",
    "state",
    "allowed_purposes",
)
OPENING_REQUIRED = ("a", "b", "width_m", "sill_z_m", "height_m")
CAMERA_REQUIRED = (
    "schema_version",
    "camera_id",
    "camera_to_world",
    "convention",
    "fx",
    "fy",
    "cx",
    "cy",
    "pixel_origin",
    "width",
    "height",
    "pixel_aspect_xy",
    "render_resolution_percentage",
    "shift_x",
    "shift_y",
    "sensor_fit",
    "sensor_width_mm",
    "sensor_height_mm",
    "focal_length_mm",
    "clip_start",
    "clip_end",
    "distortion",
    "camera_model",
    "floor_id",
    "zone_id",
    "meters_per_unit",
    "static_validity",
    "calibration_sha256",
)
# Run-bound fields must stay out of the optical calibration (§3.7: calibration_sha256 has no clock).
CAMERA_RUN_FIELDS = (
    "run_id",
    "clock_id",
    "valid_time_range_s",
    "visibility_index_ref",
    "binding_sha256",
)
BINDING_REQUIRED = (
    "run_id",
    "camera_id",
    "clock_id",
    "valid_time_range_s",
    "visibility_index_ref",
    "binding_sha256",
)
MANIFEST_REQUIRED = (
    "schema_version",
    "scene_id",
    "scene_version",
    "run_id",
    "clock_id",
    "sampling",
    "allowlist",
    "source_sha256",
)
SAMPLING_REQUIRED = (
    "fps",
    "image_size_px",
    "format",
    "sampling_version",
    "duration_s",
    "sample_count_per_camera",
    "last_timestamp_s",
)
ALLOWLIST_REQUIRED = ("role", "filename", "file_sha256")
ALLOWLIST_ROLES = ("scene_static", "cameras", "event_query", "rgb_index", "runtime_profile")
SAFE_FILENAMES = {
    "scene_static": "scene_static.json",
    "manifest": "manifest.json",
    "cameras": "cameras.json",
    "rgb_index": "rgb_index.json",
    "runtime_profile": "runtime_profile.json",
}
RGB_RECORD_REQUIRED = ("camera_id", "frame_index", "timestamp_s", "rgb_ref", "file_sha256")
RGB_MISSING_REQUIRED = ("camera_id", "frame_index", "timestamp_s", "reason")
RUNTIME_PROFILE_REQUIRED = (
    "schema_version",
    "scene_id",
    "run_id",
)  # minimal; full list UNKNOWN (§3.11)

CAMERA_CONVENTION = "BLENDER_NEG_Z_UP_Y"
PIXEL_ORIGIN = "TOP_LEFT_CONTINUOUS"
PORTAL_STATE = "OPEN"
IMAGE_FORMAT = "PNG_RGB8"

# Hash-valued keys that may legitimately be null (§3.3 approval_sha256, §3.4 NOT_EVALUATED).
NULLABLE_HASH_KEYS = frozenset({"approval_sha256", "verification_sha256"})

# Safe/private separation (§3.0, §3.10, §7).  The key blacklist is the second line of defence;
# the first is that the validator only ever opens the five allowlisted safe filenames.
FORBIDDEN_KEYS = frozenset(
    {
        "actor",
        "actors",
        "actor_id",
        "actor_ids",
        "person",
        "persons",
        "person_id",
        "person_sim_id",
        "persons_sim",
        "gait",
        "speed_mps",
        "start_s",
        "end_behavior",
        "waypoints",
        "route_waypoints_m",
        "designed_blind_intervals",
        "observation_windows",
        "overlap_requirements",
        "separation_requirements",
        "expected_blind",
        "blind_intervals",
        "production_manifest",
        "blend_file_sha256",
        "blender_version",
        "frame_start",
        "frame_step",
        "fps_base",
        "generator",
        "generator_script",
        "generator_script_sha256",
        "generator_config",
        "ground_truth",
        "gt_files",
        "depth",
        "depth_ref",
        "depth_map",
        "depth_path",
    }
)
FORBIDDEN_KEY_TOKENS = frozenset(
    {"gt", "mask", "masks", "actor", "actors", "seed", "route", "routes", "private"}
)
FORBIDDEN_VALUE_FRAGMENTS = (
    "private_evaluation",
    "production_manifest",
    "persons.sim",
    ".validation.json",
    "ground_truth",
    "groundtruth",
    ".blend",
)
FORBIDDEN_PATH_SEGMENTS = frozenset(
    {"gt", "derived", "private_evaluation", "review_only", "assets"}
)
PRIVATE_FILENAMES = frozenset({"production_manifest.json", "persons.sim.json"})
