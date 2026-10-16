#!/usr/bin/env python3
"""Immutable, hash-verified persistence for versioned ST-LAT world snapshots."""
from __future__ import annotations
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from world_state_contract import validate_state, validate_transition
from world_state_replay import canonical_state_json

STORE_SCHEMA = "stlat.snapshot-store.v1"
_VERSION_FILE = re.compile(r"^v([0-9]{8})\.json$")


class SnapshotStoreError(ValueError):
    """Raised when a snapshot cannot be safely persisted or verified."""


class WorldStateStore:
    """Single-writer append-only snapshot store backed by standard-library JSON files.

    Each world receives a directory named by SHA-256(world_id), avoiding path
    traversal through world IDs. Versions are immutable and linked contiguously.
    Writes use a temporary file plus os.replace; this is not a multi-writer database.
    """
    def __init__(self, root: str | Path):
        self.root = Path(root)

    @staticmethod
    def _digest(state: dict[str, Any]) -> str:
        return hashlib.sha256(canonical_state_json(state).encode("utf-8")).hexdigest()

    def _world_dir(self, world_id: str) -> Path:
        if not isinstance(world_id, str) or not world_id.strip():
            raise SnapshotStoreError("world_id must be a non-empty string")
        key = hashlib.sha256(world_id.encode("utf-8")).hexdigest()
        return self.root / key

    def _snapshot_path(self, world_id: str, version: int) -> Path:
        return self._world_dir(world_id) / f"v{version:08d}.json"

    @staticmethod
    def _atomic_json(path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=path.parent,
                prefix=path.name + ".", suffix=".tmp", delete=False
            ) as handle:
                temporary = Path(handle.name)
                json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()

    def save_snapshot(self, snapshot: Any) -> Path:
        errors = validate_state(snapshot)
        if errors:
            raise SnapshotStoreError("invalid snapshot: " + "; ".join(errors))
        world_id, version = snapshot["world_id"], snapshot["version"]
        path = self._snapshot_path(world_id, version)
        digest = self._digest(snapshot)
        if path.exists():
            existing = self.load_snapshot(world_id, version)
            if self._digest(existing) == digest:
                return path
            raise SnapshotStoreError(f"snapshot version {version} is immutable and already exists")

        directory = self._world_dir(world_id)
        versions = []
        if directory.exists():
            for candidate in directory.iterdir():
                match = _VERSION_FILE.fullmatch(candidate.name)
                if match and candidate.is_file():
                    versions.append(int(match.group(1)))
        latest = max(versions, default=0)
        if latest == 0:
            if version != 1:
                raise SnapshotStoreError("first persisted snapshot must be version 1")
        else:
            if version != latest + 1:
                raise SnapshotStoreError(f"new snapshot version must be latest version {latest} + 1")
            previous = self.load_snapshot(world_id, latest)
            transition_errors = validate_transition(previous, snapshot)
            if transition_errors:
                raise SnapshotStoreError("snapshot transition invalid: " + "; ".join(transition_errors))

        envelope = {
            "store_schema": STORE_SCHEMA,
            "world_id": world_id,
            "version": version,
            "snapshot_sha256": digest,
            "snapshot": snapshot,
        }
        self._atomic_json(path, envelope)
        return path

    def load_snapshot(self, world_id: str, version: int) -> dict[str, Any]:
        path = self._snapshot_path(world_id, version)
        if not path.is_file():
            raise SnapshotStoreError(f"snapshot version {version} does not exist for this world")
        try:
            envelope = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SnapshotStoreError(f"cannot read snapshot file: {exc}") from exc
        if not isinstance(envelope, dict) or envelope.get("store_schema") != STORE_SCHEMA:
            raise SnapshotStoreError("unsupported or malformed snapshot envelope")
        snapshot = envelope.get("snapshot")
        if not isinstance(snapshot, dict):
            raise SnapshotStoreError("snapshot envelope must contain an object")
        try:
            digest = self._digest(snapshot)
        except (TypeError, ValueError) as exc:
            raise SnapshotStoreError(f"snapshot cannot be canonicalized: {exc}") from exc
        if envelope.get("snapshot_sha256") != digest:
            raise SnapshotStoreError("snapshot digest mismatch; stored content was modified or corrupted")
        if envelope.get("world_id") != world_id or envelope.get("version") != version:
            raise SnapshotStoreError("snapshot envelope world_id/version mismatch")
        errors = validate_state(snapshot)
        if errors:
            raise SnapshotStoreError("stored snapshot invalid: " + "; ".join(errors))
        if snapshot["world_id"] != world_id or snapshot["version"] != version:
            raise SnapshotStoreError("snapshot payload world_id/version mismatch")
        return snapshot

    def load_latest(self, world_id: str) -> dict[str, Any]:
        directory = self._world_dir(world_id)
        if not directory.is_dir():
            raise SnapshotStoreError("no snapshots exist for this world")
        versions = []
        for candidate in directory.iterdir():
            match = _VERSION_FILE.fullmatch(candidate.name)
            if match and candidate.is_file():
                versions.append(int(match.group(1)))
        if not versions:
            raise SnapshotStoreError("no snapshots exist for this world")
        return self.load_snapshot(world_id, max(versions))
