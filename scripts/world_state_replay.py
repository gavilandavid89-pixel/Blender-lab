#!/usr/bin/env python3
"""Deterministic replay of approved events against versioned ST-LAT world snapshots."""
from __future__ import annotations
import copy
import json
import math
from typing import Any
from world_state_contract import IDENTITY_ATTRIBUTES, validate_state, validate_transition


class ReplayError(ValueError):
    """Raised when an event cannot be safely applied to the world state."""


SUPPORTED_EVENTS = {"entity_created", "entity_removed", "transform_updated", "entity_role_change_approved", "identity_change_approved", "entity_parent_change_approved"}


def replay_events(initial_state: Any, events: Any) -> dict[str, Any]:
    """Replay events in caller-supplied order; reject unsafe events without mutating inputs.

    Each approved event creates exactly one linked world version. Transform events
    must carry both the full transform and bounds so spatial metadata cannot go stale.
    """
    initial_errors = validate_state(initial_state)
    if initial_errors:
        raise ReplayError("invalid initial snapshot: " + "; ".join(initial_errors))
    if not isinstance(events, list):
        raise ReplayError("events must be an array")

    state = copy.deepcopy(initial_state)
    state.setdefault("events", [])
    seen_event_ids = {
        event["id"] for event in state["events"]
        if isinstance(event, dict) and isinstance(event.get("id"), str)
    }
    for index, raw_event in enumerate(events):
        prefix = f"events[{index}]"
        if not isinstance(raw_event, dict):
            raise ReplayError(f"{prefix} must be an object")
        event = copy.deepcopy(raw_event)
        event_id = event.get("id")
        if not isinstance(event_id, str) or not event_id.strip():
            raise ReplayError(f"{prefix}.id must be a non-empty string")
        if event_id in seen_event_ids:
            raise ReplayError(f"{prefix} duplicates event id {event_id!r}")
        event_type = event.get("type")
        if event_type not in SUPPORTED_EVENTS:
            raise ReplayError(f"{prefix}.type is unsupported: {event_type!r}")
        if event.get("approved") is not True:
            raise ReplayError(f"{prefix} must be explicitly approved")
        if "actor_id" not in event or (event["actor_id"] is not None and not isinstance(event["actor_id"], str)):
            raise ReplayError(f"{prefix}.actor_id must be a string or null")
        target_id = event.get("target_id")
        if not isinstance(target_id, str) or not target_id.strip():
            raise ReplayError(f"{prefix}.target_id must be a non-empty string")
        timestamp = event.get("timestamp")
        if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)) or not math.isfinite(timestamp):
            raise ReplayError(f"{prefix}.timestamp must be a finite non-negative number")
        if timestamp < state["timestamp"]:
            raise ReplayError(f"{prefix}.timestamp must be >= current state timestamp")
        if timestamp < 0:
            raise ReplayError(f"{prefix}.timestamp must be a finite non-negative number")
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            raise ReplayError(f"{prefix}.payload must be an object")

        before = copy.deepcopy(state)
        entities = {entity["id"]: entity for entity in state["entities"]}
        if event_type == "entity_created":
            entity = payload.get("entity")
            if not isinstance(entity, dict):
                raise ReplayError(f"{prefix}.payload.entity must be a complete entity object")
            if entity.get("id") != target_id:
                raise ReplayError(f"{prefix}.target_id must match payload.entity.id")
            if target_id in entities:
                raise ReplayError(f"{prefix} cannot create existing entity {target_id!r}")
            state["entities"].append(copy.deepcopy(entity))
        elif event_type == "entity_removed":
            if payload:
                raise ReplayError(f"{prefix}.payload must be empty for entity_removed")
            if target_id not in entities:
                raise ReplayError(f"{prefix} cannot remove missing entity {target_id!r}")
            state["entities"] = [entity for entity in state["entities"] if entity["id"] != target_id]
        elif event_type == "transform_updated":
            entity = entities.get(target_id)
            if entity is None:
                raise ReplayError(f"{prefix} target entity {target_id!r} does not exist")
            transform, bounds = payload.get("transform"), payload.get("bounds")
            if not isinstance(transform, dict) or not isinstance(bounds, dict):
                raise ReplayError(f"{prefix}.payload must include complete transform and bounds objects")
            entity["transform"] = copy.deepcopy(transform)
            entity["bounds"] = copy.deepcopy(bounds)
        elif event_type == "entity_role_change_approved":
            entity = entities.get(target_id)
            if entity is None:
                raise ReplayError(f"{prefix} target entity {target_id!r} does not exist")
            previous_role, new_role = event.get("previous_role"), event.get("new_role")
            if previous_role != entity.get("role"):
                raise ReplayError(f"{prefix}.previous_role does not match current entity role")
            if not isinstance(new_role, str) or not new_role.strip() or new_role == previous_role:
                raise ReplayError(f"{prefix}.new_role must be a different non-empty role")
            if payload:
                raise ReplayError(f"{prefix}.payload must be empty for entity_role_change_approved")
            entity["role"] = new_role
        elif event_type == "entity_parent_change_approved":
            entity = entities.get(target_id)
            if entity is None:
                raise ReplayError(f"{prefix} target entity {target_id!r} does not exist")
            if "previous_parent_id" not in event or "new_parent_id" not in event:
                raise ReplayError(f"{prefix} must declare previous_parent_id and new_parent_id")
            previous_parent, new_parent = event["previous_parent_id"], event["new_parent_id"]
            if previous_parent != entity.get("parent_id"):
                raise ReplayError(f"{prefix}.previous_parent_id does not match current parent")
            if new_parent is not None and (not isinstance(new_parent, str) or not new_parent.strip()):
                raise ReplayError(f"{prefix}.new_parent_id must be a non-empty string or null")
            if new_parent == target_id:
                raise ReplayError(f"{prefix} cannot parent an entity to itself")
            if new_parent is not None and new_parent not in entities:
                raise ReplayError(f"{prefix}.new_parent_id references a missing entity")
            if payload:
                raise ReplayError(f"{prefix}.payload must be empty for entity_parent_change_approved")
            if previous_parent == new_parent:
                raise ReplayError(f"{prefix} must change the parent relationship")
            if new_parent is None:
                entity.pop("parent_id", None)
            else:
                entity["parent_id"] = new_parent
        elif event_type == "identity_change_approved":
            entity = entities.get(target_id)
            if entity is None:
                raise ReplayError(f"{prefix} target entity {target_id!r} does not exist")
            if "previous_identity_ref" not in event or "new_identity_ref" not in event:
                raise ReplayError(f"{prefix} must declare previous_identity_ref and new_identity_ref")
            previous_ref, new_ref = event["previous_identity_ref"], event["new_identity_ref"]
            if previous_ref != entity.get("identity_ref"):
                raise ReplayError(f"{prefix}.previous_identity_ref does not match current identity")
            if new_ref is not None and not isinstance(new_ref, str):
                raise ReplayError(f"{prefix}.new_identity_ref must be a string or null")
            changed_attrs = event.get("changed_identity_attributes", [])
            if not isinstance(changed_attrs, list) or any(
                not isinstance(key, str) or key not in IDENTITY_ATTRIBUTES for key in changed_attrs
            ) or len(set(changed_attrs)) != len(changed_attrs):
                raise ReplayError(f"{prefix}.changed_identity_attributes contains unsupported or duplicate attributes")
            if set(payload) - {"attributes"}:
                raise ReplayError(f"{prefix}.payload only supports an attributes object")
            attribute_values = payload.get("attributes", {})
            if not isinstance(attribute_values, dict) or set(attribute_values) != set(changed_attrs):
                raise ReplayError(f"{prefix}.payload.attributes must exactly match changed_identity_attributes")
            identity_changed = previous_ref != new_ref
            if not identity_changed and not changed_attrs:
                raise ReplayError(f"{prefix} must change identity_ref or a protected identity attribute")
            attributes = entity.setdefault("attributes", {})
            for key in changed_attrs:
                if attributes.get(key) == attribute_values[key]:
                    raise ReplayError(f"{prefix} declares {key} changed but its value is unchanged")
                attributes[key] = copy.deepcopy(attribute_values[key])
            entity["identity_ref"] = new_ref

        state["version"] = before["version"] + 1
        state["parent_version"] = before["version"]
        state["timestamp"] = timestamp
        state.setdefault("events", []).append(event)
        state_errors = validate_state(state)
        if state_errors:
            raise ReplayError(f"{prefix} produced an invalid snapshot: " + "; ".join(state_errors))
        transition_errors = validate_transition(before, state)
        if transition_errors:
            raise ReplayError(f"{prefix} violates world transition contract: " + "; ".join(transition_errors))
        seen_event_ids.add(event_id)
    return state


def canonical_state_json(state: dict[str, Any]) -> str:
    """Canonical JSON representation for stable evidence hashes."""
    return json.dumps(state, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
