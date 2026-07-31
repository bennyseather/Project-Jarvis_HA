"""Persistent, bounded accounting for external AI usage."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock


@dataclass(frozen=True, slots=True)
class AIBudgetPolicy:
    monthly_limit_usd: float = 10.0
    warning_thresholds: tuple[float, ...] = (0.7, 0.9)
    hard_limit: bool = True

    @classmethod
    def from_config(cls, value):
        config = {} if value is None else value
        if not isinstance(config, dict):
            raise ValueError("ai_budget must be a mapping")
        limit = config.get("monthly_limit_usd", 10.0)
        hard = config.get("hard_limit", True)
        thresholds = tuple(config.get("warning_thresholds", (0.7, 0.9)))
        if not isinstance(limit, (int, float)) or isinstance(limit, bool) or limit <= 0:
            raise ValueError("ai_budget.monthly_limit_usd must be positive")
        if not isinstance(hard, bool):
            raise ValueError("ai_budget.hard_limit must be a boolean")
        if not thresholds or any(
            not isinstance(item, (int, float)) or not 0 < item < 1
            for item in thresholds
        ):
            raise ValueError("ai_budget.warning_thresholds must be between 0 and 1")
        return cls(float(limit), tuple(sorted(set(float(item) for item in thresholds))), hard)


class SQLiteAIUsageLedger:
    """Store cost totals without storing prompts or response content."""

    def __init__(self, database_path, policy: AIBudgetPolicy, *, clock=None):
        self.policy = policy
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = RLock()
        self._connection = sqlite3.connect(database_path, check_same_thread=False)
        self._connection.execute(
            """CREATE TABLE IF NOT EXISTS ai_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                occurred_at TEXT NOT NULL,
                month TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                input_tokens INTEGER NOT NULL,
                output_tokens INTEGER NOT NULL,
                estimated_cost_usd REAL NOT NULL
            )"""
        )
        self._connection.commit()

    def month_total(self) -> float:
        month = self._clock().strftime("%Y-%m")
        row = self._connection.execute(
            "SELECT COALESCE(SUM(estimated_cost_usd), 0) FROM ai_usage WHERE month = ?",
            (month,),
        ).fetchone()
        return float(row[0])

    def permitted(self, estimated_cost_usd: float = 0.0) -> bool:
        return not self.policy.hard_limit or (
            self.month_total() + max(0.0, estimated_cost_usd)
            <= self.policy.monthly_limit_usd
        )

    def record(self, provider, model, input_tokens, output_tokens, cost_usd):
        now = self._clock()
        with self._lock:
            self._connection.execute(
                """INSERT INTO ai_usage (
                    occurred_at, month, provider, model, input_tokens,
                    output_tokens, estimated_cost_usd
                ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    now.isoformat(), now.strftime("%Y-%m"), provider, model,
                    max(0, int(input_tokens)), max(0, int(output_tokens)),
                    max(0.0, float(cost_usd)),
                ),
            )
            self._connection.commit()

    def status(self):
        used = self.month_total()
        limit = self.policy.monthly_limit_usd
        ratio = used / limit
        warning = next(
            (threshold for threshold in reversed(self.policy.warning_thresholds)
             if ratio >= threshold),
            None,
        )
        return {
            "used_usd": used,
            "limit_usd": limit,
            "remaining_usd": max(0.0, limit - used),
            "ratio": ratio,
            "warning_threshold": warning,
            "blocked": self.policy.hard_limit and used >= limit,
        }

    def close(self):
        self._connection.close()
