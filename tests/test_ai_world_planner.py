import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from ai_world_planner import request_plan, validate_plan


def sample_snapshot():
    return {
        "world_id": "world.test",
        "version": 1,
        "units": "meters",
        "axes": {"x": "right", "y": "depth_positive_toward_back_wall", "z": "up"},
        "bounds": {"min": [-4.0, -4.0, 0.0], "max": [4.0, 4.0, 3.2]},
        "entities": [
            {"id": "char.001", "role": "character.torso",
             "transform": {"position": [0.0, 0.0, 1.0],
                           "rotation_euler_rad": [0.0, 0.0, 0.0],
                           "scale": [1.0, 1.0, 1.0]},
             "identity_ref": "identity.character.001",
             "attributes": {"identity_signature": "sig-001"}},
            {"id": "prop.ball.001", "role": "prop.ball",
             "transform": {"position": [1.0, 0.0, 0.2],
                           "rotation_euler_rad": [0.0, 0.0, 0.0],
                           "scale": [1.0, 1.0, 1.0]}},
        ],
    }


def operation(target="char.001", position=None):
    return {"type": "transform_updated", "target_id": target, "reason": "test",
            "transform": {"position": position or [1.0, 0.0, 1.0],
                          "rotation_euler_rad": [0.0, 0.0, 0.0],
                          "scale": [1.0, 1.0, 1.0]}}


class AIWorldPlannerRequestTests(unittest.TestCase):
    def test_request_includes_explicit_user_agent(self):
        import json
        from unittest.mock import patch

        response_body = {"choices": [{"message": {"content": json.dumps({
            "summary": "Move character right.",
            "operations": [operation(position=[1.0, 0.0, 1.0])],
        })}}]}
        class FakeResponse:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self):
                return json.dumps(response_body).encode("utf-8")

        def fake_urlopen(request, timeout):
            self.assertEqual("ST-LAT-World3D-Lab/1.0 (+https://github.com/gavilandavid89-pixel/Blender-lab)",
                             request.get_header("User-agent"))
            self.assertEqual("Bearer test-key", request.get_header("Authorization"))
            self.assertEqual(45, timeout)
            return FakeResponse()

        with patch("ai_world_planner.urllib.request.urlopen", side_effect=fake_urlopen):
            plan = request_plan("Move character right", sample_snapshot(), "test-key")
        self.assertEqual("Move character right.", plan["summary"])


class AIWorldPlannerValidationTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = sample_snapshot()
        self.plan = {"summary": "Move the character beside the table.",
                     "operations": [operation()]}

    def test_valid_existing_entity_transform_is_accepted(self):
        self.assertEqual([], validate_plan(self.plan, self.snapshot))

    def test_unknown_entity_id_is_rejected(self):
        plan = copy.deepcopy(self.plan)
        plan["operations"][0]["target_id"] = "char.not-in-world"
        self.assertTrue(any("existing entity" in e for e in validate_plan(plan, self.snapshot)))

    def test_out_of_bounds_transform_is_rejected(self):
        plan = copy.deepcopy(self.plan)
        plan["operations"][0]["transform"]["position"] = [9.0, 0.0, 1.0]
        self.assertTrue(any("hard world bounds" in e for e in validate_plan(plan, self.snapshot)))

    def test_non_positive_scale_is_rejected(self):
        plan = copy.deepcopy(self.plan)
        plan["operations"][0]["transform"]["scale"] = [1.0, 0.0, 1.0]
        self.assertTrue(any("positive" in e for e in validate_plan(plan, self.snapshot)))

    def test_nan_is_rejected(self):
        plan = copy.deepcopy(self.plan)
        plan["operations"][0]["transform"]["position"] = [float("nan"), 0.0, 1.0]
        self.assertTrue(any("finite vector3" in e for e in validate_plan(plan, self.snapshot)))

    def test_duplicate_targets_are_rejected(self):
        plan = copy.deepcopy(self.plan)
        plan["operations"].append(operation())
        self.assertTrue(any("duplicates target_id" in e for e in validate_plan(plan, self.snapshot)))

    def test_create_or_delete_operation_is_rejected(self):
        plan = copy.deepcopy(self.plan)
        plan["operations"][0]["type"] = "entity_created"
        self.assertTrue(any("cannot create/delete" in e for e in validate_plan(plan, self.snapshot)))

    def test_identity_mutation_is_rejected(self):
        plan = copy.deepcopy(self.plan)
        plan["operations"][0]["identity_ref"] = "identity.other"
        self.assertTrue(any("protected identity" in e for e in validate_plan(plan, self.snapshot)))

    def test_missing_summary_is_rejected(self):
        plan = copy.deepcopy(self.plan)
        plan["summary"] = ""
        self.assertTrue(any("summary" in e for e in validate_plan(plan, self.snapshot)))


    def test_unsupported_relationship_field_is_rejected(self):
        plan = copy.deepcopy(self.plan)
        plan["operations"][0]["parent_id"] = "char.002"
        self.assertTrue(any("protected identity or relationship" in e for e in validate_plan(plan, self.snapshot)))

    def test_unrecognized_operation_field_is_rejected(self):
        plan = copy.deepcopy(self.plan)
        plan["operations"][0]["teleport"] = True
        self.assertTrue(any("unsupported fields" in e for e in validate_plan(plan, self.snapshot)))

    def test_unrecognized_transform_field_is_rejected(self):
        plan = copy.deepcopy(self.plan)
        plan["operations"][0]["transform"]["identity_ref"] = "identity.other"
        self.assertTrue(any("unsupported fields" in e for e in validate_plan(plan, self.snapshot)))

    def test_empty_reason_is_rejected(self):
        plan = copy.deepcopy(self.plan)
        plan["operations"][0]["reason"] = " "
        self.assertTrue(any(".reason must be a non-empty string" in e for e in validate_plan(plan, self.snapshot)))

    def test_duplicate_snapshot_entity_ids_are_rejected(self):
        snapshot = copy.deepcopy(self.snapshot)
        snapshot["entities"].append(copy.deepcopy(snapshot["entities"][0]))
        self.assertTrue(any("duplicate id char.001" in e for e in validate_plan(self.plan, snapshot)))

    def test_inverted_world_bounds_are_rejected(self):
        snapshot = copy.deepcopy(self.snapshot)
        snapshot["bounds"]["min"][0] = 5.0
        snapshot["bounds"]["max"][0] = 4.0
        self.assertTrue(any("min must not exceed max" in e for e in validate_plan(self.plan, snapshot)))


if __name__ == "__main__":
    unittest.main()
