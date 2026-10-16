#!/usr/bin/env python3
"""Compare two independently generated ST-LAT world manifests for deterministic identity and geometry."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIRST = ROOT / "artifacts/stlat-world3d-manifest-first-build.json"
SECOND = ROOT / "artifacts/stlat-world3d-manifest.json"
REPORT = ROOT / "artifacts/stlat-world3d-determinism.json"
ENTITY_FIELDS = ("id", "name", "type", "role", "location", "rotation_euler_rad", "dimensions", "aabb_world", "mesh_vertex_count", "mesh_edge_count", "mesh_polygon_count", "mesh_geometry_sha256")

def index_manifest(data: Any, label: str) -> tuple[dict[str, dict[str, Any]], list[str]]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return {}, [f"{label}: root must be a JSON object"]
    if data.get("schema") != "stlat.world3d.v1":
        errors.append(f"{label}: schema must equal stlat.world3d.v1")
    if data.get("status") != "success":
        errors.append(f"{label}: status must be success")
    objects = data.get("objects")
    if not isinstance(objects, list):
        return {}, errors + [f"{label}: objects must be an array"]
    if data.get("object_count") != len(objects):
        errors.append(f"{label}: object_count does not match objects array")
    indexed: dict[str, dict[str, Any]] = {}
    for i, item in enumerate(objects):
        if not isinstance(item, dict):
            errors.append(f"{label}: objects[{i}] must be an object")
            continue
        object_id = item.get("id")
        if not isinstance(object_id, str) or not object_id.strip():
            errors.append(f"{label}: objects[{i}].id must be a non-empty string")
            continue
        if object_id in indexed:
            errors.append(f"{label}: duplicate object id {object_id!r}")
            continue
        missing = [field for field in ENTITY_FIELDS if field not in item]
        if missing:
            errors.append(f"{label}: object {object_id!r} missing fields {missing}")
            continue
        indexed[object_id] = item
    return indexed, errors

def compare_manifests(first: Any, second: Any) -> dict[str, Any]:
    left, left_errors = index_manifest(first, "first manifest")
    right, right_errors = index_manifest(second, "second manifest")
    errors = left_errors + right_errors
    left_ids, right_ids = set(left), set(right)
    missing_from_second = sorted(left_ids - right_ids)
    new_in_second = sorted(right_ids - left_ids)
    changed: list[dict[str, Any]] = []
    for object_id in sorted(left_ids & right_ids):
        differences = [field for field in ENTITY_FIELDS if left[object_id].get(field) != right[object_id].get(field)]
        if differences:
            changed.append({"id": object_id, "fields": differences})
    checks = {
        "both_manifests_valid": not left_errors and not right_errors,
        "object_ids_unique_in_both_builds": len(left) == len(left_ids) and len(right) == len(right_ids),
        "same_object_ids": not missing_from_second and not new_in_second,
        "same_semantics_and_transforms": not changed,
        "same_object_count": len(left) == len(right),
    }
    checks["status"] = "success" if all(value for value in checks.values() if isinstance(value, bool)) else "failed"
    return {
        "schema": "stlat.deterministic-build.v1",
        "status": checks["status"],
        "method": "compare IDs, names, types, semantic roles, transforms, dimensions and world AABBs from two independent scene builds",
        "first_build_object_count": len(left),
        "second_build_object_count": len(right),
        "missing_from_second": missing_from_second,
        "new_in_second": new_in_second,
        "changed_objects": changed,
        "errors": errors,
        "checks": checks,
        "note": "This compares exported semantic geometry metadata, not vertex-level mesh hashes or render pixels.",
    }

def validate_report(data: Any) -> list[str]:
    if not isinstance(data, dict):
        return ["report root must be an object"]
    errors: list[str] = []
    if data.get("schema") != "stlat.deterministic-build.v1":
        errors.append("schema must equal stlat.deterministic-build.v1")
    if data.get("status") != "success":
        errors.append("report status must be success")
    checks = data.get("checks")
    required = ("both_manifests_valid", "object_ids_unique_in_both_builds", "same_object_ids", "same_semantics_and_transforms", "same_object_count")
    if not isinstance(checks, dict):
        errors.append("checks must be an object")
    else:
        for key in required:
            if checks.get(key) is not True:
                errors.append(f"required determinism check failed: {key}")
        if checks.get("status") != "success":
            errors.append("checks.status must be success")
    if data.get("first_build_object_count") != data.get("second_build_object_count"):
        errors.append("build object counts differ")
    for key in ("missing_from_second", "new_in_second", "changed_objects", "errors"):
        if not isinstance(data.get(key), list):
            errors.append(f"{key} must be an array")
        elif data[key]:
            errors.append(f"{key} must be empty for a successful report")
    return errors

def self_test() -> None:
    obj = {"id": "character.head", "name": "Character.Head", "type": "MESH", "role": "character.head",
           "location": [0, 0, 1], "rotation_euler_rad": [0, 0, 0], "dimensions": [0.4, 0.4, 0.4],
           "aabb_world": {"min": [-0.2, -0.2, 0.8], "max": [0.2, 0.2, 1.2]},
           "mesh_vertex_count": 12, "mesh_edge_count": 18, "mesh_polygon_count": 8, "mesh_geometry_sha256": "abc123"}
    base = {"schema": "stlat.world3d.v1", "status": "success", "object_count": 1, "objects": [obj]}
    good = compare_manifests(base, copy.deepcopy(base))
    if validate_report(good):
        raise SystemExit("SELF_TEST_FAIL: identical manifests rejected")
    changed = copy.deepcopy(base)
    changed["objects"][0]["location"] = [0, 0, 2]
    bad = compare_manifests(base, changed)
    if bad["status"] != "failed" or not bad["changed_objects"]:
        raise SystemExit("SELF_TEST_FAIL: transform drift not detected")
    shape_changed = copy.deepcopy(base)
    shape_changed["objects"][0]["mesh_geometry_sha256"] = "different-hash"
    bad_shape = compare_manifests(base, shape_changed)
    if bad_shape["status"] != "failed" or "mesh_geometry_sha256" not in bad_shape["changed_objects"][0]["fields"]:
        raise SystemExit("SELF_TEST_FAIL: mesh geometry drift not detected")
    duplicate = copy.deepcopy(base)
    duplicate["objects"].append(copy.deepcopy(obj))
    duplicate["object_count"] = 2
    bad_duplicate = compare_manifests(duplicate, duplicate)
    if not bad_duplicate["errors"]:
        raise SystemExit("SELF_TEST_FAIL: duplicate IDs not rejected")
    print("DETERMINISTIC_MANIFEST_SELF_TEST=PASS (identical builds accepted; transform/mesh drift and duplicate IDs rejected)")

def main() -> None:
    if "--self-test" in sys.argv:
        self_test()
        return
    args = [arg for arg in sys.argv[1:] if not arg.startswith("--")]
    first_path = Path(args[0]) if len(args) > 0 else FIRST
    second_path = Path(args[1]) if len(args) > 1 else SECOND
    report_path = Path(args[2]) if len(args) > 2 else REPORT
    try:
        first = json.loads(first_path.read_text(encoding="utf-8"))
        second = json.loads(second_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"DETERMINISTIC_MANIFEST_VALIDATION=FAIL: cannot read manifests: {exc}")
    report = compare_manifests(first, second)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("STLAT_DETERMINISTIC_MANIFEST=" + json.dumps(report))
    errors = validate_report(report)
    if errors:
        for error in errors:
            print("ERROR:", error)
        raise SystemExit(f"DETERMINISTIC_MANIFEST_VALIDATION=FAIL ({len(errors)} errors)")
    print(f"DETERMINISTIC_MANIFEST_VALIDATION=PASS (stable IDs and transforms across {report['first_build_object_count']} objects)")

if __name__ == "__main__":
    main()
