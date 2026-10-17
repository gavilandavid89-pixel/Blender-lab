#!/usr/bin/env python3
"""Self-test persistent snapshot storage and write a machine-readable evidence report."""
from __future__ import annotations
import copy
import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from world_state_contract import AXES
from world_state_replay import ReplayError, canonical_state_json, replay_events
from world_state_store import SnapshotStoreError, WorldStateStore


def _entity(entity_id, role, position=None):
    return {
        "id": entity_id, "role": role,
        "transform": {"position": position or [0.0, 0.0, 0.0], "rotation_euler_rad": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
        "bounds": {"min": [-0.5, -0.5, 0.0], "max": [0.5, 0.5, 2.0], "kind": "aabb"},
        "persistence": "dynamic" if role.startswith("character") else "static",
        "collision": "none" if role.startswith("camera") else "solid",
        "attributes": {},
    }


def _snapshot():
    return {
        "schema": "stlat.world-state.v1", "world_id": "store-self-test",
        "version": 1, "parent_version": None, "units": "meters", "axes": dict(AXES),
        "bounds": {"min": [-4.0, -4.0, 0.0], "max": [4.0, 4.0, 3.2]},
        "timestamp": 1.0,
        "entities": [_entity("char.001", "character"), _entity("camera.main", "camera.main")],
        "events": [],
    }


def run_self_test(output_path: Path) -> dict:
    initial = _snapshot()
    event = {
        "id": "evt-move-store-001", "type": "transform_updated", "timestamp": 2.0,
        "actor_id": "store-self-test", "target_id": "char.001", "approved": True,
        "payload": {
            "transform": {"position": [1.0, 0.0, 0.0], "rotation_euler_rad": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            "bounds": {"min": [0.5, -0.5, 0.0], "max": [1.5, 0.5, 2.0], "kind": "aabb"},
        },
    }
    version_two = replay_events(initial, [event])
    checks = {}
    with tempfile.TemporaryDirectory(prefix="stlat-store-test-") as temp:
        store = WorldStateStore(Path(temp) / "store")
        store.save_snapshot(initial)
        store.save_snapshot(version_two)
        restored_initial = store.load_snapshot(initial["world_id"], 1)
        restored_final = store.load_snapshot(initial["world_id"], 2)
        replayed_from_disk = replay_events(restored_initial, [event])
        latest_from_disk = store.load_latest(initial["world_id"])
        checks["snapshot_round_trip"] = restored_initial == initial
        checks["latest_version_loaded"] = latest_from_disk == version_two
        checks["linked_versions_persisted"] = restored_final["parent_version"] == 1
        checks["idempotent_save_is_safe"] = store.save_snapshot(version_two).name == "v00000002.json"
        checks["replay_after_reload_matches_persisted_version"] = (
            canonical_state_json(replayed_from_disk) == canonical_state_json(restored_final)
        )
        checks["replay_after_reload_matches_latest_history"] = (
            canonical_state_json(replayed_from_disk) == canonical_state_json(latest_from_disk)
        )

        gap_store = WorldStateStore(Path(temp) / "gap-store")
        first_path = gap_store.save_snapshot(initial)
        gap_store.save_snapshot(version_two)
        first_path.unlink()
        try:
            gap_store.load_latest(initial["world_id"])
            checks["missing_history_version_rejected"] = False
        except SnapshotStoreError:
            checks["missing_history_version_rejected"] = True

        altered = copy.deepcopy(version_two)
        altered["timestamp"] = 2.5
        try:
            store.save_snapshot(altered)
            checks["persisted_versions_immutable"] = False
        except SnapshotStoreError:
            checks["persisted_versions_immutable"] = True

        skipped = copy.deepcopy(version_two)
        skipped["version"], skipped["parent_version"], skipped["timestamp"] = 4, 3, 4.0
        try:
            store.save_snapshot(skipped)
            checks["version_gaps_rejected"] = False
        except SnapshotStoreError:
            checks["version_gaps_rejected"] = True

        tamper_store = WorldStateStore(Path(temp) / "tamper-store")
        tamper_path = tamper_store.save_snapshot(initial)
        envelope = json.loads(tamper_path.read_text(encoding="utf-8"))
        envelope["snapshot"]["timestamp"] = 99.0
        tamper_path.write_text(json.dumps(envelope), encoding="utf-8")
        try:
            tamper_store.load_snapshot(initial["world_id"], 1)
            checks["tampering_detected"] = False
        except SnapshotStoreError:
            checks["tampering_detected"] = True

    report = {
        "schema": "stlat.world-state-store-report.v1",
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "check_count": len(checks),
        "persisted_versions_tested": [1, 2],
        "replayed_state_sha256": hashlib.sha256(canonical_state_json(replayed_from_disk).encode("utf-8")).hexdigest(),
        "persisted_latest_sha256": hashlib.sha256(canonical_state_json(latest_from_disk).encode("utf-8")).hexdigest(),
        "limitations": [
            "Single-writer local file store, not a concurrent database.",
            "SHA-256 detects accidental or uncoordinated modification; it is not a signature against an attacker who can rewrite both payload and digest.",
            "Stored snapshots are JSON world states; Blender scene synchronization is not implemented.",
            "Replay-after-reload verifies a single transform event and one persisted transition; this is not yet a long-horizon event-sourcing service.",
        ],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not all(checks.values()):
        raise SystemExit("WORLD_STATE_STORE_SELF_TEST=FAIL")
    print(f"WORLD_STATE_STORE_SELF_TEST=PASS ({len(checks)} checks)")
    print(f"WORLD_STATE_STORE_REPORT={output_path}")
    return report


if __name__ == "__main__":
    run_self_test(ROOT / "artifacts" / "stlat-world-state-store.json")
