"""
Connection Monitor for Pi Client
Tracks backend connection health and handles reconnection logic.
"""

import asyncio
import logging
from typing import Callable, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ConnectionMonitor:
    """Monitors backend connection and handles reconnection."""
    
    def __init__(
        self,
        ws_client,
        heartbeat_interval: int = 30,
        reconnect_delay: int = 2,
        max_reconnect_attempts: int = 0,
    ):
        """
        Initialize connection monitor.
        
        Args:
            ws_client: WebSocket client instance
            heartbeat_interval: Seconds between heartbeats
            reconnect_delay: Initial seconds to wait before reconnection attempts
            max_reconnect_attempts: Max reconnection attempts (0 = infinite)
        """
        self.ws_client = ws_client
        self.heartbeat_interval = heartbeat_interval
        self.reconnect_delay = reconnect_delay
        self.max_reconnect_attempts = max_reconnect_attempts
        
        self.is_monitoring = False
        self.is_connected = False
        self.reconnect_count = 0
        self.last_heartbeat = None
        
        self._monitor_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._connection_callbacks = []
        self._disconnection_callbacks = []
        
        logger.info(
            f"ConnectionMonitor initialized: "
            f"heartbeat={heartbeat_interval}s, "
            f"reconnect_delay={reconnect_delay}s, "
            f"max_attempts={max_reconnect_attempts}"
        )
    
    def on_connected(self, callback: Callable) -> None:
        """Register callback for connection events."""
        self._connection_callbacks.append(callback)
    
    def on_disconnected(self, callback: Callable) -> None:
        """Register callback for disconnection events."""
        self._disconnection_callbacks.append(callback)
    
    async def _notify_connected(self) -> None:
        """Notify all connection callbacks."""
        for callback in self._connection_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()
            except Exception as e:
                logger.error(f"Error in connection callback: {e}")
    
    async def _notify_disconnected(self, reason: str) -> None:
        """Notify all disconnection callbacks."""
        for callback in self._disconnection_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(reason)
                else:
                    callback(reason)
            except Exception as e:
                logger.error(f"Error in disconnection callback: {e}")
    
    async def _heartbeat_loop(self) -> None:
        """Periodic heartbeat to detect connection health."""
        while self.is_monitoring:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                
                if self.ws_client.is_connected():
                    self.last_heartbeat = datetime.now()
                    logger.debug("Heartbeat OK")
                else:
                    logger.warning("Heartbeat failed: not connected")
                    if self.is_connected:
                        await self._on_disconnected("Heartbeat failed")
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}")
    
    async def _reconnect_loop(self) -> None:
        """Handle reconnection attempts with exponential backoff."""
        while self.is_monitoring:
            try:
                if not self.ws_client.is_connected() and self.is_connected:
                    await self._on_disconnected("Connection lost")
                
                if not self.ws_client.is_connected() and not self.is_connected:
                    # Try to reconnect
                    if (self.max_reconnect_attempts == 0 or
                        self.reconnect_count < self.max_reconnect_attempts):
                        
                        # Linear backoff with 2x multiplier, capped at 60 seconds
                        # Progression: 2s → 4s → 8s → 16s → 32s → 60s → 60s → ...
                        delay = min(
                            self.reconnect_delay * (2 ** self.reconnect_count),
                            60  # Cap at 1 minute (much faster than the previous 5 min)
                        )
                        
                        logger.info(
                            f"Reconnection attempt {self.reconnect_count + 1}, "
                            f"waiting {delay}s..."
                        )
                        
                        await asyncio.sleep(delay)
                        
                        try:
                            logger.info("Attempting to reconnect...")
                            await self.ws_client.connect()
                            
                            if self.ws_client.is_connected():
                                self.reconnect_count = 0
                                await self._on_connected()
                                logger.info("Reconnected successfully")
                            else:
                                self.reconnect_count += 1
                        
                        except Exception as e:
                            logger.error(f"Reconnection failed: {e}")
                            self.reconnect_count += 1
                    else:
                        logger.error(
                            f"Max reconnection attempts ({self.max_reconnect_attempts}) reached"
                        )
                        await asyncio.sleep(10)  # Wait before checking again
                else:
                    await asyncio.sleep(1)
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in reconnect loop: {e}")
                await asyncio.sleep(1)
    
    async def _on_connected(self) -> None:
        """Handle connection established."""
        if not self.is_connected:
            self.is_connected = True
            logger.info("Backend connected")
            await self._notify_connected()
    
    async def _on_disconnected(self, reason: str) -> None:
        """Handle connection lost."""
        if self.is_connected:
            self.is_connected = False
            logger.warning(f"Backend disconnected: {reason}")
            await self._notify_disconnected(reason)
    
    async def start(self) -> None:
        """Start monitoring connection."""
        if self.is_monitoring:
            logger.warning("Monitor already running")
            return
        
        self.is_monitoring = True
        logger.info("Starting connection monitor")
        
        # Initial connection check
        if self.ws_client.is_connected():
            await self._on_connected()
        
        # Start background tasks
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self._monitor_task = asyncio.create_task(self._reconnect_loop())
    
    async def stop(self) -> None:
        """Stop monitoring connection."""
        if not self.is_monitoring:
            return
        
        self.is_monitoring = False
        logger.info("Stopping connection monitor")
        
        # Cancel background tasks
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
    
    def get_status(self) -> dict:
        """Get current monitor status."""
        return {
            "is_monitoring": self.is_monitoring,
            "is_connected": self.is_connected,
            "reconnect_count": self.reconnect_count,
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "uptime_seconds": (
                (datetime.now() - self.last_heartbeat).total_seconds()
                if self.last_heartbeat
                else 0
            ),
        }
    
    def __repr__(self) -> str:
        """String representation."""
        status = "connected" if self.is_connected else "disconnected"
        return f"ConnectionMonitor({status}, reconnects={self.reconnect_count})"
