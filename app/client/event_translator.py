"""
Event Translator for Pi Client
Maps hardware events to backend API calls.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class EventTranslator:
    """Translates hardware events into backend API calls."""
    
    def __init__(self, api_client):
        """
        Initialize translator.
        
        Args:
            api_client: BackendAPIClient instance
        """
        self.api = api_client
    
    async def on_button_pressed(self, event: dict):
        """
        Handle button press event.
        
        Maps button numbers to actions:
        - Button 1: Previous track
        - Button 2: Play/pause
        - Button 3: Next track
        - Button 4: Stop (with long-press handling)
        - Button 5: Custom (could be brightness, mode switch, etc.)
        """
        try:
            button = event.get("button")
            is_long_press = event.get("long_press", False)
            
            if button == 1:
                logger.info("Button 1: Previous track")
                await self.api.previous_track()
            
            elif button == 2:
                logger.info("Button 2: Play/Pause")
                await self.api.play_pause()
            
            elif button == 3:
                logger.info("Button 3: Next track")
                await self.api.next_track()
            
            elif button == 4:
                if is_long_press:
                    logger.info("Button 4 (long): Stopping playback")
                    await self.api.stop()
                else:
                    logger.info("Button 4 (short): Custom action")
                    # Could implement custom action here
            
            elif button == 5:
                logger.info("Button 5: Custom function")
                # Could implement brightness control, etc.
        
        except Exception as e:
            logger.error(f"Error handling button press event: {e}")
    
    async def on_rotary_turn(self, event: dict):
        """
        Handle rotary encoder turn event.
        
        Args:
            event: Event dict with 'direction' key (1 for clockwise, -1 for counterclockwise)
        """
        try:
            direction = event.get("direction", 0)
            steps = event.get("steps", 1)
            
            if direction > 0:
                logger.info(f"Rotary: Volume up ({steps} steps)")
                for _ in range(steps):
                    await self.api.volume_up()
            
            elif direction < 0:
                logger.info(f"Rotary: Volume down ({steps} steps)")
                for _ in range(steps):
                    await self.api.volume_down()
        
        except Exception as e:
            logger.error(f"Error handling rotary encoder event: {e}")
    
    async def on_rfid_read(self, event: dict):
        """
        Handle RFID card read event.
        
        Loads album associated with the card or starts encoding if not mapped.
        
        Args:
            event: Event dict with 'card_id' or 'rfid' key
        """
        try:
            card_id = event.get("card_id") or event.get("rfid")
            
            if not card_id:
                logger.warning("RFID read event without card_id")
                return
            
            logger.info(f"RFID: Card detected - {card_id}")
            
            # Attempt to play album or trigger encoding mode
            await self.api.play_album_from_rfid(card_id)
        
        except Exception as e:
            logger.error(f"Error handling RFID read event: {e}")
    
    async def on_card_inserted(self, event: dict):
        """
        Handle NFC card insertion event (for encoding mode detection).
        
        Args:
            event: Event dict with card information
        """
        try:
            logger.info("NFC Card inserted")
            # This might trigger encoding mode or album load depending on state
        
        except Exception as e:
            logger.error(f"Error handling card insertion: {e}")
    
    async def on_brightness_control(self, event: dict):
        """Handle brightness control event (if using dedicated button)."""
        try:
            level = event.get("level")
            
            if level is not None:
                logger.info(f"Brightness: Setting to {level}%")
                await self.api.set_brightness(level)
        
        except Exception as e:
            logger.error(f"Error handling brightness control: {e}")
