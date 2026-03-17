"""
Pi Client Main Application
Orchestrates hardware, event translation, backend communication, and display.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Setup logging FIRST, before any other imports
from app.core.logging_config import setup_logging
setup_logging()

# Get logger after setup
logger = logging.getLogger(__name__)
logger.info("=" * 60)
logger.info("🚀 Jukeplayer Pi Client Starting")
logger.info("=" * 60)

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import config
from app.core import event_bus
from app.client.api_client import BackendAPIClient
from app.client.websocket_client import BackendWebSocketClient
from app.client.event_translator import EventTranslator
from app.client.state_manager import StateManager
from app.client.connection_monitor import ConnectionMonitor


class PiClientApp:
    """Main Pi client application orchestrator."""
    
    def __init__(self):
        """Initialize all components."""
        self.config = config
        self.event_bus = event_bus
        self.api_client = BackendAPIClient(backend_url=config.BACKEND_URL)
        self.ws_client = BackendWebSocketClient(backend_ws_url=config.BACKEND_WS_URL)
        self.event_translator = EventTranslator(api_client=self.api_client)
        self.state_manager = StateManager()
        self.connection_monitor = ConnectionMonitor(
            ws_client=self.ws_client,
            heartbeat_interval=config.HEARTBEAT_INTERVAL,
            reconnect_delay=config.RECONNECT_DELAY,
            max_reconnect_attempts=config.MAX_RECONNECT_ATTEMPTS,
        )
        
        # Hardware will be initialized based on HARDWARE_MODE
        self.hardware = None
        self.screen_manager = None
        self.event_loop = None  # Will be set in run() to schedule async tasks from callbacks
        
        self.is_running = False
        
        logger.info(f"Pi Client initialized - Mode: {config.HARDWARE_MODE}, Backend: {config.BACKEND_URL}")
    
    async def initialize_hardware(self):
        """Initialize hardware components based on HARDWARE_MODE."""
        try:
            logger.info("Initializing REAL hardware")
            from app.hardware.hardware import HardwareManager
            self.hardware = HardwareManager(
                config=self.config,
                event_bus=self.event_bus,
                screen_manager=self.screen_manager
            )
            
            self.hardware.initialize_hardware()
            logger.info("Hardware initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize hardware: {e}")
            raise
    
    async def initialize_ui(self):
        """Initialize display and screen manager."""
        try:
            logger.info("Initializing UI components")
            from app.ui.screen_manager import ScreenManager
            
            self.screen_manager = ScreenManager(
                display=self.hardware.display if self.hardware else None,
                config=self.config
            )
            
            logger.info("UI initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize UI: {e}")
            raise
    
    def _register_hardware_callbacks(self):
        """Register event bus listeners for hardware events."""
        if not self.hardware:
            logger.warning("Hardware not initialized, skipping callback registration")
            return
        
        logger.info("Registering hardware event listeners")
        
        # Hardware events are emitted to event_bus and we listen for them here
        # and translate them to appropriate actions via event_translator
        
        from app.core import EventType
        
        def on_button_pressed(event):
            """Handle button press events - call backend API for playback control."""
            action = event.payload.get("action", "")
            button = event.payload.get("button", 0)
            logger.info(f"Button {button} pressed: {action}")
            
            if not self.event_loop:
                logger.warning("Event loop not available, skipping button action")
                return
            
            # Map actions to API calls
            api_calls = {
                "previous_track": self.api_client.previous_track,
                "play_pause": self.api_client.play_pause,
                "next_track": self.api_client.next_track,
                "stop": self.api_client.stop,
            }
            
            if action in api_calls:
                logger.info(f"Calling backend API: {action}")
                asyncio.run_coroutine_threadsafe(
                    api_calls[action](),
                    self.event_loop
                )
            else:
                logger.warning(f"Unknown button action: {action}")
        
        def on_rotary_turned(event):
            """Handle rotary encoder turn events - control volume."""
            direction = event.payload.get("direction", "")
            logger.info(f"Rotary turned: {direction}")
            
            if not self.event_loop:
                logger.warning("Event loop not available, skipping volume control")
                return
            
            if direction == "CW":
                logger.info("Volume up")
                asyncio.run_coroutine_threadsafe(
                    self.api_client.volume_up(),
                    self.event_loop
                )
            elif direction == "CCW":
                logger.info("Volume down")
                asyncio.run_coroutine_threadsafe(
                    self.api_client.volume_down(),
                    self.event_loop
                )
        
        def on_rfid_read(event):
            """Handle RFID card read - play the album via backend API."""
            rfid = event.payload.get("rfid")
            album_id = event.payload.get("album_id")
            logger.info(f"RFID card read: UID={rfid}, album_id={album_id}")
            
            if album_id and self.event_loop:
                logger.info(f"Playing album {album_id}")
                # Schedule the async API call on the event loop from this sync callback
                asyncio.run_coroutine_threadsafe(
                    self.api_client.play_album_from_albumid(album_id),
                    self.event_loop
                )
            elif album_id:
                logger.warning("Event loop not available yet, skipping playback request")
            else:
                logger.warning("RFID read succeeded but no album_id found")
        
        # Subscribe to hardware events from event_bus
        self.event_bus.subscribe(EventType.BUTTON_PRESSED, on_button_pressed)
        self.event_bus.subscribe(EventType.ROTARY_ENCODER, on_rotary_turned)
        self.event_bus.subscribe(EventType.RFID_READ, on_rfid_read)
        
        logger.info("Hardware event listeners registered")
    
    def _register_websocket_callbacks(self):
        """Register WebSocket event callbacks."""
        logger.info("Registering WebSocket event callbacks")
        
        # Status update callback - feed backend state to state manager
        async def on_status_update(message):
            """Handle playback status updates from backend."""
            logger.debug(f"Status update received: {message}")
            await self.state_manager.update_from_backend(message)
            
            if self.screen_manager:
                await self.screen_manager.update_status(self.state_manager.state)
        
        # Connection state callbacks
        async def on_connected():
            """Handle backend connection established."""
            logger.info("WebSocket connected to backend")
            await self.state_manager.notify_connection_restored()
            
            if self.screen_manager:
                await self.screen_manager.show_message("Connected to Backend", duration=2)
        
        async def on_disconnected():
            """Handle backend disconnection."""
            logger.warning("WebSocket disconnected from backend")
            await self.state_manager.notify_connection_lost()
            
            if self.screen_manager:
                await self.screen_manager.show_message("Backend Disconnected", duration=0)
        
        # Register WebSocket callbacks
        self.ws_client.on("message", on_status_update)
        self.ws_client.on("connected", on_connected)
        self.ws_client.on("disconnected", on_disconnected)
        
        # Register connection monitor callbacks
        self.connection_monitor.on_connected(on_connected)
        self.connection_monitor.on_disconnected(lambda reason: on_disconnected())
        
        logger.info("WebSocket callbacks registered")
    
    def _register_state_callbacks(self):
        """Register state manager callbacks to update UI."""
        logger.info("Registering state callbacks")
        
        async def on_state_changed(state):
            """Update UI on any state change."""
            if self.screen_manager:
                await self.screen_manager.update_status(state)
        
        # Register for all state change types
        self.state_manager.subscribe("state_changed", on_state_changed)
        self.state_manager.subscribe("track_changed", on_state_changed)
        self.state_manager.subscribe("playback_changed", on_state_changed)
        self.state_manager.subscribe("volume_changed", on_state_changed)
        
        logger.info("State callbacks registered")
    
    async def run(self):
        """Run the main application event loop."""
        try:
            self.is_running = True
            self.event_loop = asyncio.get_running_loop()  # Capture event loop for async calls from callbacks
            logger.info("Starting Pi Client Application")
            
            # Initialize all components
            await self.initialize_hardware()
            #await self.initialize_ui()
            
            # Register event callbacks
            self._register_hardware_callbacks()
            self._register_websocket_callbacks()
            self._register_state_callbacks()
            
            # Start connection monitor
            await self.connection_monitor.start()
            
            # Connect to WebSocket
            logger.info("Connecting to backend WebSocket")
            await self.ws_client.connect()
            
            # Show startup message
            if self.screen_manager:
                await self.screen_manager.show_message("Jukebox Ready", duration=2)
            
            # Main event loop - keep running until interrupted
            logger.info("Entering main event loop")
            while self.is_running:
                await asyncio.sleep(1)
        
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}", exc_info=True)
        finally:
            await self.shutdown()
    
    async def shutdown(self):
        """Clean shutdown of all components."""
        logger.info("Shutting down Pi Client Application")
        self.is_running = False
        
        try:
            # Stop connection monitor
            if self.connection_monitor:
                await self.connection_monitor.stop()
            
            # Close WebSocket
            if self.ws_client:
                await self.ws_client.close()
            
            # Cleanup hardware (not async)
            if self.hardware:
                self.hardware.cleanup()
            
            # Shutdown UI
            if self.screen_manager:
                await self.screen_manager.shutdown()
            
            logger.info("Shutdown complete")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}", exc_info=True)


async def main():
    """Application entry point."""
    app = PiClientApp()
    await app.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
