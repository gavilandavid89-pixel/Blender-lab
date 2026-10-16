#!/usr/bin/env python3
"""Validate the persisted motion-validation report independently of Blender."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = ROOT / "artifacts/stlat-world3d-motion-validation.json"
REQUIRED_CHECKS = (
    "character_parts_found",
    "initial_pose_is_valid",
    "safe_path_is_collision_free",
    "bed_path_hits_bed_geometry",
    "room_boundary_violation_detected",
)


def validate_report(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["root must be a JSON object"]
    if data.get("schema") != "stlat.motion-validation.v1":
        errors.append("schema must equal stlat.motion-validation.v1")
    if data.get("status") != "success":
        errors.append("report status must be success")
    method = data.get("method")
    if not isinstance(method, str) or not method.strip():
        errors.append("method must explain the validation method")
    if not isinstance(data.get("samples_per_path"), int) or data["samples_per_path"] < 1:
        errors.append("samples_per_path must be a positive integer")
    if not isinstance(data.get("epsilon_m"), (int, float)) or data["epsilon_m"] < 0:
        errors.append("epsilon_m must be a non-negative number")

    checks = data.get("checks")
    if not isinstance(checks, dict):
        errors.append("checks must be an object")
    else:
        for key in REQUIRED_CHECKS:
            if checks.get(key) is not True:
                errors.append(f"required motion check failed: {key}")
        if checks.get("status") != "success":
            errors.append("checks.status must be success")

    paths = data.get("paths")
    if not isinstance(paths, dict):
        errors.append("paths must be an object")
        paths = {}
    safe = paths.get("safe_walk_forward")
    if not isinstance(safe, dict):
        errors.append("safe_walk_forward evidence is missing")
    else:
        if safe.get("violating_samples") != 0:
            errors.append("safe_walk_forward must have zero violating samples")
        if not _vector3(safe.get("start")) or not _vector3(safe.get("end")):
            errors.append("safe_walk_forward must include finite start/end vectors")

    bed = paths.get("intentionally_blocked_toward_bed")
    if not isinstance(bed, dict):
        errors.append("intentionally_blocked_toward_bed evidence is missing")
    else:
        if not isinstance(bed.get("violating_samples"), int) or bed["violating_samples"] < 1:
            errors.append("blocked bed path must record at least one violating sample")
        if not _vector3(bed.get("start")) or not _vector3(bed.get("end")):
            errors.append("blocked bed path must include finite start/end vectors")

    outside = paths.get("intentionally_outside_room")
    if not isinstance(outside, dict):
        errors.append("intentionally_outside_room evidence is missing")
    else:
        if outside.get("inside_room") is not False:
            errors.append("outside-room test must record inside_room=false")
        if not isinstance(outside.get("outside_parts"), list) or not outside["outside_parts"]:
            errors.append("outside-room test must identify at least one outside character part")

    for key in ("character_part_count", "obstacle_count", "bed_geometry_collision_hits"):
        value = data.get(key)
        if not isinstance(value, int) or value < 0:
            errors.append(f"{key} must be a non-negative integer")
    if isinstance(data.get("character_part_count"), int) and data["character_part_count"] < 7:
        errors.append("character_part_count must be at least 7")
    if isinstance(data.get("obstacle_count"), int) and data["obstacle_count"] < 1:
        errors.append("obstacle_count must be at least 1")
    if isinstance(data.get("bed_geometry_collision_hits"), int) and data["bed_geometry_collision_hits"] < 1:
        errors.append("bed_geometry_collision_hits must be at least 1")
    if not _vector3(data.get("character_root")):
        errors.append("character_root must be a finite vector3")
    if not isinstance(data.get("initial_pose_collisions"), list):
        errors.append("initial_pose_collisions must be an array")
    return errors


def _vector3(value: Any) -> bool:
    import math
    return (
        isinstance(value, list) and len(value) == 3
        and all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in value)
    )


def self_test() -> None:
    valid = {
        "schema": "stlat.motion-validation.v1", "status": "success",
        "method": "sampled AABB validation", "samples_per_path": 48, "epsilon_m": 0.015,
        "character_root": [0.0, 0.0, 0.0], "character_part_count": 8,
        "obstacle_count": 5, "bed_geometry_collision_hits": 2, "initial_pose_collisions": [],
        "checks": {key: True for key in REQUIRED_CHECKS} | {"status": "success"},
        "paths": {
            "safe_walk_forward": {"start": [0, 0, 0], "end": [0, -2, 0], "violating_samples": 0},
            "intentionally_blocked_toward_bed": {"start": [0, 0, 0], "end": [2, 1, 0], "violating_samples": 4},
            "intentionally_outside_room": {"target": [5, 0, 0], "inside_room": False, "outside_parts": ["Character.Head"]},
        },
    }
    if validate_report(valid):
        raise SystemExit("SELF_TEST_FAIL: valid report rejected")
    bad = copy.deepcopy(valid)
    bad["paths"]["safe_walk_forward"]["violating_samples"] = 1
    bad["bed_geometry_collision_hits"] = 0
    bad["paths"]["intentionally_outside_room"]["outside_parts"] = []
    errors = validate_report(bad)
    expected = ("zero violating samples", "bed_geometry_collision_hits", "outside-room test must identify")
    if not all(any(token in error for error in errors) for token in expected):
        raise SystemExit("SELF_TEST_FAIL: negative evidence was not rejected")
    print("MOTION_REPORT_SELF_TEST=PASS (valid report accepted; unsafe path, missing bed evidence and missing boundary evidence rejected)")


def main() -> None:
    if "--self-test" in sys.argv:
        self_test()
        return
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_REPORT
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"MOTION_REPORT_VALIDATION=FAIL: cannot read {path}: {exc}")
    errors = validate_report(data)
    if errors:
        for error in errors:
            print("ERROR:", error)
        raise SystemExit(f"MOTION_REPORT_VALIDATION=FAIL ({len(errors)} errors)")
    print(
        "MOTION_REPORT_VALIDATION=PASS "
        f"(safe path clear; bed hits={data['bed_geometry_collision_hits']}; "
        f"outside parts={len(data['paths']['intentionally_outside_room']['outside_parts'])})"
    )


if __name__ == "__main__":
    main()
