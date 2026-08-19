import json
import os
from pathlib import Path
import yaml

options = json.loads(Path("/data/options.json").read_text())
general_path = Path("/app/config/general.yaml")
general = yaml.safe_load(general_path.read_text()) or {}
general.setdefault("proactive", {})["voice_enabled"] = bool(
    options.get("proactive_voice_enabled", False)
)
general.setdefault("hybrid_research", {})["searxng_url"] = str(
    options.get("searxng_url", "http://homeassistant.local:8088/search")
)
general.setdefault("ai_budget", {})["monthly_limit_usd"] = float(
    options.get("monthly_ai_budget_usd", 10.0)
)
episodic = general.setdefault("episodic_memory", {})
episodic["enabled"] = bool(options.get("episodic_memory_enabled", True))
episodic["retention_days"] = int(options.get("episodic_retention_days", 30))
episodic["maximum_episodes"] = int(options.get("maximum_episodes", 50))
persona = general.setdefault("persona", {})
persona["humour"] = str(options.get("personality_humour", "subtle"))
persona["warmth"] = str(options.get("personality_warmth", "balanced"))
persona["formality"] = str(options.get("personality_formality", "refined"))
persona["verbosity"] = str(options.get("personality_verbosity", "concise"))
persona["proactivity"] = str(options.get("personality_proactivity", "balanced"))
persona["preferred_address"] = str(options.get("preferred_address", ""))
stewardship = general.setdefault("stewardship", {})
stewardship["enabled"] = bool(options.get("stewardship_enabled", True))
stewardship["reconciliation_seconds"] = int(
    options.get("stewardship_reconciliation_seconds", 300)
)
adaptive_learning = general.setdefault("adaptive_learning", {})
adaptive_learning["enabled"] = bool(options.get("adaptive_learning_enabled", True))
routine_learning = general.setdefault("routine_learning", {})
routine_learning["enabled"] = bool(options.get("routine_learning_enabled", True))
local_reasoning = general.setdefault("local_reasoning", {})
local_reasoning["enabled"] = bool(options.get("local_reasoning_enabled", True))
local_reasoning["url"] = str(options.get("local_reasoning_url", "http://192.168.1.105:10550"))
local_reasoning["token"] = str(options.get("local_reasoning_token", ""))
local_reasoning["model"] = str(options.get("local_reasoning_model", "qwen3:8b"))
local_reasoning["voice_model"] = str(options.get("local_voice_reasoning_model", "qwen3:1.7b"))
local_reasoning["embedding_model"] = str(options.get("local_embedding_model", "qwen3-embedding:0.6b"))
local_reasoning["timeout_seconds"] = int(options.get("local_reasoning_timeout", 90))
local_reasoning["fallback_to_openai"] = bool(options.get("openai_fallback_enabled", True))
general_path.write_text(
    yaml.safe_dump(general, sort_keys=False, allow_unicode=True)
)
policy_path = Path("/config/home_access_policy.yaml")
if not policy_path.exists():
    policy_path.write_text(Path("/app/config/home_access_policy.defaults.yaml").read_text())
policy = yaml.safe_load(policy_path.read_text()) or {}
if not policy.get("m16_immediate_all_device_control", False):
    home_assistant = policy.setdefault("home_assistant", {})
    action_policy = home_assistant.setdefault("action_policy", {})
    home_assistant["all_entities"] = True
    action_policy["all_entities"] = True
    action_policy["all_device_services"] = True
    action_policy["confirm_required"] = []
    action_policy["high_impact"] = []
    policy["m16_immediate_all_device_control"] = True
    policy_path.write_text(yaml.safe_dump(policy, sort_keys=False, allow_unicode=True))
Path("/app/config/secrets.yaml").write_text(
    "home_assistant:\n  url: 'http://supervisor/core'\n  token: '" + os.environ["SUPERVISOR_TOKEN"] + "'\n"
    "openai:\n  api_key: '" + options["openai_api_key"] + "'\n"
)
os.environ["JARVIS_BRIDGE_API_KEY"] = options["bridge_api_key"]
os.environ["JARVIS_CONFIG_DIR"] = "/app/config"
os.environ["JARVIS_HOME_POLICY_PATH"] = str(policy_path)
os.environ["JARVIS_STORAGE_PATH"] = "/config/jarvis.sqlite3"
os.environ["JARVIS_BLUEPRINT_ROOT"] = "/homeassistant"
os.execvp("python", ["python", "-m", "jarvis.bridge_main"])
