#!/usr/bin/env python3
"""Validate camera-isolation evidence without requiring Blender."""
import copy
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = ROOT / "artifacts/stlat-world3d-camera-isolation.json"
REQUIRED_CHECKS = (
    "required_cameras_found",
    "camera_transform_or_lens_changed",
    "active_camera_switch_applied",
    "non_camera_objects_unchanged",
    "non_camera_geometry_and_transforms_unchanged",
)

def validate_report(data):
    errors = []
    if not isinstance(data, dict):
        return ["root must be a JSON object"]
    if data.get("schema") != "stlat.camera-isolation.v1":
        errors.append("schema must equal stlat.camera-isolation.v1")
    if data.get("status") != "success":
        errors.append("report status must be success")
    if not isinstance(data.get("method"), str) or not data["method"].strip():
        errors.append("method must describe the real-scene test")
    checks = data.get("checks")
    if not isinstance(checks, dict):
        errors.append("checks must be an object")
    else:
        for key in REQUIRED_CHECKS:
            if checks.get(key) is not True:
                errors.append(f"required camera isolation check failed: {key}")
        if checks.get("status") != "success":
            errors.append("checks.status must be success")
    for key in ("non_camera_object_count", "mesh_geometry_count"):
        value = data.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            errors.append(f"{key} must be a positive integer")
    changed = data.get("changed_non_camera_objects")
    if not isinstance(changed, list):
        errors.append("changed_non_camera_objects must be an array")
    elif changed:
        errors.append("non-camera objects changed during camera operation")
    before, after = data.get("camera_before"), data.get("camera_after")
    if not isinstance(before, dict) or not isinstance(after, dict):
        errors.append("camera_before and camera_after must be objects")
    else:
        if not isinstance(before.get("Camera.Main"), dict) or not isinstance(after.get("Camera.Main"), dict):
            errors.append("Camera.Main before/after evidence is missing")
        elif before["Camera.Main"] == after["Camera.Main"]:
            errors.append("Camera.Main must show a transform or lens change")
    if data.get("final_active_camera") != "Camera.Top":
        errors.append("final_active_camera must be Camera.Top")
    return errors

def self_test():
    valid = {
        "schema": "stlat.camera-isolation.v1", "status": "success",
        "method": "mutate camera and compare scene signatures",
        "checks": {key: True for key in REQUIRED_CHECKS} | {"status": "success"},
        "non_camera_object_count": 20, "mesh_geometry_count": 15,
        "changed_non_camera_objects": [],
        "camera_before": {"Camera.Main": {"location": [0, 0, 0], "lens": 48}, "Camera.Top": {"lens": 45}},
        "camera_after": {"Camera.Main": {"location": [1, 0, 0], "lens": 55}, "Camera.Top": {"lens": 45}},
        "final_active_camera": "Camera.Top",
    }
    if validate_report(valid):
        raise SystemExit("SELF_TEST_FAIL: valid camera report rejected")
    bad = copy.deepcopy(valid)
    bad["changed_non_camera_objects"] = ["Character.Torso"]
    bad["checks"]["non_camera_objects_unchanged"] = False
    bad["status"] = "failed"
    errors = validate_report(bad)
    if not any("objects changed" in e for e in errors) or not any("non_camera_objects_unchanged" in e for e in errors):
        raise SystemExit("SELF_TEST_FAIL: mutated world was not rejected")
    bad_camera = copy.deepcopy(valid)
    bad_camera["camera_after"]["Camera.Main"] = bad_camera["camera_before"]["Camera.Main"]
    if not any("must show a transform" in e for e in validate_report(bad_camera)):
        raise SystemExit("SELF_TEST_FAIL: unchanged camera was not rejected")
    print("CAMERA_ISOLATION_REPORT_SELF_TEST=PASS (valid evidence accepted; world mutation and unchanged camera rejected)")

def main():
    if "--self-test" in sys.argv:
        self_test()
        return
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_REPORT
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"CAMERA_ISOLATION_REPORT_VALIDATION=FAIL: cannot read {path}: {exc}")
    errors = validate_report(data)
    if errors:
        for error in errors:
            print("ERROR:", error)
        raise SystemExit(f"CAMERA_ISOLATION_REPORT_VALIDATION=FAIL ({len(errors)} errors)")
    print(
        "CAMERA_ISOLATION_REPORT_VALIDATION=PASS "
        f"(non-camera objects={data['non_camera_object_count']}; meshes={data['mesh_geometry_count']}; world unchanged)"
    )

if __name__ == "__main__":
    main()
