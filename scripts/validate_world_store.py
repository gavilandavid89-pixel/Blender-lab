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

        # Persist a longer approved event chain, reload every version, then replay
        # from the original disk snapshot and compare the exact canonical state.
        chain_initial = _snapshot()
        chain_initial["entities"].append(_entity("room.floor", "environment.floor"))
        move_event = {
            "id": "evt-chain-move", "type": "transform_updated", "timestamp": 2.0,
            "actor_id": "store-self-test", "target_id": "char.001", "approved": True,
            "payload": {
                "transform": {"position": [1.0, 0.0, 0.0], "rotation_euler_rad": [0.0, 0.0, 0.0],
                              "scale": [1.0, 1.0, 1.0]},
                "bounds": {"min": [0.5, -0.5, 0.0], "max": [1.5, 0.5, 2.0], "kind": "aabb"},
            },
        }
        parent_event = {
            "id": "evt-chain-parent", "type": "entity_parent_change_approved", "timestamp": 3.0,
            "actor_id": "store-self-test", "target_id": "char.001", "approved": True,
            "previous_parent_id": None, "new_parent_id": "room.floor", "payload": {},
        }
        identity_event = {
            "id": "evt-chain-identity", "type": "identity_change_approved", "timestamp": 4.0,
            "actor_id": "store-self-test", "target_id": "char.001", "approved": True,
            "previous_identity_ref": None, "new_identity_ref": "identity.vegeta",
            "changed_identity_attributes": ["identity_signature"],
            "payload": {"attributes": {"identity_signature": "sig-chain-v2"}},
        }
        chain_events = [move_event, parent_event, identity_event]
        chain_v2 = replay_events(chain_initial, chain_events[:1])
        chain_v3 = replay_events(chain_v2, chain_events[1:2])
        chain_v4 = replay_events(chain_v3, chain_events[2:])
        chain_store = WorldStateStore(Path(temp) / "chain-store")
        for version_state in (chain_initial, chain_v2, chain_v3, chain_v4):
            chain_store.save_snapshot(version_state)
        disk_v1 = chain_store.load_snapshot(chain_initial["world_id"], 1)
        disk_v2 = chain_store.load_snapshot(chain_initial["world_id"], 2)
        disk_v3 = chain_store.load_snapshot(chain_initial["world_id"], 3)
        disk_v4 = chain_store.load_snapshot(chain_initial["world_id"], 4)
        replayed_chain = replay_events(disk_v1, chain_events)
        loaded_latest = chain_store.load_latest(chain_initial["world_id"])
        checks["multi_event_chain_versions_linked"] = (
            [disk_v1["version"], disk_v2["version"], disk_v3["version"], disk_v4["version"]] == [1, 2, 3, 4]
            and [disk_v2["parent_version"], disk_v3["parent_version"], disk_v4["parent_version"]] == [1, 2, 3]
        )
        checks["multi_event_chain_replay_matches_persisted_latest"] = (
            canonical_state_json(replayed_chain) == canonical_state_json(disk_v4)
            == canonical_state_json(loaded_latest)
        )
        checks["multi_event_chain_preserves_parent_and_identity"] = (
            next(e for e in loaded_latest["entities"] if e["id"] == "char.001").get("parent_id") == "room.floor"
            and next(e for e in loaded_latest["entities"] if e["id"] == "char.001").get("identity_ref") == "identity.vegeta"
            and next(e for e in loaded_latest["entities"] if e["id"] == "char.001")["attributes"].get("identity_signature") == "sig-chain-v2"
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
        "multi_event_chain_versions_tested": [1, 2, 3, 4],
        "replayed_state_sha256": hashlib.sha256(canonical_state_json(replayed_from_disk).encode("utf-8")).hexdigest(),
        "persisted_latest_sha256": hashlib.sha256(canonical_state_json(latest_from_disk).encode("utf-8")).hexdigest(),
        "limitations": [
            "Single-writer local file store, not a concurrent database.",
            "SHA-256 detects accidental or uncoordinated modification; it is not a signature against an attacker who can rewrite both payload and digest.",
            "Stored snapshots are JSON world states; Blender scene synchronization is not implemented.",
            "Replay-after-reload now verifies a three-event chain across four persisted versions; this is still a bounded self-test, not a long-horizon event-sourcing service.",
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
