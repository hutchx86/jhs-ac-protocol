"""Constants for the JHS AC integration."""

DOMAIN = "jhs_ac"

# AC Command Constants
COMMANDS = {
    # Power commands
    "power_on": "A511010113F5",
    "power_off": "A511000011F5",
    
    # Mode commands
    "mode_cool": "A512010114F5",
    "mode_dry": "A512020216F5", 
    "mode_fan": "A512030318F5",
    
    # Fan speed commands
    "fan_low": "A516010118F5",
    "fan_high": "A51603031CF5",
    
    # Sleep mode commands
    "sleep_on": "A513010115F5",
    "sleep_off": "A513000013F5",
}

# Temperature command template function
def get_temp_command(temperature: int) -> str:
    """Generate temperature command with proper checksum."""
    temp = max(16, min(30, temperature))  # set valid temperature range
    temp_hex = format(temp, '02X')
    checksum = (0x14 + temp + temp) % 256
    checksum_hex = format(checksum, '02X')
    return f"A514{temp_hex}{temp_hex}{checksum_hex}F5"

# Mode mapping constants
MODE_MAP = {
    0x01: 'cool',
    0x02: 'dry', 
    0x03: 'fan_only'
}

FAN_MAP = {
    0x01: 'low',
    0x03: 'high'
}

# Default scan interval
SCAN_INTERVAL_SECONDS = 10