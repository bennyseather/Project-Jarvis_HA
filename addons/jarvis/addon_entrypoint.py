import json
import os
from pathlib import Path

options = json.loads(Path("/data/options.json").read_text())
Path("/app/config/secrets.yaml").write_text(
    "home_assistant:\n  url: 'http://supervisor/core'\n  token: '" + os.environ["SUPERVISOR_TOKEN"] + "'\n"
    "openai:\n  api_key: '" + options["openai_api_key"] + "'\n"
)
os.environ["JARVIS_BRIDGE_API_KEY"] = options["bridge_api_key"]
os.environ["JARVIS_STORAGE_PATH"] = "/config/jarvis.sqlite3"
os.execvp("python", ["python", "-m", "jarvis.bridge_main"])
