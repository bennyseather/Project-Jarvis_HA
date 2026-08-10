"""Provider-neutral contracts for bounded whole-home situational reasoning."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping


@dataclass(frozen=True, slots=True)
class HomeTopologyEntity:
    entity_id: str
    friendly_name: str
    domain: str
    state: str
    attributes: Mapping[str, object]
    area_id: str | None = None
    area_name: str | None = None
    floor_id: str | None = None
    floor_name: str | None = None
    device_id: str | None = None
    device_class: str | None = None
    action_allowed: bool = False


@dataclass(frozen=True, slots=True)
class HomeTopologySnapshot:
    captured_at: datetime
    entities: tuple[HomeTopologyEntity, ...]
    areas: Mapping[str, tuple[str, ...]]
    floors: Mapping[str, tuple[str, ...]]
    groups: Mapping[str, tuple[str, ...]]

    def entity_map(self) -> dict[str, HomeTopologyEntity]:
        return {item.entity_id: item for item in self.entities}
