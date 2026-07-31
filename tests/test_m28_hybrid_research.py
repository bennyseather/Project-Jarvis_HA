import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from jarvis.ai_budget import AIBudgetPolicy, SQLiteAIUsageLedger
from jarvis.hybrid_research import HybridResearchPolicy, HybridResearchProvider
from jarvis.research import ResearchController, ResearchPolicy


class Reasoning:
    def __init__(self, outcomes=None):
        self.calls = []
        self.outcomes = list(outcomes or ())

    def reason(self, **request):
        self.calls.append(request)
        if self.outcomes:
            return self.outcomes.pop(0)
        return {"status": "success", "message": "Evidence-based answer."}


class Search:
    def research(self, query):
        return ({
            "title": "Primary",
            "url": "https://example.com/source",
            "snippet": "Relevant evidence",
        },)


class Ledger:
    def __init__(self, permitted=True):
        self.allowed = permitted

    def permitted(self, estimate=0):
        return self.allowed

    def status(self):
        return {
            "used_usd": 0.0,
            "limit_usd": 10.0,
            "remaining_usd": 10.0,
            "ratio": 0.0,
            "warning_threshold": None,
            "blocked": False,
        }


class M28HybridResearchTests(unittest.TestCase):
    def test_policy_validates_search_and_budget_bounds(self):
        search = HybridResearchPolicy.from_config({
            "searxng_url": "http://homeassistant.local:8088/search",
            "maximum_results": 4,
            "maximum_pages": 2,
        })
        self.assertEqual(search.normal_model, "gpt-5.6-luna")
        budget = AIBudgetPolicy.from_config({
            "monthly_limit_usd": 10,
            "warning_thresholds": [0.7, 0.9],
            "hard_limit": True,
        })
        self.assertEqual(budget.monthly_limit_usd, 10)
        with self.assertRaises(ValueError):
            HybridResearchPolicy.from_config({"maximum_pages": 6})

    def test_local_search_evidence_is_synthesised_with_luna(self):
        reasoning = Reasoning()
        provider = HybridResearchProvider(
            reasoning, Search(), HybridResearchPolicy(), Ledger()
        )
        result = provider.answer("current topic", {"memory": (), "knowledge": ()})
        self.assertEqual(result["status"], "success")
        self.assertEqual(reasoning.calls[0]["model"], "gpt-5.6-luna")
        self.assertEqual(result["sources"][0]["url"], "https://example.com/source")

    def test_failed_luna_escalates_once_to_terra_and_premium_is_explicit(self):
        reasoning = Reasoning([
            {"status": "unavailable", "message": "failed"},
            {"status": "success", "message": "recovered"},
        ])
        provider = HybridResearchProvider(
            reasoning, Search(), HybridResearchPolicy(), Ledger()
        )
        result = provider.answer("compare sources", {})
        self.assertEqual(result["message"], "recovered")
        self.assertEqual(
            [call["model"] for call in reasoning.calls],
            ["gpt-5.6-luna", "gpt-5.6-terra"],
        )
        reasoning.calls.clear()
        provider.answer("Use highest quality reasoning", {})
        self.assertEqual(reasoning.calls[0]["model"], "gpt-5.6-sol")

    def test_budget_blocks_external_reasoning_but_keeps_sources(self):
        reasoning = Reasoning()
        provider = HybridResearchProvider(
            reasoning, Search(), HybridResearchPolicy(), Ledger(False)
        )
        result = provider.answer("current topic", {})
        self.assertEqual(result["status"], "budget_exceeded")
        self.assertFalse(reasoning.calls)
        self.assertTrue(result["sources"])

    def test_usage_ledger_persists_only_metadata_and_exposes_budget_command(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "jarvis.sqlite3"
            clock = lambda: datetime(2026, 7, 31, tzinfo=timezone.utc)
            ledger = SQLiteAIUsageLedger(
                path, AIBudgetPolicy(1.0, (0.7, 0.9), True), clock=clock
            )
            ledger.record("openai", "gpt-5.6-luna", 1000, 100, 0.0016)
            result = ResearchController(
                ResearchPolicy(), SimpleNamespace(), SimpleNamespace(), ledger
            ).handle("show AI usage", "one")
            self.assertEqual(result["status"], "success")
            self.assertIn("$0.00 of the $1.00 budget", result["message"])
            columns = {
                row[1] for row in ledger._connection.execute("PRAGMA table_info(ai_usage)")
            }
            self.assertNotIn("prompt", columns)
            self.assertNotIn("response", columns)
            ledger.close()

    def test_runtime_mirror_and_search_addon_are_packaged(self):
        root = Path(__file__).resolve().parents[1]
        mirrored = (
            "ai_budget.py",
            "hybrid_research.py",
            "providers/reasoning_provider.py",
            "providers/openai_provider.py",
            "research.py",
            "core/application.py",
            "core/container.py",
        )
        addon = root / "home_assistant/addons/jarvis/app/src/jarvis"
        for relative in mirrored:
            self.assertEqual(
                (root / "src/jarvis" / relative).read_text(encoding="utf-8"),
                (addon / relative).read_text(encoding="utf-8"),
            )
        search_addon = root / "home_assistant/addons/jarvis_search"
        self.assertTrue((search_addon / "Dockerfile").exists())
        self.assertIn("formats:", (search_addon / "settings.yml").read_text())


if __name__ == "__main__":
    unittest.main()
