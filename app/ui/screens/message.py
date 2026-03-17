import logging, os
from app.ui.theme import UITheme 
from app.config import config
from app.ui.screens.base import Screen, RectElement, TextElement, ImageElement
from PIL import Image

logger = logging.getLogger(__name__)

class MessageScreen(Screen):
    # event_type = "show_message_screen"
    # name = "Message Screen"

    """
    Generic message screen for displaying a title, icon, and message.
    Context keys:
        - title: str (title text)
        - icon_name: str (icon key from ICON_DEFINITIONS)
        - message: str or list of str (message lines)
        - color: str (optional, text color)
    """
    def __init__(self, theme, width=480, height=320):
        super().__init__(width, height)
        self.theme = theme
        self.screen_theme = None
        self.context = {}
        self.name = "Message Screen"

    @staticmethod
    def show(context=None):
        """Emit an event to show the home screen via the event bus."""
        from app.core import event_bus, EventType, Event
        event_bus.emit(Event(
            type=EventType.SHOW_MESSAGE,
            payload=context
        ))
        logger.info(f"EventBus: Emitted 'show_home' event from HomeScreen.show()")

    def draw(self, draw_context, fonts, context=None, image=None):
        self.context = context or {}
        theme = self.theme
        

        box = (0, 0, self.width, self.height)
        background_element = RectElement(*box, "white")
        background_element.draw(draw_context)

        box = (20, 30, 350, 50)
        title = self.context.get("title", "Message")
        screen_title_element = TextElement(*box, title, fonts["title"])
        screen_title_element.draw(draw_context)

        icon_name = self.context.get("icon_name", None)
        box = (150, 80, 120, 120)
        icon_element = ImageElement(*box, iconname=icon_name) #ImageElement(*box, img)
        icon_element.draw(draw_context, image)

        box = (20, 250, 350, 50)
        message = self.context.get("message", "")
        screen_message_element = TextElement(*box, message, fonts["info"])
        screen_message_element.draw(draw_context)

        return

