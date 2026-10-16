#!/usr/bin/env python3
"""Dependency-free contracts for versioned ST-LAT world snapshots and transitions."""
from __future__ import annotations
import math
from typing import Any

SCHEMA = "stlat.world-state.v1"
AXES = {"x": "right", "y": "depth_positive_toward_back_wall", "z": "up"}
PERSISTENCE = {"static", "dynamic", "ephemeral"}
COLLISION = {"solid", "trigger", "none"}
BOUND_KINDS = {"aabb", "obb", "capsule", "convex_hull", "mesh"}
IDENTITY_ATTRIBUTES = ("identity_signature", "asset_id", "appearance_id")


def _vector3(value: Any) -> bool:
    return isinstance(value, list) and len(value) == 3 and all(
        isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in value
    )


def _approved_event(state: dict[str, Any], event_type: str, entity_id: str) -> dict[str, Any] | None:
    events = state.get("events", [])
    if not isinstance(events, list):
        return None
    return next((event for event in events if isinstance(event, dict)
                 and event.get("type") == event_type and event.get("target_id") == entity_id
                 and event.get("approved") is True), None)


def validate_state(state: Any) -> list[str]:
    """Validate invariants needed for safe comparison; no external JSON Schema dependency."""
    errors: list[str] = []
    if not isinstance(state, dict):
        return ["root must be a JSON object"]
    if state.get("schema") != SCHEMA:
        errors.append(f"schema must equal {SCHEMA}")
    if not isinstance(state.get("world_id"), str) or not state["world_id"].strip():
        errors.append("world_id must be a non-empty string")
    version = state.get("version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        errors.append("version must be a positive integer")
    parent = state.get("parent_version")
    if parent is not None and (not isinstance(parent, int) or isinstance(parent, bool) or parent < 1):
        errors.append("parent_version must be null or a positive integer")
    if isinstance(version, int) and not isinstance(version, bool):
        if version == 1 and parent is not None:
            errors.append("version 1 must have parent_version=null")
        elif version > 1 and parent != version - 1:
            errors.append("parent_version must equal version-1")
    if state.get("units") != "meters":
        errors.append("units must equal meters")
    if state.get("axes") != AXES:
        errors.append("axes must match the canonical ST-LAT axis convention")
    timestamp = state.get("timestamp")
    if not isinstance(timestamp, (int, float)) or isinstance(timestamp, bool) or not math.isfinite(timestamp) or timestamp < 0:
        errors.append("timestamp must be a finite non-negative number")
    bounds = state.get("bounds")
    if not isinstance(bounds, dict) or not _vector3(bounds.get("min")) or not _vector3(bounds.get("max")):
        errors.append("bounds must contain finite min/max vector3 values")
    elif any(bounds["min"][i] > bounds["max"][i] for i in range(3)):
        errors.append("bounds min must not exceed max")

    entities = state.get("entities")
    if not isinstance(entities, list):
        errors.append("entities must be an array")
        entities = []
    seen: set[str] = set()
    for index, entity in enumerate(entities):
        prefix = f"entities[{index}]"
        if not isinstance(entity, dict):
            errors.append(f"{prefix} must be an object")
            continue
        entity_id = entity.get("id")
        if not isinstance(entity_id, str) or not entity_id.strip():
            errors.append(f"{prefix}.id must be a non-empty string")
        elif entity_id in seen:
            errors.append(f"duplicate entity id: {entity_id}")
        else:
            seen.add(entity_id)
        if not isinstance(entity.get("role"), str) or not entity["role"].strip():
            errors.append(f"{prefix}.role must be a non-empty string")
        transform = entity.get("transform")
        if not isinstance(transform, dict):
            errors.append(f"{prefix}.transform must be an object")
        else:
            for key in ("position", "rotation_euler_rad", "scale"):
                if not _vector3(transform.get(key)):
                    errors.append(f"{prefix}.transform.{key} must be a finite vector3")
            scale = transform.get("scale")
            if _vector3(scale) and any(v <= 0 for v in scale):
                errors.append(f"{prefix}.transform.scale values must be positive")
            position = transform.get("position")
            if (_vector3(position) and isinstance(bounds, dict)
                    and _vector3(bounds.get("min")) and _vector3(bounds.get("max"))
                    and not any(bounds["min"][i] > bounds["max"][i] for i in range(3))
                    and isinstance(entity.get("role"), str)
                    and not entity["role"].lower().startswith("camera")
                    and any(position[i] < bounds["min"][i] or position[i] > bounds["max"][i] for i in range(3))):
                errors.append(f"{prefix}.transform.position exceeds hard world bounds")
        eb = entity.get("bounds")
        if not isinstance(eb, dict):
            errors.append(f"{prefix}.bounds must be an object")
        else:
            if not _vector3(eb.get("min")) or not _vector3(eb.get("max")):
                errors.append(f"{prefix}.bounds min/max must be finite vector3 values")
            elif any(eb["min"][i] > eb["max"][i] for i in range(3)):
                errors.append(f"{prefix}.bounds min must not exceed max")
            elif (isinstance(bounds, dict) and _vector3(bounds.get("min")) and _vector3(bounds.get("max"))
                  and not any(bounds["min"][i] > bounds["max"][i] for i in range(3))
                  and isinstance(entity.get("role"), str)
                  and not entity["role"].lower().startswith("camera")
                  and any(eb["min"][i] < bounds["min"][i] or eb["max"][i] > bounds["max"][i] for i in range(3))):
                errors.append(f"{prefix}.bounds exceed hard world bounds")
            if eb.get("kind") not in BOUND_KINDS:
                errors.append(f"{prefix}.bounds.kind is unsupported")
        if entity.get("persistence") not in PERSISTENCE:
            errors.append(f"{prefix}.persistence is unsupported")
        if entity.get("collision") not in COLLISION:
            errors.append(f"{prefix}.collision is unsupported")
        if "identity_ref" in entity and entity["identity_ref"] is not None and not isinstance(entity["identity_ref"], str):
            errors.append(f"{prefix}.identity_ref must be a string or null")
        if "attributes" in entity and not isinstance(entity["attributes"], dict):
            errors.append(f"{prefix}.attributes must be an object")

    # Parent links are structural references within this snapshot; reject dangling links and cycles.
    entity_map = {
        entity["id"]: entity for entity in entities
        if isinstance(entity, dict) and isinstance(entity.get("id"), str) and entity.get("id")
    }
    for index, entity in enumerate(entities):
        if not isinstance(entity, dict):
            continue
        parent_id = entity.get("parent_id")
        entity_id = entity.get("id")
        if parent_id is not None and (not isinstance(parent_id, str) or not parent_id.strip()):
            errors.append(f"entities[{index}].parent_id must be a non-empty string or null")
        elif isinstance(parent_id, str):
            if parent_id == entity_id:
                errors.append(f"entity {entity_id} cannot be its own parent")
            elif parent_id not in entity_map:
                errors.append(f"entity {entity_id} references missing parent {parent_id}")

    reported_cycles: set[frozenset[str]] = set()
    for start_id in entity_map:
        path: list[str] = []
        positions: dict[str, int] = {}
        cursor = start_id
        while cursor in entity_map:
            if cursor in positions:
                cycle_nodes = path[positions[cursor]:]
                cycle_key = frozenset(cycle_nodes)
                if cycle_key not in reported_cycles:
                    errors.append("parent hierarchy contains a cycle: " + " -> ".join(cycle_nodes + [cursor]))
                    reported_cycles.add(cycle_key)
                break
            positions[cursor] = len(path)
            path.append(cursor)
            parent_id = entity_map[cursor].get("parent_id")
            if not isinstance(parent_id, str) or parent_id not in entity_map:
                break
            cursor = parent_id

    events = state.get("events", [])
    if not isinstance(events, list):
        errors.append("events must be an array when provided")
    else:
        event_ids: set[str] = set()
        for index, event in enumerate(events):
            if not isinstance(event, dict):
                errors.append(f"events[{index}] must be an object")
                continue
            event_id = event.get("id")
            if not isinstance(event_id, str) or not event_id.strip():
                errors.append(f"events[{index}].id must be a non-empty string")
            elif event_id in event_ids:
                errors.append(f"duplicate event id: {event_id}")
            else:
                event_ids.add(event_id)
            if not isinstance(event.get("type"), str) or not event["type"].strip():
                errors.append(f"events[{index}].type must be a non-empty string")
            ts = event.get("timestamp")
            if not isinstance(ts, (int, float)) or isinstance(ts, bool) or not math.isfinite(ts) or ts < 0:
                errors.append(f"events[{index}].timestamp must be finite and non-negative")
            if "actor_id" not in event or (event["actor_id"] is not None and not isinstance(event["actor_id"], str)):
                errors.append(f"events[{index}].actor_id must be a string or null")
    return errors


def validate_transition(previous: Any, current: Any) -> list[str]:
    """Check version lineage, approved entity lifecycle, and protected identity continuity."""
    errors = [f"previous: {e}" for e in validate_state(previous)]
    errors.extend(f"current: {e}" for e in validate_state(current))
    if errors:
        return errors
    if previous["world_id"] != current["world_id"]:
        errors.append("world_id cannot change across a transition")
    if current["version"] != previous["version"] + 1:
        errors.append("current version must be previous version + 1")
    if current.get("parent_version") != previous["version"]:
        errors.append("current parent_version must reference previous version")
    before = {e["id"]: e for e in previous["entities"]}
    after = {e["id"]: e for e in current["entities"]}
    for entity_id in sorted(after.keys() - before.keys()):
        if _approved_event(current, "entity_created", entity_id) is None:
            errors.append(f"new entity {entity_id} requires an approved entity_created event")
    for entity_id in sorted(before.keys() - after.keys()):
        if _approved_event(current, "entity_removed", entity_id) is None:
            errors.append(f"removed entity {entity_id} requires an approved entity_removed event")
    for entity_id in sorted(before.keys() & after.keys()):
        old, new = before[entity_id], after[entity_id]
        if old.get("role") != new.get("role"):
            event = _approved_event(current, "entity_role_change_approved", entity_id)
            if event is None or event.get("previous_role") != old.get("role") or event.get("new_role") != new.get("role"):
                errors.append(f"entity {entity_id} role changed without matching approved event")
        old_attrs, new_attrs = old.get("attributes", {}), new.get("attributes", {})
        protected_changed = old.get("identity_ref") != new.get("identity_ref")
        changed_attrs = {key for key in IDENTITY_ATTRIBUTES if old_attrs.get(key) != new_attrs.get(key)}
        if protected_changed or changed_attrs:
            event = _approved_event(current, "identity_change_approved", entity_id)
            matches = event is not None
            if matches and protected_changed:
                matches = (event.get("previous_identity_ref") == old.get("identity_ref")
                           and event.get("new_identity_ref") == new.get("identity_ref"))
            if matches and changed_attrs:
                approved_attrs = event.get("changed_identity_attributes", [])
                matches = isinstance(approved_attrs, list) and changed_attrs.issubset(set(approved_attrs))
            if not matches:
                changed = sorted(changed_attrs | ({"identity_ref"} if protected_changed else set()))
                errors.append(f"entity {entity_id} protected identity changed without matching approved event: {changed}")
    return errors


def validate_camera_isolation(previous: Any, current: Any) -> list[str]:
    """Require a camera change while all non-camera entities remain byte-for-byte equivalent."""
    errors = [f"previous: {e}" for e in validate_state(previous)]
    errors.extend(f"current: {e}" for e in validate_state(current))
    if errors:
        return errors
    if previous["world_id"] != current["world_id"]:
        errors.append("world_id cannot change for a camera-only operation")
    if current["version"] != previous["version"] + 1 or current.get("parent_version") != previous["version"]:
        errors.append("camera-only operation must create the next linked world version")
    def split(state: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        cameras, world = {}, {}
        for entity in state["entities"]:
            role = entity.get("role", "")
            (cameras if isinstance(role, str) and role.lower().startswith("camera") else world)[entity["id"]] = entity
        return cameras, world
    old_cameras, old_world = split(previous)
    new_cameras, new_world = split(current)
    if old_world != new_world:
        errors.append("camera-only operation modified non-camera world entities")
    if old_cameras == new_cameras:
        errors.append("camera-only operation did not change any camera entity")
    return errors
