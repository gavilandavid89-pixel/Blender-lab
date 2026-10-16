#!/usr/bin/env python3
"""Validate the machine-readable Blender world manifest without third-party packages."""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "artifacts/stlat-world3d-manifest.json"
REQUIRED_ROLES = {
    "environment.floor",
    "environment.wall",
    "prop.bed",
    "prop.window",
    "character.head",
    "character.torso",
}
EXPECTED_AXES = {
    "x": "right",
    "y": "depth; positive toward back wall",
    "z": "up",
}


def validate_manifest(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["root must be a JSON object"]
    if data.get("schema") != "stlat.world3d.v1":
        errors.append("schema must equal stlat.world3d.v1")
    if data.get("status") != "success":
        errors.append("manifest status must be success")
    if data.get("units") != "meters":
        errors.append("units must be meters")
    if data.get("axes") != EXPECTED_AXES:
        errors.append("axis convention differs from the declared world contract")

    room = data.get("room_interior")
    if not isinstance(room, dict) or not _valid_vector(room.get("min")) or not _valid_vector(room.get("max")):
        errors.append("room_interior must have finite min/max vectors of length 3")
    elif any(room["min"][i] >= room["max"][i] for i in range(3)):
        errors.append("room_interior min must be less than max on every axis")

    checks = data.get("checks")
    if not isinstance(checks, dict):
        errors.append("checks must be an object")
    else:
        for key in ("character_parts_inside_room_by_origin", "required_roles_present",
                    "main_camera_exists", "topdown_camera_exists", "coordinate_convention_declared"):
            if checks.get(key) is not True:
                errors.append(f"required manifest check failed: {key}")
        if checks.get("missing_roles") != []:
            errors.append("missing_roles must be an empty array")

    objects = data.get("objects")
    if not isinstance(objects, list) or not objects:
        errors.append("objects must be a non-empty array")
        objects = []
    ids: set[str] = set()
    roles: set[str] = set()
    for index, obj in enumerate(objects):
        prefix = f"objects[{index}]"
        if not isinstance(obj, dict):
            errors.append(f"{prefix} must be an object")
            continue
        for key in ("id", "name", "type", "role"):
            if not isinstance(obj.get(key), str) or not obj[key].strip():
                errors.append(f"{prefix}.{key} must be a non-empty string")
        obj_id = obj.get("id")
        if isinstance(obj_id, str) and obj_id:
            if obj_id in ids:
                errors.append(f"duplicate entity id: {obj_id}")
            ids.add(obj_id)
        role = obj.get("role")
        if isinstance(role, str):
            roles.add(role)
            if role == "unclassified":
                errors.append(f"{prefix} has no semantic role")
        if not _valid_vector(obj.get("location")):
            errors.append(f"{prefix}.location must be a finite vector3")
        if not _valid_vector(obj.get("rotation_euler_rad")):
            errors.append(f"{prefix}.rotation_euler_rad must be a finite vector3")
        if not _valid_vector(obj.get("dimensions")) or any(v < 0 for v in obj.get("dimensions", [])):
            errors.append(f"{prefix}.dimensions must be a finite non-negative vector3")
        aabb = obj.get("aabb_world")
        if not isinstance(aabb, dict) or not _valid_vector(aabb.get("min")) or not _valid_vector(aabb.get("max")):
            errors.append(f"{prefix}.aabb_world must have finite min/max vectors")
        elif any(aabb["min"][i] > aabb["max"][i] for i in range(3)):
            errors.append(f"{prefix}.aabb_world min exceeds max")

    missing_roles = sorted(REQUIRED_ROLES - roles)
    if missing_roles:
        errors.append(f"required semantic roles missing: {missing_roles}")
    if data.get("object_count") != len(objects):
        errors.append("object_count does not match objects array length")

    renders = data.get("renders")
    if not isinstance(renders, list) or len(renders) < 2 or not all(isinstance(x, str) and x for x in renders):
        errors.append("renders must list at least two named render outputs")
    root = data.get("character_root")
    if not _valid_vector(root):
        errors.append("character_root must be a finite vector3")
    return errors


def _valid_vector(value: Any) -> bool:
    return (isinstance(value, list) and len(value) == 3
            and all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
                    for v in value))


def self_test() -> None:
    valid = {
        "schema": "stlat.world3d.v1", "status": "success", "units": "meters",
        "axes": EXPECTED_AXES, "room_interior": {"min": [-4, -4, 0], "max": [4, 4, 3.2]},
        "character_root": [0, 0, 0], "object_count": 6, "renders": ["a.png", "b.png"],
        "checks": {"character_parts_inside_room_by_origin": True, "required_roles_present": True,
                   "main_camera_exists": True, "topdown_camera_exists": True,
                   "coordinate_convention_declared": True, "missing_roles": []},
        "objects": [
            {"id": str(i), "name": str(i), "type": "MESH", "role": role,
             "location": [0, 0, 0], "rotation_euler_rad": [0, 0, 0],
             "dimensions": [1, 1, 1], "aabb_world": {"min": [-1, -1, -1], "max": [1, 1, 1]}}
            for i, role in enumerate(sorted(REQUIRED_ROLES))
        ],
    }
    if validate_manifest(valid):
        raise SystemExit("SELF_TEST_FAIL: valid fixture rejected")
    bad = json.loads(json.dumps(valid))
    bad["objects"][1]["id"] = bad["objects"][0]["id"]
    bad["objects"][1]["aabb_world"]["min"] = [9, 0, 0]
    bad["objects"][1]["aabb_world"]["max"] = [0, 1, 1]
    errors = validate_manifest(bad)
    if not any("duplicate entity id" in e for e in errors):
        raise SystemExit("SELF_TEST_FAIL: duplicate IDs were not detected")
    if not any("min exceeds max" in e for e in errors):
        raise SystemExit("SELF_TEST_FAIL: inverted AABB was not detected")
    bad2 = json.loads(json.dumps(valid))
    bad2["checks"]["main_camera_exists"] = False
    if not any("main_camera_exists" in e for e in validate_manifest(bad2)):
        raise SystemExit("SELF_TEST_FAIL: failed camera check was not detected")
    print("WORLD_MANIFEST_SELF_TEST=PASS (valid fixture accepted; duplicate IDs, invalid AABB and failed check rejected)")


def main() -> None:
    if "--self-test" in sys.argv:
        self_test()
        return
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_MANIFEST
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"WORLD_MANIFEST_VALIDATION=FAIL: cannot read {path}: {exc}")
    errors = validate_manifest(data)
    if errors:
        for error in errors:
            print("ERROR:", error)
        raise SystemExit(f"WORLD_MANIFEST_VALIDATION=FAIL ({len(errors)} errors)")
    print(f"WORLD_MANIFEST_VALIDATION=PASS ({len(data['objects'])} objects, {len(data['renders'])} renders, semantic IDs unique)")


if __name__ == "__main__":
    main()
