"""Explicit, restart-applied Home Assistant access enrollment."""
from __future__ import annotations
from pathlib import Path
import yaml


class HomeAccessEnrollment:
    """Inspect discovery and persist explicit policy changes to general.yaml only."""
    _HIGH_IMPACT_DOMAINS = frozenset({"lock", "alarm_control_panel", "cover", "garage_door", "script", "automation"})

    def __init__(self, config_path: str | Path, catalog) -> None:
        self._path, self._catalog = Path(config_path), catalog

    def discover(self, domain: str | None = None) -> dict[str, object]:
        entities = sorted(entity for entity in self._catalog.entity_ids if domain is None or entity.startswith(f"{domain}."))
        services = sorted(f"{service.domain}.{service.service}" for service in self._catalog.services if domain is None or service.domain == domain)
        return {"status":"success","entities":tuple(entities[:100]),"services":tuple(services[:100])}

    def enroll_read(self, entity_id: str) -> dict[str, object]:
        if entity_id not in self._catalog.entity_ids: return self._error("unknown_entity")
        config = self._load(); section = config.setdefault("home_assistant", {})
        self._append(section.setdefault("allowed_read_entities", []), entity_id)
        self._save(config)
        return self._result("read_enrolled")

    def enroll_action(self, entity_id: str, service_key: str, risk: str = "normal") -> dict[str, object]:
        if entity_id not in self._catalog.entity_ids: return self._error("unknown_entity")
        if service_key not in {f"{service.domain}.{service.service}" for service in self._catalog.services}: return self._error("unknown_service")
        domain = service_key.partition(".")[0]
        if domain in self._HIGH_IMPACT_DOMAINS and risk != "high": return self._error("high_impact_classification_required")
        if risk not in {"normal", "high"}: return self._error("invalid_risk")
        config = self._load(); policy = config.setdefault("home_assistant", {}).setdefault("action_policy", {})
        self._append(policy.setdefault("allowed_entities", []), entity_id)
        self._append(policy.setdefault("high_impact" if risk == "high" else "confirm_required", []), service_key)
        self._save(config)
        return self._result("action_enrolled")

    def set_alias(self, alias: str, entity_id: str) -> dict[str, object]:
        if not alias.strip() or entity_id not in self._catalog.entity_ids: return self._error("invalid_alias_or_entity")
        config = self._load(); section = config.setdefault("home_assistant", {})
        permitted = set(section.get("allowed_read_entities", ())) | set(section.get("action_policy", {}).get("allowed_entities", ()))
        if entity_id not in permitted: return self._error("entity_not_enrolled")
        section.setdefault("entity_aliases", {})[alias.strip()] = entity_id
        self._save(config)
        return self._result("alias_enrolled")

    def _load(self) -> dict:
        with self._path.open(encoding="utf-8") as file: return yaml.safe_load(file) or {}

    def _save(self, config: dict) -> None:
        with self._path.open("w", encoding="utf-8", newline="\n") as file: yaml.safe_dump(config, file, sort_keys=False, allow_unicode=True)

    @staticmethod
    def _append(items: list, value: str) -> None:
        if value not in items: items.append(value)

    @staticmethod
    def _result(reason: str) -> dict[str, object]: return {"status":"success","message":f"{reason}; restart Jarvis to apply it."}
    @staticmethod
    def _error(reason: str) -> dict[str, object]: return {"status":"not_supported","message":reason}
