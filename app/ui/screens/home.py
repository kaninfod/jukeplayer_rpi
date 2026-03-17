import logging
import os
from app.ui.screens.base import Screen, RectElement, TextElement, ImageElement
from app.core import PlayerStatus
from app.config import config
from app.core.service_container import get_service

logger = logging.getLogger(__name__)

class HomeScreen(Screen):
    def __init__(self, theme):
        super().__init__()
        self.name = "Home Screen"
        self.theme = theme
        
        # Get singleton MediaPlayer service once at init
        self.player = get_service("media_player_service")
        
        # Cache for display values - updated on each draw() from player
        self._volume = 25
        self._player_status = PlayerStatus.STANDBY
        self._artist_name = "Unknown Artist"
        self._album_name = "Unknown Album"
        self._album_year = "----"
        self._track_title = "No Track"
        self._album_id = None
        self._output_device = "No Device"
        
    @staticmethod
    def show(context=None):
        """Emit an event to show the home screen via the event bus."""
        from app.core import event_bus, EventType, Event
        event_bus.emit(Event(
            type=EventType.SHOW_HOME,
            payload=context
        ))
        logger.info(f"EventBus: Emitted 'show_home' event from HomeScreen.show()")

    def draw(self, draw_context, fonts, context=None, image=None):
        """
        Draw the home screen with live data from MediaPlayer.
        
        HomeScreen directly queries the MediaPlayer for current state,
        ensuring we always display the most current information.
        This eliminates timing issues from event-based context passing.
        """
        logger.debug(f"HomeScreen.draw() called. Player: {self.player}, Current track: {self.player.current_track if self.player else 'N/A'}")
        
        # Only render if there's a track playing
        if not (self.player and self.player.current_track):
            logger.debug(f"Returning early - player: {self.player}, track: {self.player.current_track if self.player else 'N/A'}")
            return {"dirty": False}

        # Fetch fresh state from MediaPlayer
        try:
            # Read current player state directly
            current_track = self.player.current_track
            if current_track:
                self._artist_name = current_track.get('artist', 'Unknown Artist')
                self._track_title = current_track.get('title', 'No Track')
                self._album_id = current_track.get('album_cover_filename')
                self._album_name = current_track.get('album', 'Unknown Album')
                self._album_year = str(current_track.get('year', '----'))
                self._volume = self.player.volume if self.player.volume is not None else 25
                self._player_status = self.player.status if self.player.status else PlayerStatus.STANDBY
                backend = self.player.playback_backend if self.player else None
                self._output_device = backend.device_name if backend else 'No Device'
        except Exception as e:
            logger.warning(f"Error fetching player state: {e}, No redraw of Home screen.")
            return {"dirty": False}


        _volume_bar_width = self.theme.home_layout["volume_bar"]["width"] #15
        _volume_bar_height = self.theme.home_layout["volume_bar"]["height"] #200

        box = (0, 0, self.width, self.height)
        background_element = RectElement(*box, "white")
        background_element.draw(draw_context)

        box = (20, 10, 200, 50)
        screen_title_element = TextElement(*box, self.name, fonts["title"])
        screen_title_element.draw(draw_context)

        box = (200, 10, 200, 50)
        screen_title_element = TextElement(*box, self._output_device, fonts["title"])
        screen_title_element.draw(draw_context)

        box = (20, 60, 180, 180)
        album_cover_element = ImageElement(*box, album_id=self._album_id, size=180)
        album_cover_element.draw(draw_context, image)

        box = (20, 245, 400, 10)
        track_title_label_element = TextElement(*box, "Current track:", fonts["small"])
        track_title_label_element.draw(draw_context)

        box = (20, 255, 400, 65)
        track_title_element = TextElement(*box, self._track_title, fonts["title"])
        track_title_element.draw(draw_context)

        box = (210, 60, 240, 60)
        artist_name_element = TextElement(*box, self._artist_name, fonts["title"])
        artist_name_element.draw(draw_context)

        box = (210, 120, 240, 60)
        album_with_year = f"{self._album_name} ({self._album_year})"
        album_name_element = TextElement(*box, album_with_year, fonts["title"])
        album_name_element.draw(draw_context)

        box = (450, 60, _volume_bar_width, _volume_bar_height)
        volume_rect_outer = RectElement(*box, "grey")
        volume_rect_outer.draw(draw_context)

        _volume = int((self._volume / 100) * (_volume_bar_height - 4))
        box = (451, 258 - _volume, _volume_bar_width-2, _volume)
        volume_rect_inner = RectElement(*box, "green")
        volume_rect_inner.draw(draw_context)

        box = (450, 260, 30, 20)
        volume_value_element = TextElement(*box, f"{self._volume}%", fonts["small"])
        volume_value_element.draw(draw_context)

        icon_name = self._convert_player_status_to_icon_name()
        box = (450, 280, 30, 30)
        player_status_element = ImageElement(*box, iconname=icon_name)
        player_status_element.draw(draw_context, image)

        return {"dirty": False}

    def _use_defaults(self):
        """Set display values to safe defaults when player data unavailable."""
        self._artist_name = 'Unknown Artist'
        self._track_title = 'No Track'
        self._album_id = None
        self._album_name = 'Unknown Album'
        self._album_year = '----'
        self._output_device = 'No Device'
        self._volume = 0
        self._player_status = PlayerStatus.STANDBY




    def _convert_player_status_to_icon_name(self):
        """Map player status to icon name."""
        icon_map = {
            PlayerStatus.PLAY: "play_circle",
            PlayerStatus.PAUSE: "pause_circle",
            PlayerStatus.STOP: "stop_circle",
            PlayerStatus.STANDBY: "standby_settings"
        }
        return icon_map.get(self._player_status, "error")
