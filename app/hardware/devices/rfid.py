
from pirc522 import RFID
import RPi.GPIO as GPIO
import threading
import time
from app.config import config
import logging

logger = logging.getLogger(__name__)

class RC522Reader:
    def __init__(self, cs_pin=7, on_new_uid=None):
        """
        Initialize RC522 RFID reader with switch-triggered reading.
        
        Args:
            cs_pin: Chip select pin for RC522 (default: 7)
            on_new_uid: Callback function called when new UID is detected
        """
        

        self.cs_pin = cs_pin
        self.on_new_uid = on_new_uid
        self.rdr = None
        self.initialized = False
        self.reading_active = False
        self.read_thread = None
        self.stop_reading = False
        self._result_callback = None
        
        try:
            GPIO.setwarnings(False)
            GPIO.setmode(GPIO.BCM)
            #GPIO.setup(self.cs_pin, GPIO.OUT)
            self.rdr = RFID(bus=0, device=1, pin_mode=GPIO.BCM)
            self.initialized = True
            logger.info("RFID reader initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize RFID reader: {e}")
            logger.warning("Attempting to continue without RFID functionality...")
            self.initialized = False

        logger.info("RC522 RFID Reader with switch-triggered reading initialized")

    def start_reading(self, result_callback=None):
        """Start RFID reading process with timeout. Accepts a result_callback(status_dict) to be called when done."""
        logger.debug(f"start_reading called. initialized={self.initialized}, reading_active={self.reading_active}")
        if not self.initialized:
            logger.error("RFID reader not initialized, cannot start reading")
            return False

        if self.reading_active:
            logger.warning("RFID reading already in progress")
            return False

        logger.info(f"Starting RFID read with {config.RFID_READ_TIMEOUT}s timeout...")
        self.reading_active = True
        self.stop_reading = False
        self._result_callback = result_callback

        logger.debug("Spawning RFID read thread...")
        # Start reading in separate thread
        self.read_thread = threading.Thread(target=self._read_with_timeout, daemon=True)
        self.read_thread.start()

        logger.debug("RFID read thread started.")
        return True

    def _read_with_timeout(self):
        """Read RFID with timeout in separate thread. Calls self._result_callback(status_dict) when done."""
        logger.debug("_read_with_timeout thread started.")
        start_time = time.time()
        read_attempts = 0
        status = None
        try:
            while not self.stop_reading and (time.time() - start_time) < config.RFID_READ_TIMEOUT:
                try:
                    read_attempts += 1
                    logger.debug(f"RFID read attempt {read_attempts}")
                    # Check for RFID tag
                    uid = self.rdr.read_id(True)
                    logger.debug(f"RFID read_id returned: {uid}")
                    if uid is not None:
                        # Successfully read tag
                        logger.info(f"✅ RFID read successful after {read_attempts} attempts: {uid}")
                        self._stop_reading_internal()
                        if self.on_new_uid:
                            logger.debug(f"Calling on_new_uid callback with UID: {uid}")
                            self.on_new_uid(uid)
                        status = {"status": "success", "uid": uid}
                        break
                    time.sleep(0.2)
                except Exception as e:
                    logger.error(f"RFID read error: {e}")
                    time.sleep(0.1)
            if status is None:
                # Timeout reached without successful read
                elapsed = time.time() - start_time
                logger.warning(f"❌ RFID read timeout after {elapsed:.1f}s ({read_attempts} attempts)")
                status = {"status": "timeout", "error_message": "Card read timeout. Please try again."}
        except Exception as e:
            logger.error(f"RFID reading thread error: {e}")
            status = {"status": "error", "error_message": f"Reading error: {str(e)}"}
        self._stop_reading_internal()
        # Call the result callback if provided
        logger.debug(f"Calling result callback with status: {status}")
        if self._result_callback:
            try:
                logger.info(f"Calling result callback with status: {status}")
                self._result_callback(status)
            except Exception as cb_e:
                logger.error(f"RFID result callback error: {cb_e}")
        self._result_callback = None


    
    def _stop_reading_internal(self):
        """Internal method to stop reading"""
        self.stop_reading = True
        self.reading_active = False
        logger.info("🛑 RFID reading stopped")

    def stop_reading_external(self):
        """External method to stop reading (can be called from outside)"""
        if self.reading_active:
            logger.info("Manually stopping RFID reading...")
            self._stop_reading_internal()
            
            # Wait for thread to finish
            if self.read_thread and self.read_thread.is_alive():
                self.read_thread.join(timeout=config.RFID_THREAD_JOIN_TIMEOUT)
    
    def is_reading(self):
        """Check if RFID reading is currently active"""
        return self.reading_active
    
    def stop(self):
        """Stop the RFID reader and cleanup"""
        logger.info("Stopping RFID reader...")
        # Stop any active reading
        self.stop_reading_external()
        # Cleanup RFID reader
        if self.rdr:
            try:
                self.rdr.cleanup()
                logger.info("RFID reader cleaned up")
            except Exception as e:
                logger.error(f"Error cleaning up RFID reader: {e}")
        # No pigpio cleanup needed
        self.initialized = False
        logger.info("RFID reader stopped")

    def cleanup(self):
        """Alias for stop() for consistency with other devices"""
        self.stop()