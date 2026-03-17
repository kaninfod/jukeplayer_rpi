import logging
#from os import name
#from app.ui.theme import UITheme
from app.ui.screens.base import Screen
#from PIL import Image
from app.ui.screens.base import Screen, RectElement, TextElement, ImageElement
#import os
#from app.config import config

logger = logging.getLogger(__name__)
class IdleScreen(Screen):

    def __init__(self, theme, width=480, height=320):
        super().__init__(width, height)
        self.theme = theme
        self.event_type = "show_idle"
        self.name = "Idle Screen"


    @staticmethod
    def show(context=None):
        """Emit an event to show the home screen via the event bus."""
        from app.core import event_bus, EventType, Event
        event_bus.emit(Event(
            type=EventType.SHOW_IDLE,
            payload={}
        ))

        # from app.core import event_bus, EventFactory
        # event_bus.emit(EventFactory.show_idle())
        logger.info(f"EventBus: Emitted 'show_idle' event from IdleScreen.show()")

    def draw(self, draw_context, fonts, context=None, image=None):
        box = (0, 0, self.width, self.height)
        background_element = RectElement(*box, "white")
        background_element.draw(draw_context)

        icon_name = "klangmeister"
        #path = config.get_image_path(icon_name)
        #logger.debug(f"IdleScreen drawing image from path: {path}")
        #img = self._load_image(path)
        
        # box = (0, 0, self.width, self.height)
        # image_element = ImageElement(*box, iconname=icon_name)
        # image_element.draw(draw_context, image)

        box = (170, 180, 200, 50)
        screen_title_element = TextElement(*box, "Siemens", fonts["title"])
        screen_title_element.draw(draw_context)
        logger.info("IdleScreen drawn")
        
        box = (170, 200, 200, 50)
        screen_title_element = TextElement(*box, "Klangmeister", fonts["title"])
        screen_title_element.draw(draw_context)
        logger.info("IdleScreen drawn")
        
        box = (170, 220, 200, 50)
        screen_title_element = TextElement(*box, "RG 406", fonts["title"])
        screen_title_element.draw(draw_context)
        logger.info("IdleScreen drawn")                          

    # def _load_image(self, path):
    #     """Load album image from local cache if available."""
    #     if not path:
    #         return None

    #     logger.debug(f"Loading album image from: {path}")
    #     if os.path.exists(path):
    #         try:
    #             _image = Image.open(path)
    #             return _image
    #         except Exception as e:
    #             logger.error(f"Failed to load cached album image: {e}")
    #             return None
    #     else:
    #         return None            