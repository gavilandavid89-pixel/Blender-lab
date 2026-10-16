#!/usr/bin/env python3
"""Regression tests for ST-LAT world snapshot versioning and identity invariants."""
from __future__ import annotations
import copy
import json
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import world_state_contract as contract  # noqa: E402


def entity(entity_id, role, *, identity_ref=None, position=None, attributes=None):
    return {
        "id": entity_id, "role": role,
        "transform": {"position": position or [0.0, 0.0, 0.0],
                      "rotation_euler_rad": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
        "bounds": {"min": [-0.5, -0.5, 0.0], "max": [0.5, 0.5, 2.0], "kind": "aabb"},
        "persistence": "static" if role.startswith("environment") else "dynamic",
        "collision": "solid" if role != "camera.main" else "none",
        "identity_ref": identity_ref, "attributes": attributes or {},
    }


def snapshot(version=1, entities=None, events=None, world_id="world-alpha"):
    return {
        "schema": "stlat.world-state.v1", "world_id": world_id, "version": version,
        "parent_version": None if version == 1 else version - 1,
        "units": "meters", "axes": dict(contract.AXES),
        "bounds": {"min": [-4.0, -4.0, 0.0], "max": [4.0, 4.0, 3.2]},
        "timestamp": float(version),
        "entities": copy.deepcopy(entities if entities is not None else [
            entity("room.floor", "environment.floor"),
            entity("char.001", "character", identity_ref="identity.goku", attributes={
                "identity_signature": "sig-001", "asset_id": "asset-body-v1",
                "appearance_id": "appearance-orange-v1"}),
            entity("camera.main", "camera.main")]),
        "events": copy.deepcopy(events or []),
    }


class WorldStateValidationTests(unittest.TestCase):
    def test_valid_snapshot_passes(self):
        self.assertEqual([], contract.validate_state(snapshot()))

    def test_duplicate_entity_ids_fail(self):
        data = snapshot(); data["entities"].append(copy.deepcopy(data["entities"][0]))
        self.assertTrue(any("duplicate entity id" in e for e in contract.validate_state(data)))

    def test_invalid_axis_convention_fails(self):
        data = snapshot(); data["axes"]["y"] = "forward"
        self.assertTrue(any("axis convention" in e for e in contract.validate_state(data)))

    def test_non_finite_transform_fails(self):
        data = snapshot(); data["entities"][0]["transform"]["position"] = [0.0, float("nan"), 0.0]
        self.assertTrue(any("position must be a finite vector3" in e for e in contract.validate_state(data)))

    def test_invalid_bounds_fail(self):
        data = snapshot(); data["bounds"]["min"][0] = 9.0
        self.assertTrue(any("bounds min must not exceed max" in e for e in contract.validate_state(data)))

    def test_valid_transform_change_preserves_identity(self):
        before = snapshot(); after = snapshot(2, before["entities"])
        after["entities"][1]["transform"]["position"] = [1.0, 0.0, 0.0]
        self.assertEqual([], contract.validate_transition(before, after))

    def test_identity_ref_cannot_change_silently(self):
        before = snapshot(); after = snapshot(2, before["entities"])
        after["entities"][1]["identity_ref"] = "identity.vegeta"
        self.assertTrue(any("protected identity changed" in e for e in contract.validate_transition(before, after)))

    def test_identity_signature_cannot_change_silently(self):
        before = snapshot(); after = snapshot(2, before["entities"])
        after["entities"][1]["attributes"]["identity_signature"] = "sig-other"
        self.assertTrue(any("protected identity changed" in e for e in contract.validate_transition(before, after)))

    def test_approved_identity_change_must_match_old_and_new_values(self):
        before = snapshot()
        event = {"id": "event-identity-1", "type": "identity_change_approved", "timestamp": 2.0,
                 "actor_id": "user", "target_id": "char.001", "approved": True,
                 "previous_identity_ref": "identity.goku", "new_identity_ref": "identity.vegeta"}
        after = snapshot(2, before["entities"], events=[event])
        after["entities"][1]["identity_ref"] = "identity.vegeta"
        self.assertEqual([], contract.validate_transition(before, after))
        after["events"][0]["previous_identity_ref"] = "identity.piccolo"
        self.assertTrue(any("protected identity changed" in e for e in contract.validate_transition(before, after)))

    def test_version_jump_fails(self):
        before = snapshot(); after = snapshot(3, before["entities"])
        self.assertTrue(any("previous version + 1" in e for e in contract.validate_transition(before, after)))

    def test_world_id_cannot_change(self):
        before = snapshot(); after = snapshot(2, before["entities"], world_id="different-world")
        self.assertTrue(any("world_id cannot change" in e for e in contract.validate_transition(before, after)))

    def test_unapproved_entity_removal_fails(self):
        before = snapshot(); after = snapshot(2, [before["entities"][0], before["entities"][1]])
        self.assertTrue(any("requires an approved entity_removed" in e for e in contract.validate_transition(before, after)))

    def test_approved_entity_removal_passes(self):
        before = snapshot()
        event = {"id": "event-remove-camera", "type": "entity_removed", "timestamp": 2.0,
                 "actor_id": "system", "target_id": "camera.main", "approved": True}
        after = snapshot(2, [before["entities"][0], before["entities"][1]], events=[event])
        self.assertEqual([], contract.validate_transition(before, after))

    def test_camera_change_does_not_mutate_world(self):
        before = snapshot(); after = snapshot(2, before["entities"])
        after["entities"][2]["transform"]["position"] = [1.0, -3.0, 2.0]
        self.assertEqual([], contract.validate_camera_isolation(before, after))

    def test_camera_change_with_character_mutation_fails(self):
        before = snapshot(); after = snapshot(2, before["entities"])
        after["entities"][2]["transform"]["position"] = [1.0, -3.0, 2.0]
        after["entities"][1]["transform"]["position"] = [1.0, 0.0, 0.0]
        self.assertTrue(any("modified non-camera" in e for e in contract.validate_camera_isolation(before, after)))

    def test_camera_only_operation_must_change_a_camera(self):
        before = snapshot(); after = snapshot(2, before["entities"])
        self.assertTrue(any("did not change any camera" in e for e in contract.validate_camera_isolation(before, after)))

    def test_entity_creation_requires_approved_event(self):
        before = snapshot(); entities = before["entities"] + [entity("prop.new", "prop.table")]
        after = snapshot(2, entities)
        self.assertTrue(any("requires an approved entity_created" in e for e in contract.validate_transition(before, after)))

    def test_approved_entity_creation_passes(self):
        before = snapshot(); entities = before["entities"] + [entity("prop.new", "prop.table")]
        event = {"id": "event-create-prop", "type": "entity_created", "timestamp": 2.0,
                 "actor_id": "user", "target_id": "prop.new", "approved": True}
        after = snapshot(2, entities, events=[event])
        self.assertEqual([], contract.validate_transition(before, after))

class WorldEventReplayTests(unittest.TestCase):
    def setUp(self):
        from world_state_replay import ReplayError, replay_events
        self.ReplayError = ReplayError
        self.replay_events = replay_events
        self.initial = snapshot()

    def event(self, event_id, event_type, target_id, timestamp=2.0, payload=None, **extra):
        return {"id": event_id, "type": event_type, "timestamp": timestamp,
                "actor_id": "test-user", "target_id": target_id,
                "approved": True, "payload": payload or {}, **extra}

    def test_replay_transform_updates_transform_and_bounds(self):
        event = self.event("evt-move-1", "transform_updated", "char.001", payload={
            "transform": {"position": [1.0, 0.0, 0.0], "rotation_euler_rad": [0.0, 0.0, 0.0],
                          "scale": [1.0, 1.0, 1.0]},
            "bounds": {"min": [0.5, -0.5, 0.0], "max": [1.5, 0.5, 2.0], "kind": "aabb"}})
        result = self.replay_events(self.initial, [event])
        self.assertEqual([1.0, 0.0, 0.0], result["entities"][1]["transform"]["position"])
        self.assertEqual(2, result["version"])
        self.assertEqual(1, result["parent_version"])
        self.assertEqual([], contract.validate_state(result))
        expected = snapshot(2, self.initial["entities"], events=[event])
        expected["entities"][1]["transform"] = copy.deepcopy(event["payload"]["transform"])
        expected["entities"][1]["bounds"] = copy.deepcopy(event["payload"]["bounds"])
        self.assertEqual(expected, result, "replayed snapshot must exactly match the expected target state")

    def test_replay_create_then_remove_in_order(self):
        events = [
            self.event("evt-create", "entity_created", "prop.new", payload={"entity": entity("prop.new", "prop.table")}),
            self.event("evt-remove", "entity_removed", "prop.new", timestamp=3.0),
        ]
        result = self.replay_events(self.initial, events)
        self.assertNotIn("prop.new", [e["id"] for e in result["entities"]])
        self.assertEqual(3, result["version"])
        self.assertEqual(["evt-create", "evt-remove"], [e["id"] for e in result["events"]])

    def test_replay_does_not_mutate_input_snapshot_or_events(self):
        original = copy.deepcopy(self.initial)
        events = [self.event("evt-move", "transform_updated", "char.001", payload={
            "transform": {"position": [1.0, 0.0, 0.0], "rotation_euler_rad": [0.0, 0.0, 0.0],
                          "scale": [1.0, 1.0, 1.0]},
            "bounds": {"min": [0.5, -0.5, 0.0], "max": [1.5, 0.5, 2.0], "kind": "aabb"}})]
        original_events = copy.deepcopy(events)
        self.replay_events(self.initial, events)
        self.assertEqual(original, self.initial)
        self.assertEqual(original_events, events)

    def test_unapproved_event_is_rejected(self):
        event = self.event("evt-no-approval", "entity_removed", "camera.main")
        event["approved"] = False
        with self.assertRaisesRegex(self.ReplayError, "explicitly approved"):
            self.replay_events(self.initial, [event])

    def test_unknown_event_type_is_rejected(self):
        with self.assertRaisesRegex(self.ReplayError, "unsupported"):
            self.replay_events(self.initial, [self.event("evt-unknown", "teleport_anywhere", "char.001")])

    def test_duplicate_event_ids_are_rejected(self):
        event = self.event("evt-same", "entity_removed", "camera.main")
        with self.assertRaisesRegex(self.ReplayError, "duplicates event id"):
            self.replay_events(self.initial, [event, {**event, "timestamp": 3.0}])

    def test_event_timestamp_cannot_go_backwards(self):
        with self.assertRaisesRegex(self.ReplayError, "timestamp"):
            self.replay_events(self.initial, [self.event("evt-old", "entity_removed", "camera.main", timestamp=0.5)])

    def test_creation_target_must_match_entity_id(self):
        event = self.event("evt-create-mismatch", "entity_created", "prop.other",
                           payload={"entity": entity("prop.new", "prop.table")})
        with self.assertRaisesRegex(self.ReplayError, "must match"):
            self.replay_events(self.initial, [event])

    def test_transform_event_requires_complete_bounds(self):
        event = self.event("evt-transform-bad", "transform_updated", "char.001",
                           payload={"transform": {"position": [1, 0, 0]}})
        with self.assertRaisesRegex(self.ReplayError, "complete transform and bounds"):
            self.replay_events(self.initial, [event])

    def test_invalid_replayed_transform_is_rejected(self):
        event = self.event("evt-transform-invalid", "transform_updated", "char.001", payload={
            "transform": {"position": [1.0, 0.0, 0.0], "rotation_euler_rad": [0.0, 0.0, 0.0],
                          "scale": [1.0, 1.0, 1.0]},
            "bounds": {"min": [2.0, 0.0, 0.0], "max": [1.0, 1.0, 1.0], "kind": "aabb"}})
        with self.assertRaisesRegex(self.ReplayError, "invalid snapshot"):
            self.replay_events(self.initial, [event])

    def test_missing_target_is_rejected(self):
        with self.assertRaisesRegex(self.ReplayError, "cannot remove missing"):
            self.replay_events(self.initial, [self.event("evt-missing", "entity_removed", "does.not.exist")])

    def test_invalid_initial_snapshot_is_rejected(self):
        invalid = copy.deepcopy(self.initial)
        invalid["axes"]["z"] = "down"
        with self.assertRaisesRegex(self.ReplayError, "invalid initial snapshot"):
            self.replay_events(invalid, [])

    def test_approved_role_change_replays_with_matching_old_and_new_role(self):
        event = self.event("evt-role", "entity_role_change_approved", "char.001",
                           previous_role="character", new_role="character.hero")
        result = self.replay_events(self.initial, [event])
        self.assertEqual("character.hero", result["entities"][1]["role"])
        self.assertEqual(2, result["version"])

    def test_approved_identity_change_replays_ref_and_signature(self):
        event = self.event("evt-identity", "identity_change_approved", "char.001",
                           previous_identity_ref="identity.goku", new_identity_ref="identity.vegeta",
                           changed_identity_attributes=["identity_signature"],
                           payload={"attributes": {"identity_signature": "sig-002"}})
        result = self.replay_events(self.initial, [event])
        self.assertEqual("identity.vegeta", result["entities"][1]["identity_ref"])
        self.assertEqual("sig-002", result["entities"][1]["attributes"]["identity_signature"])
        self.assertEqual([], contract.validate_state(result))

    def test_identity_replay_rejects_wrong_previous_reference(self):
        event = self.event("evt-identity-wrong-old", "identity_change_approved", "char.001",
                           previous_identity_ref="identity.piccolo", new_identity_ref="identity.vegeta")
        with self.assertRaisesRegex(self.ReplayError, "previous_identity_ref"):
            self.replay_events(self.initial, [event])

    def test_identity_replay_rejects_unlisted_attribute_mutation(self):
        event = self.event("evt-identity-unlisted", "identity_change_approved", "char.001",
                           previous_identity_ref="identity.goku", new_identity_ref="identity.goku",
                           payload={"attributes": {"identity_signature": "sig-002"}})
        with self.assertRaisesRegex(self.ReplayError, "exactly match"):
            self.replay_events(self.initial, [event])

    def test_entity_bounds_outside_world_are_rejected(self):
        data = snapshot()
        data["entities"][1]["bounds"]["min"][0] = -5.0
        self.assertTrue(any("exceed hard world bounds" in e for e in contract.validate_state(data)))

    def test_camera_bounds_may_extend_outside_world(self):
        data = snapshot()
        data["entities"][2]["bounds"] = {
            "min": [-20.0, -20.0, -20.0], "max": [20.0, 20.0, 20.0], "kind": "aabb"}
        self.assertEqual([], contract.validate_state(data))

    def test_replay_rejects_entity_moved_outside_world_bounds(self):
        event = self.event("evt-outside-world", "transform_updated", "char.001", payload={
            "transform": {"position": [5.0, 0.0, 0.0], "rotation_euler_rad": [0.0, 0.0, 0.0],
                          "scale": [1.0, 1.0, 1.0]},
            "bounds": {"min": [4.5, -0.5, 0.0], "max": [5.5, 0.5, 2.0], "kind": "aabb"}})
        with self.assertRaisesRegex(self.ReplayError, "hard world bounds"):
            self.replay_events(self.initial, [event])

    def test_entity_transform_origin_outside_world_is_rejected(self):
        data = snapshot()
        data["entities"][1]["transform"]["position"] = [4.1, 0.0, 0.0]
        self.assertTrue(any("transform.position exceeds hard world bounds" in e for e in contract.validate_state(data)))

    def test_replay_rejects_outside_origin_even_when_bounds_claim_inside(self):
        event = self.event("evt-origin-outside", "transform_updated", "char.001", payload={
            "transform": {"position": [5.0, 0.0, 0.0], "rotation_euler_rad": [0.0, 0.0, 0.0],
                          "scale": [1.0, 1.0, 1.0]},
            "bounds": {"min": [0.5, -0.5, 0.0], "max": [1.5, 0.5, 2.0], "kind": "aabb"}})
        with self.assertRaisesRegex(self.ReplayError, "transform.position exceeds hard world bounds"):
            self.replay_events(self.initial, [event])



class WorldStateStoreTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        from world_state_store import SnapshotStoreError, WorldStateStore
        from world_state_replay import replay_events
        self.temp = tempfile.TemporaryDirectory(prefix="stlat-store-unit-")
        self.addCleanup(self.temp.cleanup)
        self.Store = WorldStateStore
        self.StoreError = SnapshotStoreError
        self.replay_events = replay_events
        self.root = Path(self.temp.name) / "store"
        self.initial = snapshot()
        self.event = {
            "id": "evt-store-unit", "type": "transform_updated", "timestamp": 2.0,
            "actor_id": "unit-test", "target_id": "char.001", "approved": True,
            "payload": {
                "transform": {"position": [1.0, 0.0, 0.0], "rotation_euler_rad": [0.0, 0.0, 0.0],
                              "scale": [1.0, 1.0, 1.0]},
                "bounds": {"min": [0.5, -0.5, 0.0], "max": [1.5, 0.5, 2.0], "kind": "aabb"}}}
        self.next_state = self.replay_events(self.initial, [self.event])

    def test_snapshot_store_round_trip_and_latest(self):
        store = self.Store(self.root)
        store.save_snapshot(self.initial)
        store.save_snapshot(self.next_state)
        self.assertEqual(self.initial, store.load_snapshot("world-alpha", 1))
        self.assertEqual(self.next_state, store.load_latest("world-alpha"))

    def test_snapshot_store_versions_are_immutable(self):
        store = self.Store(self.root)
        store.save_snapshot(self.initial)
        altered = copy.deepcopy(self.initial)
        altered["timestamp"] = 1.5
        with self.assertRaisesRegex(self.StoreError, "immutable"):
            store.save_snapshot(altered)

    def test_snapshot_store_rejects_version_gaps(self):
        store = self.Store(self.root)
        store.save_snapshot(self.initial)
        gap = snapshot(3, self.initial["entities"])
        with self.assertRaisesRegex(self.StoreError, "latest version"):
            store.save_snapshot(gap)

    def test_snapshot_store_detects_file_tampering(self):
        store = self.Store(self.root)
        path = store.save_snapshot(self.initial)
        envelope = json.loads(path.read_text(encoding="utf-8"))
        envelope["snapshot"]["timestamp"] = 99.0
        path.write_text(json.dumps(envelope), encoding="utf-8")
        with self.assertRaisesRegex(self.StoreError, "digest mismatch"):
            store.load_snapshot("world-alpha", 1)

    def test_snapshot_store_rejects_invalid_snapshot(self):
        store = self.Store(self.root)
        invalid = copy.deepcopy(self.initial)
        invalid["axes"]["z"] = "down"
        with self.assertRaisesRegex(self.StoreError, "invalid snapshot"):
            store.save_snapshot(invalid)

    def test_snapshot_store_save_is_idempotent_for_same_version(self):
        store = self.Store(self.root)
        first = store.save_snapshot(self.initial)
        second = store.save_snapshot(self.initial)
        self.assertEqual(first, second)

    def test_snapshot_store_requires_contiguous_valid_transition(self):
        store = self.Store(self.root)
        store.save_snapshot(self.initial)
        invalid_next = copy.deepcopy(self.next_state)
        invalid_next["entities"][1]["identity_ref"] = "identity.vegeta"
        with self.assertRaisesRegex(self.StoreError, "transition invalid"):
            store.save_snapshot(invalid_next)
    def test_snapshot_store_detects_missing_history_version(self):
        store = self.Store(self.root)
        first_path = store.save_snapshot(self.initial)
        store.save_snapshot(self.next_state)
        first_path.unlink()
        with self.assertRaisesRegex(self.StoreError, "missing versions"):
            store.load_latest("world-alpha")

    def test_valid_parent_child_hierarchy_passes(self):
        data = snapshot()
        data["entities"][1]["parent_id"] = "room.floor"
        self.assertEqual([], contract.validate_state(data))

    def test_missing_parent_reference_is_rejected(self):
        data = snapshot()
        data["entities"][1]["parent_id"] = "entity.missing"
        self.assertTrue(any("references missing parent" in e for e in contract.validate_state(data)))

    def test_entity_cannot_parent_itself(self):
        data = snapshot()
        data["entities"][1]["parent_id"] = "char.001"
        self.assertTrue(any("cannot be its own parent" in e for e in contract.validate_state(data)))

    def test_parent_hierarchy_cycle_is_rejected(self):
        data = snapshot()
        data["entities"][0]["parent_id"] = "char.001"
        data["entities"][1]["parent_id"] = "room.floor"
        self.assertTrue(any("parent hierarchy contains a cycle" in e for e in contract.validate_state(data)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
