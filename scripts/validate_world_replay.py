#!/usr/bin/env python3
"""Run deterministic positive/negative world-event replay checks and persist JSON evidence."""
from __future__ import annotations
import copy
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from world_state_contract import AXES, validate_state
from world_state_replay import ReplayError, canonical_state_json, replay_events


def _entity(entity_id, role, position=None):
    position = position or [0.0, 0.0, 0.0]
    return {
        "id": entity_id, "role": role,
        "transform": {"position": position, "rotation_euler_rad": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
        "bounds": {"min": [-0.5, -0.5, 0.0], "max": [0.5, 0.5, 2.0], "kind": "aabb"},
        "persistence": "dynamic" if role.startswith("character") else "static",
        "collision": "none" if role.startswith("camera") else "solid",
        "attributes": {},
    }


def _snapshot():
    return {
        "schema": "stlat.world-state.v1", "world_id": "replay-self-test",
        "version": 1, "parent_version": None, "units": "meters", "axes": dict(AXES),
        "bounds": {"min": [-4.0, -4.0, 0.0], "max": [4.0, 4.0, 3.2]},
        "timestamp": 1.0,
        "entities": [_entity("char.001", "character", [0.0, 0.0, 0.0]), _entity("camera.main", "camera.main")],
        "events": [],
    }


def run_self_test(output_path: Path) -> dict:
    initial = _snapshot()
    events = [{
        "id": "evt-move-001", "type": "transform_updated", "timestamp": 2.0,
        "actor_id": "self-test", "target_id": "char.001", "approved": True,
        "payload": {
            "transform": {"position": [1.0, 0.0, 0.0], "rotation_euler_rad": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            "bounds": {"min": [0.5, -0.5, 0.0], "max": [1.5, 0.5, 2.0], "kind": "aabb"},
        },
    }]
    final_state = replay_events(initial, events)
    checks = {
        "valid_event_replayed": final_state["entities"][0]["transform"]["position"] == [1.0, 0.0, 0.0],
        "version_lineage_preserved": final_state["version"] == 2 and final_state["parent_version"] == 1,
        "final_snapshot_valid": validate_state(final_state) == [],
        "input_snapshot_unchanged": initial["version"] == 1 and initial["entities"][0]["transform"]["position"] == [0.0, 0.0, 0.0],
    }
    identity_initial = copy.deepcopy(initial)
    identity_initial["entities"][0]["identity_ref"] = "identity.original"
    identity_initial["entities"][0]["attributes"]["identity_signature"] = "sig-v1"
    identity_event = {
        "id": "evt-identity-001", "type": "identity_change_approved", "timestamp": 2.0,
        "actor_id": "self-test", "target_id": "char.001", "approved": True,
        "previous_identity_ref": "identity.original", "new_identity_ref": "identity.updated",
        "changed_identity_attributes": ["identity_signature"],
        "payload": {"attributes": {"identity_signature": "sig-v2"}},
    }
    identity_state = replay_events(identity_initial, [identity_event])
    checks["approved_identity_event_replayed"] = (
        identity_state["entities"][0]["identity_ref"] == "identity.updated"
        and identity_state["entities"][0]["attributes"]["identity_signature"] == "sig-v2"
    )
    role_event = {
        "id": "evt-role-001", "type": "entity_role_change_approved", "timestamp": 2.0,
        "actor_id": "self-test", "target_id": "char.001", "approved": True,
        "previous_role": "character", "new_role": "character.hero",
    }
    role_state = replay_events(initial, [role_event])
    checks["approved_role_event_replayed"] = role_state["entities"][0]["role"] == "character.hero"

    rejected = copy.deepcopy(events[0])
    rejected["id"], rejected["approved"] = "evt-unapproved-001", False
    try:
        replay_events(initial, [rejected])
        checks["unapproved_event_rejected"] = False
    except ReplayError:
        checks["unapproved_event_rejected"] = True
    unknown = copy.deepcopy(events[0])
    unknown["id"], unknown["type"] = "evt-unknown-001", "invented_action"
    try:
        replay_events(initial, [unknown])
        checks["unknown_event_rejected"] = False
    except ReplayError:
        checks["unknown_event_rejected"] = True
    report = {
        "schema": "stlat.world-state-replay-report.v1",
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks, "event_count": len(events), "final_version": final_state["version"],
        "final_state_sha256": hashlib.sha256(canonical_state_json(final_state).encode("utf-8")).hexdigest(),
        "limitations": [
            "Supported events: entity_created, entity_removed, transform_updated, entity_role_change_approved, identity_change_approved.",
            "Approval is an explicit event field, not cryptographic authorization.",
            "Replay is an in-memory JSON operation; it does not mutate Blender scenes or persist a database.",
        ],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not all(checks.values()):
        raise SystemExit("WORLD_EVENT_REPLAY_SELF_TEST=FAIL")
    print(f"WORLD_EVENT_REPLAY_SELF_TEST=PASS ({len(checks)} checks)")
    print(f"WORLD_EVENT_REPLAY_REPORT={output_path}")
    return report


if __name__ == "__main__":
    run_self_test(ROOT / "artifacts" / "stlat-world-state-replay.json")
