#!/usr/bin/env python3
"""Explicit-approval transaction boundary between AI proposals and persisted ST-LAT state.

This module never calls the AI provider and never touches Blender directly. A trusted
caller must independently authorize the plan and provide evaluated post-transform
bounds from the geometry adapter. The store is single-writer; this is not a distributed
compare-and-swap or a multi-process lock.
"""
from __future__ import annotations

import copy
import math
from pathlib import Path
from typing import Any

from ai_world_planner import validate_plan
from world_state_replay import ReplayError, replay_events, canonical_state_json
from world_state_store import SnapshotStoreError, WorldStateStore
from world_state_contract import validate_state


class WorldTransactionError(ValueError):
    """Raised when an AI proposal cannot be committed as a world transaction."""


def commit_approved_transform(
    store_root: str | Path,
    *,
    expected_world_id: str,
    expected_version: int,
    plan: Any,
    target_bounds: Any,
    event_id: str,
    approved_by: str,
    timestamp: float,
) -> dict[str, Any]:
    """Validate one explicitly approved transform, replay it, then append one snapshot.

    `approved_by` must come from a trusted application/user approval gate, never from
    model output. `target_bounds` must be measured from evaluated geometry after a
    staged Blender application; this function cannot derive mesh bounds by itself.
    """
    if not isinstance(expected_world_id, str) or not expected_world_id.strip():
        raise WorldTransactionError("expected_world_id must be non-empty")
    if not isinstance(expected_version, int) or isinstance(expected_version, bool) or expected_version < 1:
        raise WorldTransactionError("expected_version must be a positive integer")
    if not isinstance(event_id, str) or not event_id.strip():
        raise WorldTransactionError("event_id must be non-empty")
    if not isinstance(approved_by, str) or not approved_by.strip():
        raise WorldTransactionError("explicit trusted approval (approved_by) is required")
    if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)) or not math.isfinite(timestamp) or timestamp < 0:
        raise WorldTransactionError("timestamp must be finite and non-negative")

    store = WorldStateStore(store_root)
    try:
        latest = store.load_latest(expected_world_id)
    except SnapshotStoreError as exc:
        raise WorldTransactionError(f"cannot load current world: {exc}") from exc
    if latest["world_id"] != expected_world_id:
        raise WorldTransactionError("world ID mismatch")
    if latest["version"] != expected_version:
        raise WorldTransactionError(
            f"stale proposal: expected version {expected_version}, current version is {latest['version']}"
        )
    if timestamp < latest["timestamp"]:
        raise WorldTransactionError("timestamp must not precede the current world timestamp")

    plan_errors = validate_plan(plan, {
        "world_id": latest["world_id"], "version": latest["version"],
        "units": latest["units"], "axes": latest["axes"], "bounds": latest["bounds"],
        "entities": latest["entities"],
    })
    if plan_errors:
        raise WorldTransactionError("proposal rejected: " + "; ".join(plan_errors))
    operations = plan["operations"]
    if len(operations) != 1:
        raise WorldTransactionError("transaction v1 accepts exactly one transform operation")
    operation = operations[0]
    target_id = operation["target_id"]
    entity = next((item for item in latest["entities"] if item["id"] == target_id), None)
    if entity is None:
        raise WorldTransactionError(f"target entity {target_id!r} no longer exists")
    transform = operation["transform"]
    if transform["rotation_euler_rad"] != entity["transform"]["rotation_euler_rad"]:
        raise WorldTransactionError("transaction v1 forbids rotation changes")
    if transform["scale"] != entity["transform"]["scale"]:
        raise WorldTransactionError("transaction v1 forbids scale changes")

    if not isinstance(target_bounds, dict) or target_bounds.get("kind") != "aabb":
        raise WorldTransactionError("target_bounds must be an evaluated AABB with kind='aabb'")
    if transform == entity["transform"] and target_bounds == entity["bounds"]:
        raise WorldTransactionError("no-op transform rejected")

    candidate = copy.deepcopy(latest)
    target = next(item for item in candidate["entities"] if item["id"] == target_id)
    target["transform"] = copy.deepcopy(transform)
    target["bounds"] = copy.deepcopy(target_bounds)
    state_errors = validate_state(candidate)
    if state_errors:
        raise WorldTransactionError("candidate state rejected: " + "; ".join(state_errors))

    event = {
        "id": event_id,
        "type": "transform_updated",
        "timestamp": float(timestamp),
        "actor_id": approved_by.strip(),
        "target_id": target_id,
        "approved": True,
        "payload": {
            "transform": copy.deepcopy(transform),
            "bounds": copy.deepcopy(target_bounds),
        },
        "reason": operation["reason"],
        "source": "approved_ai_plan",
        "approved_by": approved_by.strip(),
        "expected_version": expected_version,
    }
    try:
        replayed = replay_events(latest, [event])
    except ReplayError as exc:
        raise WorldTransactionError(f"event replay rejected; no snapshot committed: {exc}") from exc

    # Verify replay produced precisely the candidate state plus the expected event/version.
    if replayed["version"] != expected_version + 1 or replayed["parent_version"] != expected_version:
        raise WorldTransactionError("replay produced unexpected version lineage")
    replay_target = next(item for item in replayed["entities"] if item["id"] == target_id)
    if replay_target["transform"] != transform or replay_target["bounds"] != target_bounds:
        raise WorldTransactionError("replay read-back mismatch; no snapshot committed")
    if canonical_state_json(latest) == canonical_state_json(replayed):
        raise WorldTransactionError("no-op transaction rejected")

    try:
        path = store.save_snapshot(replayed)
        persisted = store.load_snapshot(expected_world_id, expected_version + 1)
    except SnapshotStoreError as exc:
        raise WorldTransactionError(f"persistence failed: {exc}") from exc
    if canonical_state_json(persisted) != canonical_state_json(replayed):
        raise WorldTransactionError("persisted read-back mismatch after append")
    return {
        "schema": "stlat.world-transaction-report.v1",
        "status": "committed",
        "world_id": expected_world_id,
        "previous_version": expected_version,
        "version": expected_version + 1,
        "event_id": event_id,
        "target_id": target_id,
        "approved_by": approved_by.strip(),
        "snapshot_path": str(path),
        "checks": {
            "explicit_approval_present": True,
            "expected_version_matches_latest": True,
            "proposal_schema_valid": True,
            "single_target_only": True,
            "rotation_and_scale_unchanged": True,
            "evaluated_aabb_supplied_and_validated": True,
            "approved_event_replayed": True,
            "version_lineage_valid": True,
            "persisted_readback_matches_replay": True,
        },
        "limitations": [
            "Caller must enforce authenticated human/system approval; approved_by is an audit label, not a cryptographic credential.",
            "Caller must stage and verify the Blender transform and supply evaluated AABB before calling this commit function.",
            "The snapshot store is single-writer; concurrent writers need an external lock or transactional database.",
            "This transaction does not itself mutate or save a .blend file.",
        ],
    }
