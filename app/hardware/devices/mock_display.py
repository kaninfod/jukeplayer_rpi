"""
Mock display device for headless operation.
Used when hardware is not available or HARDWARE_MODE is disabled.
"""
import logging

logger = logging.getLogger(__name__)

class MockDevice:
    """Mock device object to match luma display interface"""
    def __init__(self):
        self.width = 480
        self.height = 320
    
    def display(self, image):
        """Mock device display method"""
        logger.debug(f"📺 MockDevice: Would display image to device")

class MockDisplay:
    """Mock display that logs operations instead of rendering to hardware"""
    
    def __init__(self):
        """Initialize mock display"""
        self.width = 480
        self.height = 320
        self.device = MockDevice()  # Compatibility with luma display interface
        logger.info("🖥️  MockDisplay initialized for headless operation")
    
    def display(self, image):
        """Mock display operation - logs instead of rendering"""
        if hasattr(image, 'size'):
            logger.debug(f"📺 MockDisplay: Would render image {image.size}")
        else:
            logger.debug("📺 MockDisplay: Would render image")
    
    def clear(self):
        """Mock clear operation"""
        logger.debug("📺 MockDisplay: Screen cleared")
    
    def show(self):
        """Mock show operation"""
        logger.debug("📺 MockDisplay: Screen updated")
    
    def cleanup(self):
        """Mock cleanup operation"""
        logger.info("🖥️  MockDisplay: Cleanup complete")
