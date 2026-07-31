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
os.execvp("python", ["python", "-m", "jarvis.bridge_main"])
