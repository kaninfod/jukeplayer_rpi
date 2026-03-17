"""
Pi Client Configuration
Hardware GPIO pins, thresholds, and backend connection settings.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class PiConfig:
    """Configuration for Pi client hardware and backend connection."""
    
    # === BACKEND CONNECTION ===
    BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
    BACKEND_WS_URL = os.getenv("BACKEND_WS_URL", "ws://127.0.0.1:8000/ws/mediaplayer/status")
    
    # === HARDWARE MODE ===
    # Set to "mock" for development without physical hardware
    # Set to "real" for actual Raspberry Pi hardware
    HARDWARE_MODE = os.getenv("HARDWARE_MODE", "real")
    
    # === GPIO BUTTON CONFIGURATION ===
    BUTTON_1_GPIO = int(os.getenv("BUTTON_1_GPIO", "14"))    # Previous track
    BUTTON_2_GPIO = int(os.getenv("BUTTON_2_GPIO", "15"))    # Play/Pause
    BUTTON_3_GPIO = int(os.getenv("BUTTON_3_GPIO", "12"))    # Next track
    BUTTON_4_GPIO = int(os.getenv("BUTTON_4_GPIO", "19"))    # Stop
    BUTTON_5_GPIO = int(os.getenv("BUTTON_5_GPIO", "17"))    # Custom function
    
    # Button debounce time (milliseconds)
    BUTTON_BOUNCETIME = int(os.getenv("BUTTON_BOUNCETIME", "200"))
    
    # Long press detection threshold (milliseconds)
    BUTTON_LONG_PRESS_TIME = int(os.getenv("BUTTON_LONG_PRESS_TIME", "1000"))
    
    # === ROTARY ENCODER CONFIGURATION ===
    # Physical wiring: CLK on GPIO 27, DT on GPIO 22
    # Software pins swapped: PIN_A reads DT, PIN_B reads CLK for correct direction
    ROTARY_ENCODER_PIN_A = int(os.getenv("ROTARY_ENCODER_PIN_A", "22"))    # Read DT
    ROTARY_ENCODER_PIN_B = int(os.getenv("ROTARY_ENCODER_PIN_B", "27"))    # Read CLK
    
    # Rotary encoder debounce time (milliseconds)
    ENCODER_BOUNCETIME = int(os.getenv("ENCODER_BOUNCETIME", "10"))
    
    # === NFC CARD READER CONFIGURATION ===
    # Card insertion detection GPIO
    NFC_CARD_SWITCH_GPIO = int(os.getenv("NFC_CARD_SWITCH_GPIO", "4"))
    
    # RFID block configuration (maps logical names to block numbers)
    RFID_BLOCKS = {
        "album_id": 4
    }
    
    # RFID reader SPI settings
    RFID_CS_PIN = int(os.getenv("RFID_CS_PIN", "7"))
    
    # === DISPLAY CONFIGURATION ===
    DISPLAY_WIDTH = int(os.getenv("DISPLAY_WIDTH", "480"))
    DISPLAY_HEIGHT = int(os.getenv("DISPLAY_HEIGHT", "320"))
    DISPLAY_ROTATION = int(os.getenv("DISPLAY_ROTATION", "0"))
    
    # Display GPIO pins (for backlight, power, etc.)
    DISPLAY_POWER_GPIO = int(os.getenv("DISPLAY_POWER_GPIO", "20"))
    DISPLAY_BACKLIGHT_GPIO = int(os.getenv("DISPLAY_BACKLIGHT_GPIO", "18"))
    
    # ILI9488 SPI GPIOs
    DISPLAY_GPIO_CS = int(os.getenv("DISPLAY_GPIO_CS", "8"))
    DISPLAY_GPIO_DC = int(os.getenv("DISPLAY_GPIO_DC", "6"))
    DISPLAY_GPIO_RST = int(os.getenv("DISPLAY_GPIO_RST", "5"))
    
    # === FONT CONFIGURATION ===
    FONT_BASE_PATH = os.getenv("FONT_BASE_PATH", "fonts")
    
    # === LOGGING ===
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("LOG_FILE", "logs/pi_client.log")
    LOG_SERVER_HOST = os.getenv("LOG_SERVER_HOST", "127.0.0.1")
    LOG_SERVER_PORT = int(os.getenv("LOG_SERVER_PORT", "514"))
    
    # === CONNECTION MONITORING ===
    # Heartbeat interval to detect backend disconnection (seconds)
    HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", "30"))
    
    # Reconnection delay when backend is unavailable (seconds)
    RECONNECT_DELAY = int(os.getenv("RECONNECT_DELAY", "5"))
    
    # Maximum reconnection attempts before showing error
    MAX_RECONNECT_ATTEMPTS = int(os.getenv("MAX_RECONNECT_ATTEMPTS", "0"))  # 0 = infinite
    
    @classmethod
    def get_font_definitions(cls):
        """Get font definitions with relative paths from font base directory."""
        base_path = cls.FONT_BASE_PATH
        return [
            {"name": "title", "path": os.path.join(base_path, "opensans", "OpenSans-Regular.ttf"), "size": 20},
            {"name": "info", "path": os.path.join(base_path, "opensans", "OpenSans-Regular.ttf"), "size": 18},
            {"name": "small", "path": os.path.join(base_path, "opensans", "OpenSans-Regular.ttf"), "size": 12},
            {"name": "symbols", "path": os.path.join(base_path, "symbolfont", "symbolfont.ttf"), "size": 24},
        ]


# Create global config instance
config = PiConfig()
