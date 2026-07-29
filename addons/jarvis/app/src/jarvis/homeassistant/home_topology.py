"""Assemble a bounded, ephemeral topology from Home Assistant-owned metadata."""

from __future__ import annotations

from datetime import datetime, timezone

from jarvis.models.home_topology import HomeTopologyEntity, HomeTopologySnapshot


class HomeTopologyAssembler:
    """Build current topology without persisting Home Assistant state."""

    def __init__(
        self,
        areas,
        floors,
        registry,
        devices,
        permitted_read_entities,
        permitted_action_entities,
        *,
        maximum_entities: int = 500,
    ) -> None:
        if (
            not isinstance(maximum_entities, int)
            or isinstance(maximum_entities, bool)
            or not 1 <= maximum_entities <= 2000
        ):
            raise ValueError("maximum_entities must be between 1 and 2000")
        self.maximum_entities = maximum_entities
        self._reads = frozenset(permitted_read_entities)
        self._actions = frozenset(permitted_action_entities)
        self._area_names = {
            str(item.get("area_id")): str(item.get("name"))
            for item in areas
            if item.get("area_id") and item.get("name")
        }
        self._area_floors = {
            str(item.get("area_id")): str(item.get("floor_id"))
            for item in areas
            if item.get("area_id") and item.get("floor_id")
        }
        self._floor_names = {
            str(item.get("floor_id", item.get("id"))): str(item.get("name"))
            for item in floors
            if item.get("floor_id", item.get("id")) and item.get("name")
        }
        self._device_areas = {
            str(item.get("id")): (
                None if item.get("area_id") is None else str(item.get("area_id"))
            )
            for item in devices
            if item.get("id")
        }
        self._registry = {}
        for item in registry:
            entity_id = item.get("entity_id", item.get("ei"))
            if not entity_id:
                continue
            self._registry[str(entity_id)] = {
                "area_id": item.get("area_id", item.get("ai")),
                "device_id": item.get("device_id", item.get("di")),
            }

    def assemble(self, states, *, captured_at: datetime | None = None):
        entities: list[HomeTopologyEntity] = []
        areas: dict[str, list[str]] = {}
        floors: dict[str, list[str]] = {}
        groups: dict[str, tuple[str, ...]] = {}
        permitted_states = sorted(
            (
                item for item in states
                if isinstance(item, dict)
                and item.get("entity_id") in self._reads
            ),
            key=lambda item: str(item.get("entity_id")),
        )[: self.maximum_entities]
        for item in permitted_states:
            entity_id = str(item["entity_id"])
            attributes = (
                dict(item.get("attributes", {}))
                if isinstance(item.get("attributes", {}), dict)
                else {}
            )
            metadata = self._registry.get(entity_id, {})
            device_id = metadata.get("device_id")
            area_id = metadata.get("area_id")
            if area_id is None and device_id is not None:
                area_id = self._device_areas.get(str(device_id))
            area_id = None if area_id is None else str(area_id)
            floor_id = self._area_floors.get(area_id) if area_id else None
            area_name = self._area_names.get(area_id) if area_id else None
            floor_name = self._floor_names.get(floor_id) if floor_id else None
            entity = HomeTopologyEntity(
                entity_id=entity_id,
                friendly_name=str(attributes.get("friendly_name", entity_id)),
                domain=entity_id.partition(".")[0],
                state=str(item.get("state", "unknown")),
                attributes=attributes,
                area_id=area_id,
                area_name=area_name,
                floor_id=floor_id,
                floor_name=floor_name,
                device_id=None if device_id is None else str(device_id),
                device_class=(
                    None
                    if attributes.get("device_class") is None
                    else str(attributes.get("device_class"))
                ),
                action_allowed=entity_id in self._actions,
            )
            entities.append(entity)
            if area_name:
                areas.setdefault(area_name.casefold(), []).append(entity_id)
            if floor_name:
                floors.setdefault(floor_name.casefold(), []).append(entity_id)
            members = attributes.get("entity_id")
            if isinstance(members, (list, tuple)):
                targets = tuple(
                    str(member) for member in members if member in self._reads
                )
                groups[entity.friendly_name.casefold()] = targets
                groups[entity_id.casefold()] = targets
        return HomeTopologySnapshot(
            captured_at=captured_at or datetime.now(timezone.utc),
            entities=tuple(entities),
            areas={
                name: tuple(sorted(values))
                for name, values in sorted(areas.items())
            },
            floors={
                name: tuple(sorted(values))
                for name, values in sorted(floors.items())
            },
            groups=dict(sorted(groups.items())),
        )

    @property
    def floor_references(self) -> dict[str, tuple[str, ...]]:
        values: dict[str, list[str]] = {}
        for entity_id, metadata in self._registry.items():
            if entity_id not in self._reads:
                continue
            area_id = metadata.get("area_id")
            device_id = metadata.get("device_id")
            if area_id is None and device_id is not None:
                area_id = self._device_areas.get(str(device_id))
            floor_id = self._area_floors.get(str(area_id)) if area_id else None
            floor_name = self._floor_names.get(floor_id) if floor_id else None
            if floor_name:
                values.setdefault(floor_name.casefold(), []).append(entity_id)
        return {
            name: tuple(sorted(entity_ids))
            for name, entity_ids in sorted(values.items())
        }
