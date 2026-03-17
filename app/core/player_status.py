from enum import Enum


class PlayerStatus(Enum):
    """Player playback status enumeration."""
    PLAY = "playing"
    PAUSE = "paused"
    STOP = "idle"
    STANDBY = "unavailable"
    OFF = "off"
