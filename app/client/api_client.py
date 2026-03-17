"""
Backend API Client for Pi Client
Handles HTTP requests to the backend server for music control and status.
"""

import httpx
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class BackendAPIClient:
    """HTTP client for communicating with Jukeplayer backend server."""
    
    def __init__(self, backend_url: str, timeout: float = 10.0):
        """
        Initialize API client.
        
        Args:
            backend_url: Base URL of backend server (e.g., "http://192.168.1.100:8000")
            timeout: Request timeout in seconds
        """
        self.base_url = backend_url.rstrip("/")
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Make HTTP request to backend.
        
        Args:
            method: HTTP method (GET, POST, DELETE)
            endpoint: API endpoint (e.g., "/api/mediaplayer/next_track")
            json_data: JSON body for POST requests
            params: Query parameters
            
        Returns:
            Response JSON as dict
            
        Raises:
            httpx.HTTPError: If request fails
        """
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = await self.client.request(
                method,
                url,
                json=json_data,
                params=params
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"API request failed: {method} {endpoint} - {e}")
            raise
    
    # Playback control methods
    
    async def next_track(self) -> Dict[str, Any]:
        """Play next track."""
        return await self._make_request("POST", "/api/mediaplayer/next_track")
    
    async def previous_track(self) -> Dict[str, Any]:
        """Play previous track."""
        return await self._make_request("POST", "/api/mediaplayer/previous_track")
    
    async def play_pause(self) -> Dict[str, Any]:
        """Toggle play/pause."""
        return await self._make_request("POST", "/api/mediaplayer/play_pause")
    
    async def stop(self) -> Dict[str, Any]:
        """Stop playback."""
        return await self._make_request("POST", "/api/mediaplayer/stop")
    
    async def play_track(self, track_index: int) -> Dict[str, Any]:
        """Play specific track by index."""
        return await self._make_request(
            "POST",
            "/api/mediaplayer/play_track",
            json_data={"track_index": track_index}
        )
    
    async def play_album_from_albumid(
        self,
        album_id: str,
        start_track_index: int = 0
    ) -> Dict[str, Any]:
        """Play album by ID, optionally starting at specific track."""
        return await self._make_request(
            "POST",
            f"/api/mediaplayer/play_album_from_albumid/{album_id}",
            params={"start_track_index": start_track_index}
        )
    
    async def play_album_from_rfid(self, rfid: str) -> Dict[str, Any]:
        """Play album using RFID card ID."""
        return await self._make_request(
            "POST",
            f"/api/mediaplayer/play_album_from_rfid/{rfid}"
        )
    
    # Volume control
    
    async def volume_up(self) -> Dict[str, Any]:
        """Increase volume."""
        return await self._make_request("POST", "/api/mediaplayer/volume_up")
    
    async def volume_down(self) -> Dict[str, Any]:
        """Decrease volume."""
        return await self._make_request("POST", "/api/mediaplayer/volume_down")
    
    async def set_volume(self, level: int) -> Dict[str, Any]:
        """Set volume to specific level (0-100)."""
        return await self._make_request(
            "POST",
            "/api/mediaplayer/volume_set",
            params={"volume": level}
        )
    
    async def volume_mute(self) -> Dict[str, Any]:
        """Toggle mute."""
        return await self._make_request("POST", "/api/mediaplayer/volume_mute")
    
    # Display control (if backend has it)
    
    async def set_brightness(self, level: int) -> Dict[str, Any]:
        """Set display brightness (0-100)."""
        return await self._make_request(
            "POST",
            "/api/display/brightness",
            params={"level": level}
        )
    
    async def get_brightness(self) -> Dict[str, Any]:
        """Get current brightness."""
        return await self._make_request("GET", "/api/display/brightness")
    
    # Status queries
    
    async def get_status(self) -> Dict[str, Any]:
        """Get current playback status."""
        return await self._make_request("GET", "/api/mediaplayer/status")
    
    async def get_system_status(self) -> Dict[str, Any]:
        """Get system status."""
        return await self._make_request("GET", "/api/system/operations/status")
    
    # System control
    
    async def request_shutdown(self) -> Dict[str, Any]:
        """Request system shutdown."""
        return await self._make_request("POST", "/api/system/shutdown")
    
    async def request_reboot(self) -> Dict[str, Any]:
        """Request system reboot."""
        return await self._make_request("POST", "/api/system/reboot")
    
    async def request_restart(self) -> Dict[str, Any]:
        """Request service restart."""
        return await self._make_request("POST", "/api/system/restart")
    
    async def close(self):
        """Close HTTP client connection."""
        await self.client.aclose()
