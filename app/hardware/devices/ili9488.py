import logging
logger = logging.getLogger(__name__)
from luma.core.interface.serial import spi
from luma.lcd.device import ili9488
from luma.core.render import canvas
from luma.core.framebuffer import diff_to_previous
from PIL import Image, ImageDraw, ImageFont
from luma.core.render import canvas
from app.config import config
import lgpio

# Example: open GPIO chip and set pin mode
# h = lgpio.gpiochip_open(0)  # Open first GPIO chip
# lgpio.gpio_claim_input(h, pin_number, lgpio.SET_PULL_UP)
# value = lgpio.gpio_read(h, pin_number)
# lgpio.gpiochip_close(h)

class ILI9488:
    def __init__(self):
        # Initialize display with backlight control
        # Note: The backlight turns OFF during device initialization and the 
        # device.backlight() method doesn't seem to work with our hardware setup
        self.serial = spi(
            port=0,
            device=0,
            gpio_CS=config.DISPLAY_GPIO_CS,
            gpio_DC=config.DISPLAY_GPIO_DC,
            gpio_RST=config.DISPLAY_GPIO_RST,
            bus_speed_hz=48000000
        )
        self.device = ili9488(self.serial, 
                             rotate=2, 
                             gpio_LIGHT=config.DISPLAY_BACKLIGHT_GPIO, 
                             active_low=False,
                             framebuffer=diff_to_previous())
        #self.canvas = canvas(self.device)
        # Try to turn backlight on, but this may not work with our hardware
        try:
            # logger.info("Attempting to draw to display")
            # with canvas(self.device) as draw:
            #     draw.rectangle(self.device.bounding_box, outline="white", fill="black")
            #     draw.text((30, 40), "Hello World", fill="red")
            self.power_on()  # Ensure backlight is on if control fails
            logger.info("Display: Power turned on")
            self.turn_on_backlight()  
            logger.info("Backlight turned on")
        except Exception as e:
            logger.warning(f"Backlight control may not work: {e}")
        try:
            self.font = ImageFont.truetype("/home/pi/shared/jukebox/fonts/opensans/OpenSans-Regular.ttf", 30)
        except (OSError, ImportError) as e:
            logger.warning(f"Font loading failed: {e}, using default font")
            self.font = ImageFont.load_default()

        # Clear the display to black after initialization to avoid garbage/partial frames
        try:
            from PIL import Image
            black = Image.new('RGB', (self.device.width, self.device.height), 'black')
            self.device.display(black)
            logger.info("Display cleared to black after initialization")
        except Exception as e:
            logger.warning(f"Display clear after init failed: {e}")

        logger.info("ILI9488 display initialized")


    def cleanup(self):
        """Clean up GPIO resources (normal cleanup for app restart)"""
        try:
            self.device.backlight(False)
            logger.info("Display: Backlight turned off")
        except Exception as e:
            logger.error(f"Display: Failed to turn off backlight: {e}")
        logger.info("Display cleanup: luma will handle all GPIO cleanup")

    def turn_off_backlight(self):
        """Turn off the display backlight"""
        try:
            self.device.backlight(False)
            logger.info("Display: Backlight turned off")
        except Exception as e:
            logger.error(f"Display: Failed to turn off backlight: {e}")

    def turn_on_backlight(self):
        """Turn on the display backlight"""
        try:
            self.device.backlight(True)
            logger.info("Display: Backlight turned on")
        except Exception as e:
            logger.error(f"Display: Failed to turn on backlight: {e}")

    def power_off(self):
        """Turn off the display using hardware power switching via S8550 transistor"""
        try:
            logger.info("Display: Attempting hardware power OFF...")
            self.gpio_handle = lgpio.gpiochip_open(0)
            #lgpio.gpio_claim_input(self.gpio_handle, config.DISPLAY_POWER_GPIO)
            logger.info("Display: Hardware power OFF (S8550 transistor)")
        except Exception as e:
            logger.error(f"Display: Hardware power OFF failed: {e}")
    
    def power_on(self):
        """Turn on the display using hardware power switching via S8550 transistor"""
        try:
            logger.info("Display: Attempting hardware power ON...")
            self.gpio_handle = lgpio.gpiochip_open(0)
            #lgpio.gpio_claim_output(self.gpio_handle, config.DISPLAY_POWER_GPIO)
            #lgpio.gpio_write(self.gpio_handle, config.DISPLAY_POWER_GPIO, 0)  # LOW
            logger.info("Display: Hardware power ON (S8550 transistor)")
        except Exception as e:
            logger.error(f"Display: Hardware power ON failed: {e}")
    def cleanup(self):
        if hasattr(self, 'gpio_handle'):
            lgpio.gpiochip_close(self.gpio_handle)

    # def display_image(self, text: str):
    #     with canvas(self.device) as draw:
    #         draw.rectangle(self.device.bounding_box, outline="green", fill="white")
    #         draw.text((30, 40), text, font=self.font, fill="green")
