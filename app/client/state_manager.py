"""
State Manager for Pi Client
Tracks and caches backend state received via WebSocket.
"""

import asyncio
import logging
from typing import Dict, Any, Callable, List, Optional

logger = logging.getLogger(__name__)


class PlaybackState:
    """Immutable playback state snapshot."""
    
    def __init__(self, data: Dict[str, Any]):
        """Initialize from WebSocket message data."""
        self.raw_data = data
        
        # Track information
        self.current_track_index = data.get("track_index", 0)
        self.current_album_id = data.get("album_id", None)
        self.total_tracks = data.get("total_tracks", 0)
        self.current_track = data.get("track", {})
        self.album_name = data.get("album_name", "Unknown Album")
        
        # Playback state
        self.is_playing = data.get("is_playing", False)
        self.elapsed_time = data.get("elapsed_time", 0)
        self.total_time = data.get("total_time", 0)
        
        # Volume and output
        self.volume = data.get("volume", 50)
        self.is_mute = data.get("is_mute", False)
        self.output_type = data.get("output_type", None)
        
        # Display
        self.brightness = data.get("brightness", 100)
        
        # Connection status
        self.backend_connected = data.get("backend_connected", True)
    
    def __repr__(self) -> str:
        """String representation."""
        status = "Playing" if self.is_playing else "Stopped"
        track = self.current_track.get("title", "Unknown")
        return f"PlaybackState({status}: {track} [{self.current_track_index}/{self.total_tracks}])"


class StateManager:
    """Manages backend state with subscriber pattern."""
    
    def __init__(self):
        """Initialize state manager."""
        self._state: Optional[PlaybackState] = None
        self._subscribers: Dict[str, List[Callable]] = {
            "state_changed": [],
            "track_changed": [],
            "playback_changed": [],
            "volume_changed": [],
            "connection_changed": [],
        }
        self._lock = asyncio.Lock()
        
        logger.info("StateManager initialized")
    
    def subscribe(self, event_type: str, callback: Callable) -> None:
        """Subscribe to state change events."""
        if event_type not in self._subscribers:
            logger.warning(f"Unknown event type: {event_type}")
            return
        
        if callback not in self._subscribers[event_type]:
            self._subscribers[event_type].append(callback)
            logger.debug(f"Subscribed to {event_type}: {callback.__name__}")
    
    def unsubscribe(self, event_type: str, callback: Callable) -> None:
        """Unsubscribe from state change events."""
        if event_type in self._subscribers:
            self._subscribers[event_type].discard(callback)
            logger.debug(f"Unsubscribed from {event_type}: {callback.__name__}")
    
    async def _notify_subscribers(self, event_type: str, data: Any = None) -> None:
        """Notify all subscribers of an event."""
        callbacks = self._subscribers.get(event_type, [])
        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(data)
                else:
                    callback(data)
            except Exception as e:
                logger.error(f"Error in {event_type} callback: {e}")
    
    async def update_from_backend(self, message: Dict[str, Any]) -> None:
        """Update internal state from backend WebSocket message."""
        async with self._lock:
            old_state = self._state
            new_state = PlaybackState(message)
            self._state = new_state
            
            logger.debug(f"State updated: {new_state}")
            
            # Emit appropriate events based on what changed
            await self._notify_subscribers("state_changed", new_state)
            
            if not old_state:
                return  # First state update, only emit general state_changed
            
            # Check for track changes
            if (old_state.current_track_index != new_state.current_track_index or
                old_state.current_album_id != new_state.current_album_id):
                await self._notify_subscribers("track_changed", new_state)
            
            # Check for playback state changes
            if old_state.is_playing != new_state.is_playing:
                await self._notify_subscribers("playback_changed", new_state)
            
            # Check for volume changes
            if (old_state.volume != new_state.volume or
                old_state.is_mute != new_state.is_mute):
                await self._notify_subscribers("volume_changed", new_state)
            
            # Check for connection status changes
            if old_state.backend_connected != new_state.backend_connected:
                await self._notify_subscribers("connection_changed", new_state)
    
    async def notify_connection_lost(self) -> None:
        """Notify that backend connection was lost."""
        async with self._lock:
            if self._state:
                self._state.backend_connected = False
                await self._notify_subscribers("connection_changed", self._state)
    
    async def notify_connection_restored(self) -> None:
        """Notify that backend connection was restored."""
        async with self._lock:
            if self._state:
                self._state.backend_connected = True
                await self._notify_subscribers("connection_changed", self._state)
    
    @property
    def state(self) -> Optional[PlaybackState]:
        """Get current state (read-only snapshot)."""
        return self._state
    
    @property
    def is_playing(self) -> bool:
        """Check if currently playing."""
        return self._state.is_playing if self._state else False
    
    @property
    def current_track(self) -> Dict[str, Any]:
        """Get current track info."""
        return self._state.current_track if self._state else {}
    
    @property
    def volume(self) -> int:
        """Get current volume level (0-100)."""
        return self._state.volume if self._state else 50
    
    @property
    def is_muted(self) -> bool:
        """Check if currently muted."""
        return self._state.is_mute if self._state else False
    
    @property
    def brightness(self) -> int:
        """Get display brightness level (0-100)."""
        return self._state.brightness if self._state else 100
    
    @property
    def backend_connected(self) -> bool:
        """Check if backend is connected."""
        return self._state.backend_connected if self._state else False
    
    @property
    def progress_percent(self) -> float:
        """Get playback progress as percentage (0-100)."""
        if not self._state or self._state.total_time == 0:
            return 0.0
        return min(100.0, (self._state.elapsed_time / self._state.total_time) * 100)
    
    def __repr__(self) -> str:
        """String representation."""
        return f"StateManager({self._state})"
