import unittest
import sys
from pathlib import Path
from types import SimpleNamespace

sys.modules.setdefault("openai", SimpleNamespace(OpenAI=object))

from jarvis.core.assistant_orchestrator import AssistantOrchestrator
from jarvis.models.assistant_slice import AssistantInput, AssistantProposalKind
from jarvis.providers.assistant_proposal_provider import OpenAIAssistantProposalProvider
from jarvis.providers.openai_provider import OpenAIProvider
from jarvis.research import GeneralResearchProvider, ResearchController, ResearchPolicy


class ProposalModel:
    def __init__(self, payload):
        self.payload = payload

    def ask(self, request):
        self.request = request
        return self.payload


class ResearchModel:
    def __init__(self):
        self.calls = []

    def research(self, **request):
        self.calls.append(request)
        return {
            "status": "success",
            "message": "A researched answer.",
            "sources": ({"title": "Primary", "url": "https://example.com"},),
            "researched": True,
        }


class Home:
    async def read_entity_state(self, entity_id):
        raise AssertionError("Research must not call Home Assistant.")


class MemoryStore:
    def __init__(self):
        self.deleted = []

    def delete(self, memory_id):
        self.deleted.append(memory_id)


class MemoryWriter:
    def create_explicit_memory(self, request):
        self.request = request
        return SimpleNamespace(record=SimpleNamespace(memory_id="research-memory"))


class M27OpenKnowledgeResearchTests(unittest.IsolatedAsyncioTestCase):
    def test_runtime_addon_configuration_and_release_are_complete(self):
        root = Path(__file__).resolve().parents[1]
        mirrored = (
            "research.py",
            "core/application.py",
            "core/assistant_factory.py",
            "core/assistant_orchestrator.py",
            "core/container.py",
            "homeassistant/situational_intelligence.py",
            "models/assistant_slice.py",
            "providers/assistant_proposal_provider.py",
            "providers/openai_provider.py",
        )
        for relative in mirrored:
            self.assertEqual(
                (root / "src/jarvis" / relative).read_text(encoding="utf-8"),
                (
                    root
                    / "home_assistant/addons/jarvis/app/src/jarvis"
                    / relative
                ).read_text(encoding="utf-8"),
            )
        config = (root / "config/general.yaml").read_text(encoding="utf-8")
        addon_config = (
            root / "home_assistant/addons/jarvis/app/config/general.yaml"
        ).read_text(encoding="utf-8")
        self.assertEqual(config, addon_config)
        self.assertIn('version: "0.36.2"', config)
        self.assertIn("research:", config)
        self.assertIn(
            "M27 - Open Knowledge and Live Research (complete)",
            (root / "docs/roadmap.md").read_text(encoding="utf-8"),
        )

    def test_policy_is_bounded_and_exposes_conversation_state(self):
        policy = ResearchPolicy.from_config({
            "enabled": True,
            "automatic": True,
            "search_context_size": "high",
            "maximum_sources": 4,
            "timeout_seconds": 30,
            "allowed_domains": ["Example.COM"],
        })
        self.assertEqual(policy.allowed_domains, ("example.com",))
        self.assertTrue(policy.context(True)["enabled"])
        self.assertFalse(policy.context(False)["enabled"])
        with self.assertRaisesRegex(ValueError, "maximum_sources"):
            ResearchPolicy.from_config({"maximum_sources": 11})

    def test_language_layer_can_route_unknown_or_current_topics_to_research(self):
        model = ProposalModel(
            '{"kind":"research","research_query":"current topic",'
            '"force_research":true}'
        )
        proposal = OpenAIAssistantProposalProvider(model).propose(
            AssistantInput("What happened today?", {"research": {"enabled": True}})
        )
        self.assertEqual(proposal.kind, AssistantProposalKind.RESEARCH)
        self.assertEqual(proposal.research_query, "current topic")
        self.assertTrue(proposal.force_research)
        self.assertIn("kind conversation, research", model.request["instructions"])

    def test_language_layer_falls_back_to_research_for_current_and_identity_queries(self):
        for text in (
            "What is the latest stable Home Assistant release and what changed?",
            "Who am I?",
        ):
            proposal = OpenAIAssistantProposalProvider(
                ProposalModel("not-json")
            ).propose(AssistantInput(
                text,
                {"research": {"enabled": True, "automatic": True}},
            ))
            self.assertEqual(proposal.kind, AssistantProposalKind.RESEARCH)
            self.assertEqual(proposal.research_query, text)
            self.assertTrue(proposal.force_research)

    def test_language_layer_respects_disabled_research_during_fallback(self):
        proposal = OpenAIAssistantProposalProvider(
            ProposalModel("not-json")
        ).propose(AssistantInput(
            "Who am I?",
            {"research": {"enabled": False, "automatic": True}},
        ))
        self.assertEqual(proposal.kind, AssistantProposalKind.UNSUPPORTED)

    async def test_orchestrator_routes_research_without_home_authority(self):
        proposal_model = ProposalModel(
            '{"kind":"research","research_query":"latest solar research",'
            '"force_research":true}'
        )
        language = OpenAIAssistantProposalProvider(proposal_model)
        research_model = ResearchModel()
        research = GeneralResearchProvider(research_model, ResearchPolicy())
        orchestrator = AssistantOrchestrator(
            language, Home(), research_provider=research
        )
        result = await orchestrator.handle(
            "Research solar power",
            {
                "research": {"enabled": True},
                "conversation": (),
                "interaction": {"voice": False},
            },
        )
        self.assertEqual(result["message"], "A researched answer.")
        self.assertTrue(research_model.calls[0]["force_search"])

        disabled = await orchestrator.handle(
            "Research solar power",
            {"research": {"enabled": False}},
        )
        self.assertEqual(disabled["status"], "not_supported")

    def test_provider_extracts_unique_bounded_url_citations(self):
        citation = lambda title, url: SimpleNamespace(
            type="url_citation", title=title, url=url
        )
        response = SimpleNamespace(output=(
            SimpleNamespace(content=(
                SimpleNamespace(annotations=(
                    citation("One", "https://one.example"),
                    citation("One duplicate", "https://one.example"),
                    citation("Two", "https://two.example"),
                )),
            )),
        ))
        self.assertEqual(
            OpenAIProvider._response_sources(response, 2),
            (
                {"title": "One", "url": "https://one.example"},
                {"title": "Two", "url": "https://two.example"},
            ),
        )

    def test_conversation_controls_sources_and_explicit_memory(self):
        store = MemoryStore()
        writer = MemoryWriter()
        controller = ResearchController(ResearchPolicy(), store, writer)
        controller.record("one", {
            "message": "Verified information",
            "sources": ({"title": "Source", "url": "https://example.com"},),
            "researched": True,
        })
        sources = controller.handle("what sources did you use?", "one")
        self.assertIn("https://example.com", sources["message"])
        remembered = controller.handle("remember this", "one")
        self.assertEqual(remembered["status"], "success")
        self.assertEqual(writer.request.metadata["sources"][0]["title"], "Source")
        forgotten = controller.handle("forget this", "one")
        self.assertEqual(forgotten["status"], "success")
        self.assertEqual(store.deleted, ["research-memory"])
        controller.handle("do not use web research for this conversation", "one")
        self.assertFalse(controller.enabled("one"))
        controller.handle("enable web research for this conversation", "one")
        self.assertTrue(controller.enabled("one"))
