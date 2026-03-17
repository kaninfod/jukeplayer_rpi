"""
Hardware management module for the jukebox.
Handles initialization and callbacks for all hardware devices.
"""
#from .devices.ili9488 import ILI9488
#from .devices.rfid import RC522Reader
import logging
from app.core import EventType, Event

logger = logging.getLogger(__name__)

# Lazy imports for CircuitPython device dependencies (requires board module)
PushButton = None
RotaryEncoder = None

def _load_circuitpython_devices():
    """Lazily load CircuitPython device modules when hardware is needed."""
    global PushButton, RotaryEncoder
    if PushButton is None:
        try:
            from .devices.pushbutton import PushButton as _PushButton
            from .devices.rotaryencoder import RotaryEncoder as _RotaryEncoder
            PushButton = _PushButton
            RotaryEncoder = _RotaryEncoder
            logger.info("✓ CircuitPython device modules loaded successfully")
        except ImportError as e:
            logger.warning(f"⚠ Failed to load CircuitPython device modules: {e}")
            logger.warning("  This is expected on systems without adafruit-blinka installed")
            raise

class HardwareManager:
    
    def __init__(self, config, event_bus, screen_manager=None):
        """
        Initialize HardwareManager with dependency injection.
        
        Args:
            config: Configuration object for hardware settings
            event_bus: EventBus instance for event communication
            screen_manager: ScreenManager instance (can be set later)
        """
        # Inject dependencies - no more direct imports needed
        self.config = config
        self.event_bus = event_bus
        #self.screen_manager = screen_manager
        self.playback_service = None
        
        # Hardware device instances
        self.display = None
        self.rfid_reader = None
        self.rfid_switch = None
        self.encoder = None
        self.button0 = None
        self.button1 = None
        self.button2 = None
        self.button3 = None
        self.button4 = None
        self.button5 = None

        logger.info("HardwareManager initialized with dependency injection")

    def initialize_hardware(self):
        """Initialize all hardware devices using injected config"""
        if not self.config.HARDWARE_MODE:
            logger.info("🖥️  Headless mode enabled - skipping hardware initialization")
            from .devices.mock_display import MockDisplay
            return MockDisplay()
        
        try:
            # Load CircuitPython devices (raises if board module not available)
            _load_circuitpython_devices()
            
            # Initialize display
            
            from .devices.mock_display import MockDisplay
            #return MockDisplay()
            self.display = MockDisplay()


            from .devices.pn532_rfid import PN532Reader
            self.rfid_reader = PN532Reader

            # Initialize rotary encoder with callback using CircuitPython keypad
            self.encoder = RotaryEncoder(
                pin_a=self.config.ROTARY_ENCODER_PIN_A,
                pin_b=self.config.ROTARY_ENCODER_PIN_B,
                callback=self._on_rotate,
                bouncetime=self.config.ENCODER_BOUNCETIME
            )

            # Initialize ButtonManager with all buttons at once to avoid reinitialization
            from .devices.pushbutton import ButtonManager
            button_manager = ButtonManager()
            
            # Register all buttons at once before starting monitoring
            button_configs = [
                (self.config.NFC_CARD_SWITCH_GPIO, {
                    'press_callback': self._on_rfid_switch_activated,
                    'bouncetime': 200,
                    'pull_up_down': True
                }),
                (self.config.BUTTON_1_GPIO, {
                    'callback': self._on_button1_press,
                    'bouncetime': self.config.BUTTON_BOUNCETIME,
                    'pull_up_down': True
                }),
                (self.config.BUTTON_2_GPIO, {
                    'callback': self._on_button2_press,
                    'bouncetime': self.config.BUTTON_BOUNCETIME,
                    'pull_up_down': True
                }),
                (self.config.BUTTON_3_GPIO, {
                    'callback': self._on_button3_press,
                    'bouncetime': self.config.BUTTON_BOUNCETIME,
                    'pull_up_down': True
                }),
                (self.config.BUTTON_4_GPIO, {
                    'callback': self._on_button4_press,
                    'long_press_callback': self._on_button4_long_press,
                    'long_press_threshold': 1.5,
                    'bouncetime': self.config.BUTTON_BOUNCETIME,
                    'pull_up_down': True
                }),
                (self.config.BUTTON_5_GPIO, {
                    'callback': self._on_button5_press,
                    'bouncetime': self.config.BUTTON_BOUNCETIME,
                    'pull_up_down': True
                }),
            ]
            
            # Register all buttons at once (initializes keypad only once)
            button_manager.register_all_buttons(button_configs)
            
            # Create PushButton wrappers (these won't trigger reinitialization)
            self.rfid_switch = PushButton(pin=self.config.NFC_CARD_SWITCH_GPIO, press_callback=self._on_rfid_switch_activated, bouncetime=200, pull_up_down=True)
            self.button1 = PushButton(pin=self.config.BUTTON_1_GPIO, callback=self._on_button1_press, bouncetime=self.config.BUTTON_BOUNCETIME, pull_up_down=True)
            self.button2 = PushButton(pin=self.config.BUTTON_2_GPIO, callback=self._on_button2_press, bouncetime=self.config.BUTTON_BOUNCETIME, pull_up_down=True)
            self.button3 = PushButton(pin=self.config.BUTTON_3_GPIO, callback=self._on_button3_press, bouncetime=self.config.BUTTON_BOUNCETIME, pull_up_down=True)
            self.button4 = PushButton(pin=self.config.BUTTON_4_GPIO, callback=self._on_button4_press, long_press_callback=self._on_button4_long_press, long_press_threshold=5, bouncetime=self.config.BUTTON_BOUNCETIME, pull_up_down=True)
            self.button5 = PushButton(pin=self.config.BUTTON_5_GPIO, callback=self._on_button5_press, bouncetime=self.config.BUTTON_BOUNCETIME, pull_up_down=True)

            logger.info("🔧 Hardware initialization complete")
            return self.display
            
        except Exception as e:
            logger.error(f"❌ Hardware initialization failed: {e}")
            # logger.info("🖥️  Falling back to headless mode")
            # from .devices.mock_display import MockDisplay
            # return MockDisplay()


    def _on_rfid_switch_activated(self):
        """Handle card insertion - initiate RFID read. Triggered by CircuitPython keypad event."""
        
        logger.info("=" * 70)
        logger.info("1. HARDWARE TRIGGER")
        logger.info("   └─ Card detected - initiating read")
        
        logger.info("2. INSTANTIATE & START READING")
        logger.info("   └─ Creating PN532Reader instance")
        reader = self.rfid_reader()
        try:
            logger.info("   └─ Calling reader.start_reading() with callback")
            reader.start_reading(result_callback=lambda result: self._rfid_read_callback(result, reader))
        except Exception as e:
            logger.error(f"   ❌ start_reading() failed: {e}")
            reader.cleanup()

    def _rfid_read_callback(self, result, reader=None):
        """Callback function to handle RFID read results from PN532Reader."""
        _callback_result_status = result.get('status')
        logger.info("5. CALLBACK TRIGGERED")
        logger.info(f"   └─ _rfid_read_callback() called with status='{_callback_result_status}'")
        
        try:
            if _callback_result_status == "success":
                logger.info("6. PROCESS RESULT (Success)")
                uid = result.get('uid')
                album_id = result.get('blocks', {}).get('album_id')
                logger.info(f"   ├─ UID extracted: {hex(uid) if uid else 'None'}")
                logger.info(f"   ├─ Album ID extracted: {album_id}")
                logger.info("   └─ Emitting Event(type=EventType.RFID_READ)")

                self.event_bus.emit(Event(
                    type=EventType.RFID_READ,
                    payload={"rfid": uid, "album_id": album_id}
                ))
                logger.info("   ✓ RFID_READ event emitted successfully")

            elif _callback_result_status == "timeout":
                logger.warning("6. PROCESS RESULT (Timeout)")
                logger.warning("   └─ Card read timeout (5 second threshold exceeded)")
                event = Event(EventType.SHOW_SCREEN_QUEUED,
                    payload={
                        "screen_type": "message",
                        "context": {
                            "title": "Error Reading Card",
                            "icon_name": "error.png",
                            "message": "Reading timed out. Try again...",
                            "theme": "message_info"
                        },
                        "duration": 3
                    }
                )
                self.event_bus.emit(event)
                logger.info("   ✓ Error screen queued")
                
            elif _callback_result_status == "error":
                logger.error("6. PROCESS RESULT (Error)")
                error_msg = result.get('error_message', 'Unknown error')
                logger.error(f"   └─ Read error: {error_msg}")
                event = Event(EventType.SHOW_SCREEN_QUEUED,
                    payload={
                        "screen_type": "message",
                        "context": {
                            "title": "Error Reading Card",
                            "icon_name": "error.png",
                            "message": "Try again...",
                            "theme": "message_info"},
                        "duration": 3
                    }
                )
                self.event_bus.emit(event)
                logger.info("   ✓ Error screen queued")
        except Exception as e:
            logger.error(f"   ❌ Exception in callback: {e}", exc_info=True)
        finally:
            logger.info("7. CLEANUP")
            if reader:
                logger.info("   └─ Calling reader.cleanup()")
                reader.cleanup()
                logger.info("   ✓ Reader cleaned up")
            logger.info("=" * 70)

    def _rfid_write_callback(self, result, reader=None):
        logger.info(f"RFID write result: {result}")
        uid = result.get('uid')
        album_id = result.get('blocks', {}).get('album_id')
        self.event_bus.emit(Event(
            type=EventType.ENCODE_CARD,
            payload={"rfid": uid, "album_id": album_id}
        ))
        # Clean up reader after callback completes
        if reader:
            reader.cleanup()

    def _on_button0_press(self):
        """Handle button 0 press - Generic button"""
        logger.info("Button 0 was pressed!")
        self.event_bus.emit(Event(
            type=EventType.BUTTON_PRESSED,
            payload={"button": 0, "action": "generic"}
        ))
    
    def _on_button1_press(self):
        """Handle button 1 press - Previous track"""
        logger.info("Button 1 press: Previous track")
        self.event_bus.emit(Event(
            type=EventType.BUTTON_PRESSED,
            payload={"button": 1, "action": "previous_track"}
        ))

    def _on_button2_press(self):
        """Handle button 2 press - Play/Pause"""
        logger.info("Button 2 press: Play/Pause")
        self.event_bus.emit(Event(
            type=EventType.BUTTON_PRESSED,
            payload={"button": 2, "action": "play_pause"}
        ))

    def _on_button3_press(self):
        """Handle button 3 press - Next track"""
        logger.info("Button 3 press: Next track")
        self.event_bus.emit(Event(
            type=EventType.BUTTON_PRESSED,
            payload={"button": 3, "action": "next_track"}
        ))
    
    def _on_button4_press(self):
        """Handle button 4 press - Stop"""
        logger.info("Button 4 press: Stop")
        self.event_bus.emit(Event(
            type=EventType.BUTTON_PRESSED,
            payload={"button": 4, "action": "stop"}
        ))
    
    def _on_button4_long_press(self):
        """Handle button 4 long press - System Reboot"""
        logger.info("Button 4 long press detected (requesting system reboot)")
        self.event_bus.emit(Event(
            type=EventType.TOGGLE_REPEAT_ALBUM,
            payload={"button": 4}
        ))

    def _on_button5_press(self):
        """Handle button 5 press - Rotary encoder button"""
        logger.info("Rotary encoder button was pressed!")
        self.event_bus.emit(Event(
            type=EventType.BUTTON_PRESSED,
            payload={"button": "rotary_encoder"}
        ))

    def _on_rotate(self, direction, position):
        """
        Handle rotary encoder rotation.
        direction=1 means CW (position increased), direction=-1 means CCW (position decreased)
        """
        if direction > 0:
            # Clockwise rotation (turning right = volume up)
            self.event_bus.emit(Event(
                type=EventType.ROTARY_ENCODER,
                payload={"direction": "CW"}
            ))
        else:
            # Counter-clockwise rotation (turning left = volume down)
            self.event_bus.emit(Event(
                type=EventType.ROTARY_ENCODER,
                payload={"direction": "CCW"}
            ))


    def cleanup(self):
        """Clean up GPIO resources"""
        def _safe_cleanup(device, label: str):
            if not device:
                return
            cleanup_fn = getattr(device, "cleanup", None)
            if not callable(cleanup_fn):
                logger.debug("%s cleanup skipped: no cleanup()", label)
                return
            try:
                cleanup_fn()
            except Exception as e:
                logger.error(f"{label} cleanup error: {e}")

        # Clean up individual devices first (while GPIO mode is still set)               
        if self.rfid_reader:
            try:
                pass
                #self.rfid_reader.stop()
            except Exception as e:
                logger.error(f"RFID cleanup error: {e}")
        # Clean up RFID switch (CircuitPython PushButton)
        _safe_cleanup(self.rfid_switch, "RFID switch")
                
        _safe_cleanup(self.encoder, "Encoder")
        
        # Clean up buttons using their cleanup methods
        _safe_cleanup(self.button0, "Button 0")
            
        _safe_cleanup(self.button1, "Button 1")

        _safe_cleanup(self.button2, "Button 2")

        _safe_cleanup(self.button3, "Button 3")

        if self.button4:
            _safe_cleanup(self.button4, "Button 4")
        else:
            logger.info("Button 4 cleanup skipped - was used as RFID switch")

        _safe_cleanup(self.button5, "Button 5")

        # Clean up display last
        if self.display:
            try:
                self.display.cleanup()
            except Exception as e:
                logger.error(f"Display cleanup error: {e}")
        
        # No final GPIO cleanup needed for lgpio


# import RPi.GPIO as GPIO
# GPIO.setmode(GPIO.BCM)
# GPIO.setup(26, GPIO.IN, pull_up_down=GPIO.PUD_UP)
# print(GPIO.input(26))