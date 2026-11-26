"""SQLite persistence. One connection guarded by a lock; all money is integer paise."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from typing import Any, Iterable

from .audit import GENESIS, ChainStatus, entry_hash, verify_rows
from .clock import Clock, SystemClock, iso
from .domain import TxnState
from .privacy import hash_phone

SCHEMA = """
CREATE TABLE IF NOT EXISTS families (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    child_token TEXT NOT NULL UNIQUE,
    timezone TEXT NOT NULL DEFAULT 'Asia/Kolkata',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    family_id TEXT NOT NULL REFERENCES families(id),
    role TEXT NOT NULL,
    display_name TEXT NOT NULL,
    phone_hash TEXT NOT NULL,
    channel_ids TEXT NOT NULL DEFAULT '{}'
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_phone ON users(phone_hash);

CREATE TABLE IF NOT EXISTS limits (
    family_id TEXT PRIMARY KEY REFERENCES families(id),
    per_txn_cap INTEGER NOT NULL,
    daily_cap INTEGER NOT NULL,
    monthly_cap INTEGER NOT NULL,
    hard_ceiling INTEGER NOT NULL,
    capabilities_enabled TEXT NOT NULL,
    allowlisted_payees TEXT NOT NULL,
    paused INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bills (
    id TEXT PRIMARY KEY,
    family_id TEXT NOT NULL,
    biller TEXT NOT NULL,
    account_no TEXT NOT NULL,
    amount_paise INTEGER NOT NULL,
    due_date TEXT NOT NULL,
    paid INTEGER NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_bills_family_biller ON bills(family_id, biller);

CREATE TABLE IF NOT EXISTS calls (
    id TEXT PRIMARY KEY,
    family_id TEXT,
    caller_hash TEXT,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    status TEXT NOT NULL,
    meta TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    call_id TEXT NOT NULL,
    idx INTEGER NOT NULL,
    asr_text TEXT NOT NULL,
    asr_confidence REAL NOT NULL,
    proposal_json TEXT NOT NULL,
    decision TEXT NOT NULL,
    spoken_reply TEXT NOT NULL,
    trace_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_turns_call ON turns(call_id, idx);

CREATE TABLE IF NOT EXISTS transactions (
    id TEXT PRIMARY KEY,
    family_id TEXT NOT NULL,
    call_id TEXT,
    idempotency_key TEXT NOT NULL UNIQUE,
    capability TEXT NOT NULL,
    resolved_action TEXT NOT NULL,
    amount_paise INTEGER,
    state TEXT NOT NULL,
    mode TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_txn_family ON transactions(family_id, created_at DESC);

CREATE TABLE IF NOT EXISTS approvals (
    id TEXT PRIMARY KEY,
    txn_id TEXT NOT NULL,
    family_id TEXT NOT NULL,
    state TEXT NOT NULL,
    summary TEXT NOT NULL,
    requested_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    decided_at TEXT,
    decided_by TEXT,
    channel TEXT
);

CREATE TABLE IF NOT EXISTS notifications (
    id TEXT PRIMARY KEY,
    family_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    kind TEXT NOT NULL,
    body TEXT NOT NULL,
    related_txn TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    actor TEXT NOT NULL,
    event TEXT NOT NULL,
    payload TEXT NOT NULL,
    prev_hash TEXT NOT NULL,
    hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pending_limits (
    token TEXT PRIMARY KEY,
    family_id TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS webhook_events (
    event_id TEXT PRIMARY KEY,
    received_at TEXT NOT NULL
);
"""


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


class Database:
    def __init__(self, path: str = ":memory:", clock: Clock | None = None) -> None:
        self.clock = clock or SystemClock()
        self._lock = threading.RLock()
        self.path = path
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        if path != ":memory:":
            self.conn.execute("PRAGMA journal_mode = WAL")
        self.init_schema()

    # ------------------------------------------------------------------ setup
    def init_schema(self) -> None:
        with self._lock:
            self.conn.executescript(SCHEMA)
            self.conn.commit()

    def close(self) -> None:
        with self._lock:
            self.conn.close()

    def reset(self) -> None:
        with self._lock:
            for table in (
                "webhook_events", "pending_limits", "audit_log", "notifications", "approvals",
                "transactions", "turns", "calls", "bills", "limits", "users", "families",
            ):
                self.conn.execute(f"DELETE FROM {table}")
            self.conn.execute("DELETE FROM sqlite_sequence")
            self.conn.commit()
        self.seed_demo()

    def seed_demo(self) -> None:
        now = iso(self.clock.now())
        families = [
            ("fam_devi", "Devi family", "demo-child-token"),
            ("fam_sharma", "Sharma family", "sharma-child-token"),
        ]
        with self._lock:
            for family_id, name, token in families:
                self.conn.execute(
                    "INSERT OR IGNORE INTO families(id, name, child_token, timezone, created_at) VALUES (?,?,?,?,?)",
                    (family_id, name, token, "Asia/Kolkata", now),
                )
            people = [
                ("usr_amma", "fam_devi", "parent", "Kamla Devi", hash_phone("9812345678")),
                ("usr_rohit", "fam_devi", "child", "Rohit", hash_phone("9898989898")),
                ("usr_sunita", "fam_sharma", "parent", "Sunita Sharma", hash_phone("9700000001")),
                ("usr_arjun", "fam_sharma", "child", "Arjun", hash_phone("9700000002")),
            ]
            for row in people:
                self.conn.execute(
                    "INSERT OR IGNORE INTO users(id, family_id, role, display_name, phone_hash, channel_ids) "
                    "VALUES (?,?,?,?,?,?)",
                    (*row, _json({"telegram": None, "whatsapp": None})),
                )
            limits_rows = [
                ("fam_devi", 200000, 300000, 500000, 500000,
                 _json(["pay_bill", "book_gas_cylinder", "refill_medicine", "message_child"]),
                 _json(["bijli", "gas", "dawai"]), 0, now),
                ("fam_sharma", 150000, 200000, 300000, 300000,
                 _json(["pay_bill", "message_child"]),
                 _json(["bijli"]), 0, now),
            ]
            for row in limits_rows:
                self.conn.execute(
                    "INSERT OR IGNORE INTO limits(family_id, per_txn_cap, daily_cap, monthly_cap, hard_ceiling, "
                    "capabilities_enabled, allowlisted_payees, paused, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                    row,
                )
            bills = [
                ("bill_bijli_devi", "fam_devi", "bijli", "BRPL-4471", 124000, "2026-11-27", 0),
                ("bill_paani_devi", "fam_devi", "paani", "DJB-2210", 75000, "2026-11-30", 0),
                ("bill_bijli_sharma", "fam_sharma", "bijli", "BRPL-9902", 98000, "2026-11-28", 0),
            ]
            for row in bills:
                self.conn.execute(
                    "INSERT OR IGNORE INTO bills(id, family_id, biller, account_no, amount_paise, due_date, paid) "
                    "VALUES (?,?,?,?,?,?,?)",
                    row,
                )
            self.conn.commit()

    def all_families(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self.conn.execute("SELECT * FROM families ORDER BY id").fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------ family
    def family(self, family_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self.conn.execute("SELECT * FROM families WHERE id = ?", (family_id,)).fetchone()
        return dict(row) if row else None

    def family_by_token(self, token: str) -> dict[str, Any] | None:
        with self._lock:
            row = self.conn.execute(
                "SELECT * FROM families WHERE child_token = ?", (token,)
            ).fetchone()
        return dict(row) if row else None

    def users(self, family_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM users WHERE family_id = ? ORDER BY role", (family_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    def user_by_phone_hash(self, phone_hash: str) -> dict[str, Any] | None:
        with self._lock:
            row = self.conn.execute(
                "SELECT * FROM users WHERE phone_hash = ?", (phone_hash,)
            ).fetchone()
        return dict(row) if row else None

    def child(self, family_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self.conn.execute(
                "SELECT * FROM users WHERE family_id = ? AND role = 'child'", (family_id,)
            ).fetchone()
        return dict(row) if row else None

    def limits(self, family_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self.conn.execute(
                "SELECT * FROM limits WHERE family_id = ?", (family_id,)
            ).fetchone()
        if not row:
            return None
        data = dict(row)
        data["capabilities_enabled"] = json.loads(data["capabilities_enabled"])
        data["allowlisted_payees"] = json.loads(data["allowlisted_payees"])
        data["paused"] = bool(data["paused"])
        return data

    def update_limits(self, family_id: str, **fields: Any) -> dict[str, Any]:
        allowed = {
            "per_txn_cap", "daily_cap", "monthly_cap", "hard_ceiling",
            "capabilities_enabled", "allowlisted_payees", "paused",
        }
        updates: dict[str, Any] = {}
        for key, value in fields.items():
            if key not in allowed:
                raise ValueError(f"cannot update limit field {key}")
            if key in {"capabilities_enabled", "allowlisted_payees"}:
                updates[key] = _json(value)
            elif key == "paused":
                updates[key] = 1 if value else 0
            else:
                updates[key] = int(value)
        updates["updated_at"] = iso(self.clock.now())
        assignments = ", ".join(f"{k} = ?" for k in updates)
        with self._lock:
            self.conn.execute(
                f"UPDATE limits SET {assignments} WHERE family_id = ?",
                (*updates.values(), family_id),
            )
            self.conn.commit()
        result = self.limits(family_id)
        assert result is not None
        return result

    # ------------------------------------------------------------------- bills
    def bill(self, family_id: str, biller: str) -> dict[str, Any] | None:
        with self._lock:
            row = self.conn.execute(
                "SELECT * FROM bills WHERE family_id = ? AND biller = ? AND paid = 0",
                (family_id, biller),
            ).fetchone()
        return dict(row) if row else None

    def list_bills(self, family_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM bills WHERE family_id = ? AND paid = 0 ORDER BY due_date", (family_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    def mark_bill_paid(self, bill_id: str) -> None:
        with self._lock:
            self.conn.execute("UPDATE bills SET paid = 1 WHERE id = ?", (bill_id,))
            self.conn.commit()

    # ------------------------------------------------------------------- calls
    def create_call(
        self,
        call_id: str,
        family_id: str | None,
        caller_hash: str | None,
        started_at: str,
        status: str,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            self.conn.execute(
                "INSERT INTO calls(id, family_id, caller_hash, started_at, status, meta) VALUES (?,?,?,?,?,?)",
                (call_id, family_id, caller_hash, started_at, status, _json(meta or {})),
            )
            self.conn.commit()
        return self.call(call_id)  # type: ignore[return-value]

    def call(self, call_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self.conn.execute("SELECT * FROM calls WHERE id = ?", (call_id,)).fetchone()
        if not row:
            return None
        data = dict(row)
        data["meta"] = json.loads(data["meta"])
        return data

    def active_call(self, family_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self.conn.execute(
                "SELECT * FROM calls WHERE family_id = ? AND status = 'active' ORDER BY started_at DESC LIMIT 1",
                (family_id,),
            ).fetchone()
        if not row:
            return None
        data = dict(row)
        data["meta"] = json.loads(data["meta"])
        return data

    def update_call(
        self,
        call_id: str,
        *,
        status: str | None = None,
        ended_at: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        fields: dict[str, Any] = {}
        if status is not None:
            fields["status"] = status
        if ended_at is not None:
            fields["ended_at"] = ended_at
        if meta is not None:
            fields["meta"] = _json(meta)
        if not fields:
            return
        assignments = ", ".join(f"{k} = ?" for k in fields)
        with self._lock:
            self.conn.execute(
                f"UPDATE calls SET {assignments} WHERE id = ?",
                (*fields.values(), call_id),
            )
            self.conn.commit()

    def list_calls(self, family_id: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        query = "SELECT * FROM calls"
        params: list[Any] = []
        if family_id:
            query += " WHERE family_id = ?"
            params.append(family_id)
        query += " ORDER BY started_at DESC LIMIT ?"
        params.append(limit)
        with self._lock:
            rows = self.conn.execute(query, params).fetchall()
        out = []
        for row in rows:
            data = dict(row)
            data["meta"] = json.loads(data["meta"])
            out.append(data)
        return out

    def add_turn(
        self,
        call_id: str,
        idx: int,
        asr_text: str,
        asr_confidence: float,
        proposal: dict[str, Any],
        decision: str,
        spoken_reply: str,
        trace: dict[str, Any],
        created_at: str,
    ) -> int:
        with self._lock:
            cur = self.conn.execute(
                "INSERT INTO turns(call_id, idx, asr_text, asr_confidence, proposal_json, decision, "
                "spoken_reply, trace_json, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (call_id, idx, asr_text, asr_confidence, _json(proposal), decision,
                 spoken_reply, _json(trace), created_at),
            )
            self.conn.commit()
            return int(cur.lastrowid)

    def turns(self, call_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM turns WHERE call_id = ? ORDER BY idx", (call_id,)
            ).fetchall()
        results = []
        for row in rows:
            data = dict(row)
            data["proposal"] = json.loads(data.pop("proposal_json"))
            data["trace"] = json.loads(data.pop("trace_json"))
            results.append(data)
        return results

    def turn_count(self, call_id: str) -> int:
        with self._lock:
            row = self.conn.execute(
                "SELECT COUNT(*) AS n FROM turns WHERE call_id = ?", (call_id,)
            ).fetchone()
        return int(row["n"])

    # -------------------------------------------------------------- money/txns
    def create_transaction(
        self,
        *,
        family_id: str,
        call_id: str | None,
        idempotency_key: str,
        capability: str,
        resolved_action: dict[str, Any],
        amount_paise: int | None,
        state: TxnState,
        mode: str,
        reason: str,
        created_at: str,
    ) -> dict[str, Any]:
        txn_id = f"txn_{uuid.uuid4().hex[:12]}"
        with self._lock:
            self.conn.execute(
                "INSERT OR IGNORE INTO transactions(id, family_id, call_id, idempotency_key, capability, "
                "resolved_action, amount_paise, state, mode, reason, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (txn_id, family_id, call_id, idempotency_key, capability,
                 _json(resolved_action), amount_paise, state.value, mode, reason, created_at, created_at),
            )
            self.conn.commit()
            row = self.conn.execute(
                "SELECT * FROM transactions WHERE idempotency_key = ?", (idempotency_key,)
            ).fetchone()
        assert row is not None
        return self._txn_row(row)

    def _txn_row(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["resolved_action"] = json.loads(data["resolved_action"])
        data["state_value"] = data["state"]
        return data

    def transaction(self, txn_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self.conn.execute(
                "SELECT * FROM transactions WHERE id = ?", (txn_id,)
            ).fetchone()
        return self._txn_row(row) if row else None

    def transaction_by_key(self, key: str) -> dict[str, Any] | None:
        with self._lock:
            row = self.conn.execute(
                "SELECT * FROM transactions WHERE idempotency_key = ?", (key,)
            ).fetchone()
        return self._txn_row(row) if row else None

    def set_transaction_state(
        self, txn_id: str, state: TxnState, *, reason: str | None = None, at: str | None = None
    ) -> None:
        fields = ["state = ?", "updated_at = ?"]
        params: list[Any] = [state.value, at or iso(self.clock.now())]
        if reason is not None:
            fields.append("reason = ?")
            params.append(reason)
        params.append(txn_id)
        with self._lock:
            self.conn.execute(
                f"UPDATE transactions SET {', '.join(fields)} WHERE id = ?", params
            )
            self.conn.commit()

    def transactions(
        self, family_id: str, *, states: Iterable[TxnState] | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM transactions WHERE family_id = ?"
        params: list[Any] = [family_id]
        if states is not None:
            values = [s.value for s in states]
            if not values:
                return []
            placeholders = ",".join("?" for _ in values)
            query += f" AND state IN ({placeholders})"
            params.extend(values)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self._lock:
            rows = self.conn.execute(query, params).fetchall()
        return [self._txn_row(r) for r in rows]

    def pending_readback(self, family_id: str) -> dict[str, Any] | None:
        rows = self.transactions(family_id, states=[TxnState.AWAITING_READBACK], limit=1)
        return rows[0] if rows else None

    def spend_between(self, family_id: str, start: str, end: str) -> int:
        with self._lock:
            row = self.conn.execute(
                "SELECT COALESCE(SUM(amount_paise), 0) AS total FROM transactions "
                "WHERE family_id = ? AND state = 'SUCCEEDED' AND updated_at >= ? AND updated_at < ?",
                (family_id, start, end),
            ).fetchone()
        return int(row["total"])

    def cancel_non_terminal(self, family_id: str, *, reason: str, at: str) -> list[str]:
        states = [
            TxnState.PROPOSED, TxnState.NEEDS_CLARIFICATION, TxnState.AWAITING_READBACK,
            TxnState.AWAITING_APPROVAL, TxnState.APPROVED,
        ]
        rows = self.transactions(family_id, states=states, limit=500)
        ids = [row["id"] for row in rows]
        if not ids:
            return []
        placeholders = ",".join("?" for _ in ids)
        with self._lock:
            self.conn.execute(
                f"UPDATE transactions SET state = 'CANCELLED', reason = ?, updated_at = ? "
                f"WHERE id IN ({placeholders})",
                (reason, at, *ids),
            )
            self.conn.execute(
                f"UPDATE approvals SET state = 'CANCELLED', decided_at = ? "
                f"WHERE family_id = ? AND state = 'PENDING'",
                (at, family_id),
            )
            self.conn.commit()
        return ids

    # --------------------------------------------------------------- approvals
    def create_approval(
        self,
        *,
        txn_id: str,
        family_id: str,
        summary: str,
        requested_at: str,
        expires_at: str,
    ) -> dict[str, Any]:
        approval_id = f"apr_{uuid.uuid4().hex[:12]}"
        with self._lock:
            self.conn.execute(
                "INSERT INTO approvals(id, txn_id, family_id, state, summary, requested_at, expires_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (approval_id, txn_id, family_id, "PENDING", summary, requested_at, expires_at),
            )
            self.conn.commit()
        return self.approval(approval_id)  # type: ignore[return-value]

    def approval(self, approval_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self.conn.execute(
                "SELECT * FROM approvals WHERE id = ?", (approval_id,)
            ).fetchone()
        return dict(row) if row else None

    def approval_for_txn(self, txn_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self.conn.execute(
                "SELECT * FROM approvals WHERE txn_id = ? ORDER BY requested_at DESC LIMIT 1", (txn_id,)
            ).fetchone()
        return dict(row) if row else None

    def approvals(self, family_id: str, state: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        query = "SELECT * FROM approvals WHERE family_id = ?"
        params: list[Any] = [family_id]
        if state:
            query += " AND state = ?"
            params.append(state)
        query += " ORDER BY requested_at DESC LIMIT ?"
        params.append(limit)
        with self._lock:
            rows = self.conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def set_approval_state(
        self,
        approval_id: str,
        state: str,
        *,
        decided_by: str | None = None,
        channel: str | None = None,
        at: str | None = None,
    ) -> None:
        with self._lock:
            self.conn.execute(
                "UPDATE approvals SET state = ?, decided_by = ?, channel = ?, decided_at = ? WHERE id = ?",
                (state, decided_by, channel, at, approval_id),
            )
            self.conn.commit()

    # ----------------------------------------------------------- notifications
    def add_notification(
        self,
        family_id: str,
        channel: str,
        kind: str,
        body: str,
        created_at: str,
        related_txn: str | None = None,
    ) -> dict[str, Any]:
        notification_id = f"ntf_{uuid.uuid4().hex[:12]}"
        with self._lock:
            self.conn.execute(
                "INSERT INTO notifications(id, family_id, channel, kind, body, related_txn, created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (notification_id, family_id, channel, kind, body, related_txn, created_at),
            )
            self.conn.commit()
        return {
            "id": notification_id, "family_id": family_id, "channel": channel,
            "kind": kind, "body": body, "related_txn": related_txn, "created_at": created_at,
        }

    def notifications(self, family_id: str, limit: int = 50, channel: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM notifications WHERE family_id = ?"
        params: list[Any] = [family_id]
        if channel:
            query += " AND channel = ?"
            params.append(channel)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self._lock:
            rows = self.conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    # ----------------------------------------------------------------- pending
    def put_pending_limits(self, token: str, family_id: str, payload: dict[str, Any], created_at: str) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO pending_limits(token, family_id, payload, created_at) VALUES (?,?,?,?)",
                (token, family_id, _json(payload), created_at),
            )
            self.conn.commit()

    def get_pending_limits(self, token: str) -> dict[str, Any] | None:
        with self._lock:
            row = self.conn.execute(
                "SELECT * FROM pending_limits WHERE token = ?", (token,)
            ).fetchone()
        if not row:
            return None
        data = dict(row)
        data["payload"] = json.loads(data["payload"])
        return data

    def delete_pending_limits(self, token: str) -> None:
        with self._lock:
            self.conn.execute("DELETE FROM pending_limits WHERE token = ?", (token,))
            self.conn.commit()

    # ---------------------------------------------------------------- webhooks
    def record_webhook_event(self, event_id: str, received_at: str) -> bool:
        """Return True if this event is new, False if it was already processed."""
        with self._lock:
            cur = self.conn.execute(
                "INSERT OR IGNORE INTO webhook_events(event_id, received_at) VALUES (?,?)",
                (event_id, received_at),
            )
            self.conn.commit()
            return cur.rowcount == 1

    # ------------------------------------------------------------------- audit
    def audit(self, actor: str, event: str, payload: dict[str, Any], ts: str | None = None) -> int:
        ts = ts or iso(self.clock.now())
        with self._lock:
            row = self.conn.execute(
                "SELECT seq, hash FROM audit_log ORDER BY seq DESC LIMIT 1"
            ).fetchone()
            prev = row["hash"] if row else GENESIS
            next_seq = (int(row["seq"]) + 1) if row else 1
            payload_json = _json(payload)
            digest = entry_hash(next_seq, ts, actor, event, json.loads(payload_json), prev)
            self.conn.execute(
                "INSERT INTO audit_log(seq, ts, actor, event, payload, prev_hash, hash) VALUES (?,?,?,?,?,?,?)",
                (next_seq, ts, actor, event, payload_json, prev, digest),
            )
            self.conn.commit()
        return next_seq

    def audit_rows(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self.conn.execute("SELECT * FROM audit_log ORDER BY seq").fetchall()
        out = []
        for row in rows:
            data = dict(row)
            data["payload_json"] = data.pop("payload")
            out.append(data)
        return out

    def verify_audit(self) -> ChainStatus:
        return verify_rows(self.audit_rows())
