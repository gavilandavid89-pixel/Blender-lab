import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from ai_world_planner import validate_plan


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


if __name__ == "__main__":
    unittest.main()
