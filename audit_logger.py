import sqlite3
import json
import os
from datetime import datetime
from typing import List, Optional
from framework.models import AgentRun, FailureEvent


DB_PATH = os.environ.get("AUDIT_DB_PATH", "finagent_audit.db")


class AuditLogger:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_runs (
                    run_id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    task TEXT NOT NULL,
                    status TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    result TEXT,
                    total_tokens INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS failure_events (
                    event_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    failure_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    description TEXT NOT NULL,
                    raw_error TEXT,
                    context_snapshot TEXT,
                    recovery_action TEXT,
                    recovery_successful INTEGER,
                    post_mortem TEXT,
                    FOREIGN KEY (run_id) REFERENCES agent_runs(run_id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS injection_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    source TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    detected_patterns TEXT NOT NULL,
                    recommendation TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES agent_runs(run_id)
                )
            """)

    def _conn(self):
        return sqlite3.connect(self.db_path)

    def log_run_start(self, run: AgentRun):
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO agent_runs (run_id, agent_id, task, status, start_time, total_tokens) VALUES (?,?,?,?,?,?)",
                (run.run_id, run.agent_id, run.task, run.status, run.start_time, run.total_tokens),
            )

    def log_run_end(self, run: AgentRun):
        end_time = datetime.utcnow().isoformat()
        with self._conn() as conn:
            conn.execute(
                "UPDATE agent_runs SET status=?, end_time=?, result=?, total_tokens=? WHERE run_id=?",
                (run.status, end_time, run.result, run.total_tokens, run.run_id),
            )

    def log_failure(self, run_id: str, event: FailureEvent):
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO failure_events
                (event_id, run_id, agent_id, timestamp, failure_type, severity,
                 description, raw_error, context_snapshot, recovery_action,
                 recovery_successful, post_mortem)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    event.event_id,
                    run_id,
                    event.agent_id,
                    event.timestamp,
                    event.failure_type.value,
                    event.severity.value,
                    event.description,
                    event.raw_error,
                    json.dumps(event.context_snapshot) if event.context_snapshot else None,
                    event.recovery_action.value if event.recovery_action else None,
                    int(event.recovery_successful) if event.recovery_successful is not None else None,
                    event.post_mortem,
                ),
            )

    def log_injection(self, run_id: str, agent_id: str, source: str, confidence: float, patterns: List[str], recommendation: str):
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO injection_events
                (run_id, agent_id, timestamp, source, confidence, detected_patterns, recommendation)
                VALUES (?,?,?,?,?,?,?)""",
                (
                    run_id,
                    agent_id,
                    datetime.utcnow().isoformat(),
                    source,
                    confidence,
                    json.dumps(patterns),
                    recommendation,
                ),
            )

    def get_run_summary(self, run_id: str) -> Optional[dict]:
        with self._conn() as conn:
            conn.row_factory = sqlite3.Row
            run = conn.execute("SELECT * FROM agent_runs WHERE run_id=?", (run_id,)).fetchone()
            if not run:
                return None
            failures = conn.execute(
                "SELECT * FROM failure_events WHERE run_id=?", (run_id,)
            ).fetchall()
            injections = conn.execute(
                "SELECT * FROM injection_events WHERE run_id=?", (run_id,)
            ).fetchall()
            return {
                "run": dict(run),
                "failures": [dict(f) for f in failures],
                "injections": [dict(i) for i in injections],
            }

    def get_all_runs(self, limit: int = 50) -> List[dict]:
        with self._conn() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM agent_runs ORDER BY start_time DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_security_report(self) -> dict:
        with self._conn() as conn:
            total_injections = conn.execute("SELECT COUNT(*) FROM injection_events").fetchone()[0]
            critical_failures = conn.execute(
                "SELECT COUNT(*) FROM failure_events WHERE severity='critical'"
            ).fetchone()[0]
            by_type = conn.execute(
                "SELECT failure_type, COUNT(*) as count FROM failure_events GROUP BY failure_type"
            ).fetchall()
            return {
                "total_injection_attempts": total_injections,
                "critical_failures": critical_failures,
                "failures_by_type": {row[0]: row[1] for row in by_type},
            }
