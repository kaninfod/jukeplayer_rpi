"""
Display hardware device for Raspberry Pi backlight control.
Handles reading and writing brightness to sysfs backlight interface.
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class DisplayDevice:
    """
    Hardware device for controlling display brightness via sysfs.
    Auto-detects backlight device and provides brightness control.
    """
    
    def __init__(self):
        self.backlight_path = None
        self.brightness_file = None
        self.max_brightness_file = None
        self._max_brightness = None
        self._discover_backlight()
    
    def _discover_backlight(self) -> bool:
        """Auto-discover the backlight device path."""
        backlight_dir = "/sys/class/backlight"
        
        if not os.path.exists(backlight_dir):
            logger.warning(f"Backlight directory not found: {backlight_dir}")
            return False
        
        try:
            devices = os.listdir(backlight_dir)
            if not devices:
                logger.warning(f"No backlight devices found in {backlight_dir}")
                return False
            
            # Use the first device found
            device = devices[0]
            self.backlight_path = os.path.join(backlight_dir, device)
            self.brightness_file = os.path.join(self.backlight_path, "brightness")
            self.max_brightness_file = os.path.join(self.backlight_path, "max_brightness")
            
            logger.info(f"Display device discovered: {device} at {self.backlight_path}")
            return True
        except Exception as e:
            logger.error(f"Error discovering backlight device: {e}")
            return False
    
    def is_available(self) -> bool:
        """Check if backlight device is available."""
        if not self.backlight_path:
            return False
        return os.path.exists(self.brightness_file) and os.path.exists(self.max_brightness_file)
    
    def get_max_brightness(self) -> Optional[int]:
        """Get the maximum brightness value."""
        if self._max_brightness is not None:
            return self._max_brightness
        
        if not self.is_available():
            logger.error("Display device not available")
            return None
        
        try:
            with open(self.max_brightness_file, 'r') as f:
                self._max_brightness = int(f.read().strip())
            logger.debug(f"Max brightness: {self._max_brightness}")
            return self._max_brightness
        except PermissionError:
            logger.error(f"Permission denied reading max brightness: {self.max_brightness_file}")
            return None
        except Exception as e:
            logger.error(f"Error reading max brightness: {e}")
            return None
    
    def get_brightness(self) -> Optional[int]:
        """
        Get current brightness value (0-31).
        Returns None if reading fails.
        """
        if not self.is_available():
            logger.error("Display device not available")
            return None
        
        try:
            with open(self.brightness_file, 'r') as f:
                brightness = int(f.read().strip())
            logger.debug(f"Current brightness: {brightness}")
            return brightness
        except PermissionError:
            logger.error(f"Permission denied reading brightness: {self.brightness_file}")
            return None
        except Exception as e:
            logger.error(f"Error reading brightness: {e}")
            return None
    
    def get_brightness_percent(self) -> Optional[float]:
        """Get current brightness as a percentage (0-100)."""
        brightness = self.get_brightness()
        max_brightness = self.get_max_brightness()
        
        if brightness is None or max_brightness is None or max_brightness == 0:
            return None
        
        return (brightness / max_brightness) * 100
    
    def set_brightness(self, brightness: int) -> bool:
        """
        Set brightness to an absolute value (0-31).
        
        Args:
            brightness: Brightness level (0 to max_brightness)
        
        Returns:
            True if successful, False otherwise
        """
        if not self.is_available():
            logger.error("Display device not available")
            return False
        
        max_brightness = self.get_max_brightness()
        if max_brightness is None:
            logger.error("Could not determine max brightness")
            return False
        
        # Clamp brightness to valid range
        brightness = max(0, min(brightness, max_brightness))
        
        try:
            with open(self.brightness_file, 'w') as f:
                f.write(str(brightness))
            logger.info(f"Brightness set to {brightness}")
            return True
        except PermissionError:
            logger.error(f"Permission denied writing brightness: {self.brightness_file}")
            return False
        except Exception as e:
            logger.error(f"Error setting brightness: {e}")
            return False
    
    def set_brightness_percent(self, percent: float) -> bool:
        """
        Set brightness as a percentage (0-100).
        
        Args:
            percent: Brightness percentage (0-100)
        
        Returns:
            True if successful, False otherwise
        """
        max_brightness = self.get_max_brightness()
        if max_brightness is None:
            logger.error("Could not determine max brightness")
            return False
        
        # Clamp percent to 0-100
        percent = max(0, min(percent, 100))
        
        # Convert percentage to absolute brightness value
        brightness = int((percent / 100) * max_brightness)
        
        logger.debug(f"Setting brightness to {percent}% ({brightness} absolute)")
        return self.set_brightness(brightness)
