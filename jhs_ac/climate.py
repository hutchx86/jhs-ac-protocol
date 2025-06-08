"""Climate platform for JHS AC."""
import asyncio
import logging
import re
from datetime import timedelta
from typing import Any

import aiohttp

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN, COMMANDS, MODE_MAP, FAN_MAP, SCAN_INTERVAL_SECONDS, get_temp_command

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=SCAN_INTERVAL_SECONDS)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the JHS AC climate platform."""
    
    coordinator = JHSACDataUpdateCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()

    async_add_entities([JHSACClimate(coordinator)])


class JHSACDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the Tasmota device."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize."""
        self.host = config_entry.data["host"]
        
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self):
        """Update data via HTTP console polling."""
        try:
            async with aiohttp.ClientSession() as session:
                # First check if Tasmota is online
                async with session.get(
                    f"http://{self.host}/cm?cmnd=Status",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status != 200:
                        _LOGGER.warning(f"Tasmota offline - HTTP {response.status} from {self.host}")
                        return self._get_offline_data()
                
                # Tasmota is online, get console data
                async with session.get(
                    f"http://{self.host}/cs?c2=1",
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        console_text = await response.text()
                        parsed_data = self._parse_console_data(console_text)
                        if parsed_data and parsed_data.get('raw_message') != 'No data':
                            return parsed_data
                        else:
                            # Tasmota is online but no AC heartbeat found
                            _LOGGER.warning("Tasmota online but no AC heartbeat found")
                            return self._get_ac_offline_data()
                    else:
                        _LOGGER.warning(f"Console request failed - HTTP {response.status}")
                        return self._get_offline_data()
                        
        except asyncio.TimeoutError:
            _LOGGER.warning(f"Timeout connecting to Tasmota at {self.host}")
            return self._get_offline_data()
        except Exception as err:
            _LOGGER.error(f"Error communicating with Tasmota: {err}")
            return self._get_offline_data()

    def _parse_console_data(self, console_text: str) -> dict:
        """Parse console data for AC heartbeat messages."""
        lines = console_text.split('\n')
        
        # Look for the most recent SerialReceived message
        for line in reversed(lines):
            # Look for 36-character hex strings (A5...F5 pattern)
            match = re.search(r'[A-Fa-f0-9]{36}', line)
            if match:
                hex_message = match.group(0)
                if hex_message.startswith(('A5', 'a5')) and hex_message.endswith(('F5', 'f5')):
                    parsed = self._parse_hex_message(hex_message)
                    if parsed:
                        _LOGGER.info(f"Parsed heartbeat: {parsed}")
                        return parsed
        
        _LOGGER.debug("No valid heartbeat found in console")
        return self._get_default_data()

    def _parse_hex_message(self, hex_string: str) -> dict | None:
        """Parse 36-char hex heartbeat message from AC."""
        try:
            hex_string = hex_string.replace(' ', '').upper()
            
            if len(hex_string) != 36:
                return None

            # Convert to bytes
            bytes_data = [int(hex_string[i:i+2], 16) for i in range(0, len(hex_string), 2)]

            if bytes_data[0] != 0xA5 or bytes_data[17] != 0xF5:
                return None

            # Parse the heartbeat message using constants
            power = bytes_data[3] != 0x00
            mode = MODE_MAP.get(bytes_data[4], 'unknown')
            sleep = bytes_data[5] == 0x01
            ambient_temp = bytes_data[6]
            target_temp = bytes_data[7]
            fan_speed = FAN_MAP.get(bytes_data[9], 'low')
            temp_unit = '°F' if bytes_data[14] == 0x24 else '°C'
            water_tank = bytes_data[15] == 0x03

            return {
                'power': power,
                'mode': mode,
                'sleep': sleep,
                'ambient_temp': ambient_temp,
                'target_temp': target_temp,
                'fan_speed': fan_speed,
                'temp_unit': temp_unit,
                'water_tank_full': water_tank,
                'raw_message': hex_string
            }
            
        except Exception as e:
            _LOGGER.error(f"Error parsing hex message {hex_string}: {e}")
            return None

    def _get_default_data(self) -> dict:
        """Return default data when no AC data available."""
        return {
            'power': False,
            'mode': 'unknown',
            'sleep': False,
            'ambient_temp': 20,
            'target_temp': 20,
            'fan_speed': 'low',
            'temp_unit': '°C',
            'water_tank_full': False,
            'raw_message': 'No data'
        }

    def _get_offline_data(self) -> dict:
        """Return offline data when Tasmota is unreachable."""
        return {
            'power': False,
            'mode': 'unknown',
            'sleep': False,
            'ambient_temp': None,
            'target_temp': None,
            'fan_speed': 'unknown',
            'temp_unit': '°C',
            'water_tank_full': False,
            'raw_message': 'Tasmota device offline'
        }

    def _get_ac_offline_data(self) -> dict:
        """Return data when Tasmota is online but AC is not responding."""
        return {
            'power': False,
            'mode': 'unknown', 
            'sleep': False,
            'ambient_temp': None,
            'target_temp': None,
            'fan_speed': 'unknown',
            'temp_unit': '°C',
            'water_tank_full': False,
            'raw_message': 'AC not responding - check power/connection'
        }

    async def send_command(self, command: str) -> bool:
        """Send command to AC via Tasmota."""
        try:
            _LOGGER.info(f"Sending command: {command}")
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"http://{self.host}/cm",
                    params={"cmnd": f"SerialSend5 {command}"},
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    success = response.status == 200
                    if success:
                        _LOGGER.info(f"Command sent successfully: {command}")
                        # Request immediate refresh after sending command
                        await asyncio.sleep(1)
                        await self.async_request_refresh()
                    else:
                        _LOGGER.error(f"Command failed with status {response.status}: {command}")
                    return success
        except Exception as err:
            _LOGGER.error(f"Error sending command: {err}")
            return False


class JHSACClimate(CoordinatorEntity, ClimateEntity):
    """JHS AC Climate entity."""

    def __init__(self, coordinator: JHSACDataUpdateCoordinator) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self._attr_name = "JHS AC"
        self._attr_unique_id = f"jhs_ac_{coordinator.host.replace('.', '_')}"
        
        self._attr_hvac_modes = [
            HVACMode.OFF,
            HVACMode.COOL,
            HVACMode.DRY,
            HVACMode.FAN_ONLY,
        ]
        
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )
        
        self._attr_fan_modes = ["low", "high"]
        self._attr_min_temp = 16
        self._attr_max_temp = 30
        self._attr_target_temperature_step = 1

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        raw_message = self.coordinator.data.get('raw_message', '')
        return not raw_message.startswith(('Tasmota device offline', 'AC not responding'))

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        temp = self.coordinator.data.get('ambient_temp')
        return temp if temp is not None else None

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        temp = self.coordinator.data.get('target_temp')
        return temp if temp is not None else None

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        unit = self.coordinator.data.get('temp_unit', '°C')
        return UnitOfTemperature.FAHRENHEIT if unit == '°F' else UnitOfTemperature.CELSIUS

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current operation mode."""
        if not self.coordinator.data.get('power', False):
            return HVACMode.OFF
            
        mode = self.coordinator.data.get('mode', 'cool')
        mode_map = {
            'cool': HVACMode.COOL,
            'dry': HVACMode.DRY,
            'fan_only': HVACMode.FAN_ONLY,
        }
        return mode_map.get(mode, HVACMode.OFF)

    @property
    def fan_mode(self) -> str | None:
        """Return the fan setting."""
        return self.coordinator.data.get('fan_speed')

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        return {
            'sleep_mode': self.coordinator.data.get('sleep'),
            'water_tank_full': self.coordinator.data.get('water_tank_full'),
            'raw_message': self.coordinator.data.get('raw_message'),
        }

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.OFF:
            await self.coordinator.send_command(COMMANDS["power_off"])
        else:
            # Turn on first if needed
            if not self.coordinator.data.get('power'):
                await self.coordinator.send_command(COMMANDS["power_on"])
                await asyncio.sleep(1)
            
            # Set mode using constants
            mode_commands = {
                HVACMode.COOL: COMMANDS["mode_cool"],
                HVACMode.DRY: COMMANDS["mode_dry"],
                HVACMode.FAN_ONLY: COMMANDS["mode_fan"],
            }
            
            if hvac_mode in mode_commands:
                await self.coordinator.send_command(mode_commands[hvac_mode])

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        fan_commands = {
            "low": COMMANDS["fan_low"],
            "high": COMMANDS["fan_high"],
        }
        
        if fan_mode in fan_commands:
            await self.coordinator.send_command(fan_commands[fan_mode])

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        # Use the const function to generate the command
        command = get_temp_command(int(temperature))
        await self.coordinator.send_command(command)

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        await self.coordinator.send_command(COMMANDS["power_on"])

    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        await self.coordinator.send_command(COMMANDS["power_off"])