#!/usr/bin/env python3
"""CLI-source regression tests for the Blender world-state bridge."""
from __future__ import annotations
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from world3d_sync_state import BlenderSyncError, load_snapshot_source
from world_state_contract import AXES
from world_state_replay import replay_events
from world_state_store import WorldStateStore


def _snapshot():
    return {
        "schema": "stlat.world-state.v1", "world_id": "sync-cli-test",
        "version": 1, "parent_version": None, "units": "meters", "axes": dict(AXES),
        "bounds": {"min": [-4.0, -4.0, 0.0], "max": [4.0, 4.0, 3.2]},
        "timestamp": 1.0, "events": [],
        "entities": [{
            "id": "character.torso", "role": "character.torso",
            "transform": {"position": [0.0, 0.0, 1.0], "rotation_euler_rad": [0.0, 0.0, 0.0],
                          "scale": [1.0, 1.0, 1.0]},
            "bounds": {"min": [-0.24, -0.15, 0.68], "max": [0.24, 0.15, 1.32], "kind": "aabb"},
            "persistence": "dynamic", "collision": "solid", "attributes": {},
        }],
    }


class SnapshotSourceTests(unittest.TestCase):
    def test_store_source_loads_latest_and_explicit_version(self):
        initial = _snapshot()
        event = {
            "id": "evt-move-cli", "type": "transform_updated", "timestamp": 2.0,
            "actor_id": "test", "target_id": "character.torso", "approved": True,
            "payload": {
                "transform": {"position": [0.5, 0.0, 1.0], "rotation_euler_rad": [0.0, 0.0, 0.0],
                              "scale": [1.0, 1.0, 1.0]},
                "bounds": {"min": [0.26, -0.15, 0.68], "max": [0.74, 0.15, 1.32], "kind": "aabb"},
            },
        }
        version_two = replay_events(initial, [event])
        with tempfile.TemporaryDirectory(prefix="stlat-sync-cli-test-") as temp:
            store = WorldStateStore(Path(temp) / "store")
            store.save_snapshot(initial)
            store.save_snapshot(version_two)
            latest, latest_source = load_snapshot_source(store_root=Path(temp) / "store", world_id="sync-cli-test")
            explicit, explicit_source = load_snapshot_source(
                store_root=Path(temp) / "store", world_id="sync-cli-test", version=1
            )
        self.assertEqual(2, latest["version"])
        self.assertEqual("store", latest_source["kind"])
        self.assertEqual("latest", latest_source["selection"])
        self.assertEqual(1, explicit["version"])
        self.assertEqual("explicit", explicit_source["selection"])

    def test_json_file_source_loads_snapshot(self):
        snapshot = _snapshot()
        with tempfile.TemporaryDirectory(prefix="stlat-sync-file-test-") as temp:
            path = Path(temp) / "snapshot.json"
            path.write_text(json.dumps(snapshot), encoding="utf-8")
            loaded, source = load_snapshot_source(snapshot_path=path)
        self.assertEqual(snapshot, loaded)
        self.assertEqual("file", source["kind"])

    def test_source_options_must_be_unambiguous(self):
        with self.assertRaises(BlenderSyncError):
            load_snapshot_source()
        with self.assertRaises(BlenderSyncError):
            load_snapshot_source(snapshot_path=Path("snapshot.json"), store_root=Path("store"))
        with self.assertRaises(BlenderSyncError):
            load_snapshot_source(store_root=Path("store"))
        with self.assertRaises(BlenderSyncError):
            load_snapshot_source(snapshot_path=Path("snapshot.json"), version=2)

    def test_missing_store_version_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="stlat-sync-missing-test-") as temp:
            with self.assertRaises(BlenderSyncError):
                load_snapshot_source(store_root=Path(temp) / "store", world_id="absent-world")


if __name__ == "__main__":
    unittest.main()
