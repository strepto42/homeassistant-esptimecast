"""Base entity for ESPTimeCast."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import ESPTimeCastCoordinator


class ESPTimeCastEntity(CoordinatorEntity[ESPTimeCastCoordinator]):
    """Common base wiring coordinator data and device info."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ESPTimeCastCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_{key}"

    @property
    def device_info(self) -> DeviceInfo:
        status = self.coordinator.data
        entry = self.coordinator.config_entry
        return DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
            name=entry.title,
            manufacturer=MANUFACTURER,
            model=MODEL,
            sw_version=status.version if status else None,
            hw_version=status.board if status else None,
            configuration_url=self.coordinator.client.base_url,
        )

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.data is not None
