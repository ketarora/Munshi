"""Append-only, hash-chained audit log.

This is tamper-evident, not a blockchain. Each entry hashes its content together
with the previous entry's hash, so editing or deleting a row is detectable.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Iterable

GENESIS = "0" * 64


def canonical(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def entry_hash(
    seq: int,
    ts: str,
    actor: str,
    event: str,
    payload: Any,
    prev_hash: str,
) -> str:
    material = "|".join(
        [str(seq), ts, actor, event, canonical(payload), prev_hash]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ChainStatus:
    ok: bool
    first_bad_seq: int | None = None
    entries: int = 0
    detail: str = ""


def verify_rows(rows: Iterable[dict[str, Any]]) -> ChainStatus:
    prev = GENESIS
    count = 0
    for row in rows:
        count += 1
        seq = int(row["seq"])
        expected = entry_hash(
            seq=seq,
            ts=row["ts"],
            actor=row["actor"],
            event=row["event"],
            payload=json.loads(row["payload_json"]),
            prev_hash=prev,
        )
        if row["prev_hash"] != prev or row["hash"] != expected:
            return ChainStatus(
                ok=False,
                first_bad_seq=seq,
                entries=count,
                detail=(
                    "prev_hash mismatch" if row["prev_hash"] != prev else "content hash mismatch"
                ),
            )
        prev = row["hash"]
    return ChainStatus(ok=True, entries=count)
