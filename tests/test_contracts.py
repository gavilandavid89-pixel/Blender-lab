#!/usr/bin/env python3
"""Fast, dependency-free regression tests for ST-LAT's implemented contracts."""
from __future__ import annotations

import copy
import json
import math
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import validate_world_manifest as manifest_validator  # noqa: E402


class WorldManifestContractTests(unittest.TestCase):
    def setUp(self) -> None:
        roles = sorted(manifest_validator.REQUIRED_ROLES)
        self.valid = {
            "schema": "stlat.world3d.v1",
            "status": "success",
            "units": "meters",
            "axes": dict(manifest_validator.EXPECTED_AXES),
            "room_interior": {"min": [-4.0, -4.0, 0.0], "max": [4.0, 4.0, 3.2]},
            "character_root": [0.0, 0.0, 0.0],
            "object_count": len(roles),
            "renders": ["main.png", "topdown.png"],
            "checks": {
                "character_parts_inside_room_by_origin": True,
                "required_roles_present": True,
                "main_camera_exists": True,
                "topdown_camera_exists": True,
                "coordinate_convention_declared": True,
                "missing_roles": [],
            },
            "objects": [
                {
                    "id": f"entity-{i}",
                    "name": f"Entity {i}",
                    "type": "MESH",
                    "role": role,
                    "location": [0.0, 0.0, 0.0],
                    "rotation_euler_rad": [0.0, 0.0, 0.0],
                    "dimensions": [1.0, 1.0, 1.0],
                    "aabb_world": {"min": [-0.5, -0.5, -0.5], "max": [0.5, 0.5, 0.5]},
                }
                for i, role in enumerate(roles)
            ],
        }

    def errors(self, data=None):
        return manifest_validator.validate_manifest(self.valid if data is None else data)

    def test_valid_manifest_is_accepted(self):
        self.assertEqual([], self.errors())

    def test_non_object_root_is_rejected(self):
        self.assertIn("root must be a JSON object", self.errors([]))

    def test_wrong_schema_is_rejected(self):
        data = copy.deepcopy(self.valid)
        data["schema"] = "stlat.world3d.v0"
        self.assertTrue(any("schema" in e for e in self.errors(data)))

    def test_failed_status_is_rejected(self):
        data = copy.deepcopy(self.valid)
        data["status"] = "failed"
        self.assertTrue(any("status" in e for e in self.errors(data)))

    def test_wrong_units_and_axes_are_rejected(self):
        data = copy.deepcopy(self.valid)
        data["units"] = "centimeters"
        data["axes"]["y"] = "forward"
        errors = self.errors(data)
        self.assertTrue(any("units" in e for e in errors))
        self.assertTrue(any("axis convention" in e for e in errors))

    def test_inverted_room_bounds_are_rejected(self):
        data = copy.deepcopy(self.valid)
        data["room_interior"]["min"][0] = 5
        self.assertTrue(any("room_interior min" in e for e in self.errors(data)))

    def test_failed_required_check_is_rejected(self):
        data = copy.deepcopy(self.valid)
        data["checks"]["topdown_camera_exists"] = False
        self.assertTrue(any("topdown_camera_exists" in e for e in self.errors(data)))

    def test_missing_role_list_must_be_empty(self):
        data = copy.deepcopy(self.valid)
        data["checks"]["missing_roles"] = ["character.head"]
        self.assertTrue(any("missing_roles" in e for e in self.errors(data)))

    def test_duplicate_entity_ids_are_rejected(self):
        data = copy.deepcopy(self.valid)
        data["objects"][1]["id"] = data["objects"][0]["id"]
        self.assertTrue(any("duplicate entity id" in e for e in self.errors(data)))

    def test_unclassified_role_is_rejected(self):
        data = copy.deepcopy(self.valid)
        data["objects"][0]["role"] = "unclassified"
        self.assertTrue(any("no semantic role" in e for e in self.errors(data)))

    def test_missing_required_semantic_role_is_rejected(self):
        data = copy.deepcopy(self.valid)
        data["objects"][0]["role"] = "prop.unknown"
        self.assertTrue(any("required semantic roles missing" in e for e in self.errors(data)))

    def test_non_finite_location_is_rejected(self):
        data = copy.deepcopy(self.valid)
        data["objects"][0]["location"] = [0.0, math.inf, 0.0]
        self.assertTrue(any("location must be a finite vector3" in e for e in self.errors(data)))

    def test_boolean_is_not_accepted_as_coordinate(self):
        data = copy.deepcopy(self.valid)
        data["character_root"] = [False, 0.0, 0.0]
        self.assertTrue(any("character_root" in e for e in self.errors(data)))

    def test_negative_dimensions_are_rejected(self):
        data = copy.deepcopy(self.valid)
        data["objects"][0]["dimensions"] = [1.0, -0.1, 1.0]
        self.assertTrue(any("dimensions" in e for e in self.errors(data)))

    def test_inverted_object_aabb_is_rejected(self):
        data = copy.deepcopy(self.valid)
        data["objects"][0]["aabb_world"] = {"min": [2, 0, 0], "max": [1, 1, 1]}
        self.assertTrue(any("aabb_world min exceeds max" in e for e in self.errors(data)))

    def test_object_count_must_match_array(self):
        data = copy.deepcopy(self.valid)
        data["object_count"] += 1
        self.assertTrue(any("object_count" in e for e in self.errors(data)))

    def test_render_outputs_must_be_named(self):
        data = copy.deepcopy(self.valid)
        data["renders"] = ["main.png", ""]
        self.assertTrue(any("renders must list" in e for e in self.errors(data)))

    def test_scene_profile_contract_script_passes(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/validate_scene_profiles.py")],
            cwd=ROOT, text=True, capture_output=True, check=False,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("SCENE_PROFILE_VALIDATION=PASS", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
