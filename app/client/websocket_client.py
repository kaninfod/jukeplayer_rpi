"""
WebSocket Client for Backend Status Updates
Maintains real-time connection to backend and broadcasts status changes.
Registers with backend on connection for client tracking.
"""

import asyncio
import json
import logging
from typing import Callable, Dict, List, Optional

import websockets

logger = logging.getLogger(__name__)


class BackendWebSocketClient:
    """WebSocket client for receiving real-time updates from backend."""
    
    def __init__(self, backend_ws_url: str, client_name: str = "rpi_client", 
                 capabilities: List[str] = None):
        """
        Initialize WebSocket client.
        
        Args:
            backend_ws_url: WebSocket URL for backend (e.g., "ws://192.168.1.100:8000/ws/mediaplayer/status")
            client_name: User-friendly name for this client (from config)
            capabilities: List of capabilities this client has (e.g., ['nfc_reader', 'display'])
        """
        self.url = backend_ws_url
        self.client_name = client_name
        self.capabilities = capabilities or ["nfc_reader", "display", "buttons"]
        self.websocket = None
        self.connected = False
        self.client_id = None  # Set after registration
        self.listeners: Dict[str, List[Callable]] = {}
        self._listen_task = None
    
    async def connect(self):
        """Connect to backend WebSocket server and register."""
        try:
            self.websocket = await websockets.connect(self.url)
            self.connected = True
            logger.info(f"✅ Connected to backend WebSocket: {self.url}")
            
            # Register with backend immediately after connecting
            await self._register_with_backend()
            
            # Start listening task
            self._listen_task = asyncio.create_task(self._listen())
        except Exception as e:
            logger.error(f"❌ Failed to connect to WebSocket: {e}")
            self.connected = False
            # Clean up the websocket if it was created but registration failed
            if self.websocket:
                try:
                    await self.websocket.close()
                except Exception as close_err:
                    logger.debug(f"Error closing websocket after failed registration: {close_err}")
                self.websocket = None
            raise
    
    async def _register_with_backend(self):
        """Send registration message to backend."""
        try:
            registration_msg = {
                "type": "register_client",
                "payload": {
                    "client_type": "rpi",
                    "client_name": self.client_name,
                    "capabilities": self.capabilities
                }
            }
            
            await self.websocket.send(json.dumps(registration_msg))
            logger.info(f"📝 Registration message sent: {self.client_name}")
            
            # Wait for registration response (may receive other messages first)
            # Keep receiving until we get the register_response
            import time
            timeout_end = time.time() + 5
            while time.time() < timeout_end:
                response = await asyncio.wait_for(
                    self.websocket.recv(),
                    timeout=max(0.1, timeout_end - time.time())
                )
                response_data = json.loads(response)
                
                if response_data.get("type") == "register_response":
                    payload = response_data.get("payload", {})
                    if payload.get("status") == "success":
                        self.client_id = payload.get("client_id")
                        logger.info(f"✅ Registration successful: {self.client_name} (ID: {self.client_id})")
                        return
                    else:
                        logger.error(f"❌ Registration failed: {payload.get('message')}")
                        raise Exception(f"Registration failed: {payload.get('message')}")
                else:
                    # Process other message types (e.g., current_track) during registration
                    await self._handle_message(response)
            
            raise Exception("Registration timeout")
        
        except asyncio.TimeoutError:
            logger.error("❌ Registration response timeout")
            raise Exception("Registration timeout")
        except Exception as e:
            logger.error(f"❌ Registration error: {e}")
            raise
    
    async def _listen(self):
        """Listen for messages from backend."""
        try:
            async for message in self.websocket:
                await self._handle_message(message)
        except websockets.exceptions.ConnectionClosed:
            logger.warning("WebSocket connection closed")
            self.connected = False
        except Exception as e:
            logger.error(f"WebSocket listening error: {e}")
            self.connected = False
    
    async def _handle_message(self, message: str):
        """Handle incoming message and dispatch to listeners."""
        try:
            data = json.loads(message)
            event_type = data.get("type")
            
            if not event_type:
                logger.warning(f"Received message without type: {data}")
                return
            
            logger.debug(f"Received event: {event_type}")
            
            # Dispatch to registered listeners
            if event_type in self.listeners:
                for callback in self.listeners[event_type]:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(data)
                        else:
                            callback(data)
                    except Exception as e:
                        logger.error(f"Error in listener for {event_type}: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse WebSocket message: {e}")
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {e}")
    
    def on(self, event_type: str, callback: Callable):
        """
        Register a listener for an event type.
        
        Args:
            event_type: Event type to listen for (e.g., "current_track", "volume_changed")
            callback: Async or sync function to call when event fires
        """
        if event_type not in self.listeners:
            self.listeners[event_type] = []
        self.listeners[event_type].append(callback)
        logger.debug(f"Registered listener for {event_type}")
    
    def off(self, event_type: str, callback: Callable):
        """
        Unregister a listener.
        
        Args:
            event_type: Event type
            callback: Function to remove
        """
        if event_type in self.listeners:
            try:
                self.listeners[event_type].remove(callback)
                logger.debug(f"Unregistered listener for {event_type}")
            except ValueError:
                logger.warning(f"Listener not found for {event_type}")
    
    async def close(self):
        """Close WebSocket connection."""
        self.connected = False
        if self._listen_task:
            self._listen_task.cancel()
        if self.websocket:
            await self.websocket.close()
        logger.info("WebSocket connection closed")
    
    def is_connected(self) -> bool:
        """Check if WebSocket is connected."""
        return self.connected and self.websocket is not None
