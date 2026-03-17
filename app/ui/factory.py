import logging
from app.ui.screens.message import MessageScreen
from app.ui.theme import UITheme
from app.ui.screens.idle import IdleScreen
from app.ui.screens.home import HomeScreen

logger = logging.getLogger(__name__)

def screen_factory(theme):
    screens = {
        "idle": IdleScreen(theme),
        "home": HomeScreen(theme),
        "message_screen": MessageScreen(theme),
    }
    return screens