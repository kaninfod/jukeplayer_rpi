import threading
import time
import logging
#from digitalio import DigitalInOut
#import board
#import busio
from adafruit_pn532.i2c import PN532_I2C

logger = logging.getLogger(__name__)


# Persistent I2C cache: shared across reads to preserve working state
class I2CCache:
    _instance = None
    _lock = threading.Lock()
    _cache = None
    _last_check_time = 0
    
    @classmethod
    def get_or_create(cls):
        """Get cached I2C or create new one. Thread-safe."""
        import threading
        with cls._lock:
            current_time = time.time()
            # Invalidate cache if more than 30 seconds old (health check)
            if cls._cache is not None and (current_time - cls._last_check_time) > 30:
                logger.debug("   ├─ I2C cache expired (30s+), creating fresh")
                try:
                    cls._cache.deinit()
                except:
                    pass
                cls._cache = None
            
            if cls._cache is None:
                logger.debug("   ├─ Creating I2C bus (persistent cache)")
                import busio, board
                
                # Create I2C with timeout protection - if it hangs, we need to detect it
                bus_created = threading.Event()
                i2c_bus = [None]  # Use list to capture in thread
                create_error = [None]
                
                def create_i2c_with_timeout():
                    try:
                        i2c_bus[0] = busio.I2C(board.SCL, board.SDA, frequency=100000)
                        bus_created.set()
                    except Exception as e:
                        create_error[0] = e
                        bus_created.set()
                
                create_thread = threading.Thread(target=create_i2c_with_timeout, daemon=True)
                create_thread.start()
                
                # Wait up to 2 seconds for I2C creation
                if bus_created.wait(timeout=2.0):
                    if create_error[0]:
                        logger.error(f"   ├─ I2C creation failed: {create_error[0]}")
                        raise create_error[0]
                    cls._cache = i2c_bus[0]
                    logger.debug("   ├─ I2C bus created successfully")
                else:
                    logger.error("   ├─ I2C creation timeout (bus initialization hanging)")
                    raise Exception("I2C bus creation timeout - hardware may be stuck")
                
                time.sleep(0.1)  # Let bus settle
                cls._last_check_time = current_time
            
            return cls._cache
    
    @classmethod
    def reset(cls):
        """Force reset of I2C cache (L2 recovery)."""
        import threading
        with cls._lock:
            logger.debug("   ├─ Force resetting I2C cache (L2 recovery)")
            if cls._cache is not None:
                try:
                    logger.debug("   │  ├─ Deinitializing I2C (with 1s timeout)")
                    deinit_completed = threading.Event()
                    
                    def deinit_with_timeout():
                        try:
                            cls._cache.deinit()
                            deinit_completed.set()
                        except Exception as e:
                            logger.warning(f"   │  ├─ Deinit thread error: {e}")
                            deinit_completed.set()
                    
                    deinit_thread = threading.Thread(target=deinit_with_timeout, daemon=True)
                    deinit_thread.start()
                    
                    # Wait up to 1 second for deinit to complete
                    if deinit_completed.wait(timeout=1.0):
                        logger.debug("   │  ├─ I2C deinit complete")
                    else:
                        logger.warning("   │  ├─ I2C deinit timeout (bus may be stuck) - forcing reset anyway")
                        
                except Exception as e:
                    logger.warning(f"   │  ├─ Error during deinit (non-fatal): {e}")
                
                cls._cache = None
                logger.debug("   │  ├─ Cache cleared, settling 300ms")
                time.sleep(0.3)  # Extended settling for full reset
            
            logger.debug("   │  └─ Recreating I2C bus")
            cls._cache = None  # Redundant but explicit
            return cls.get_or_create()


# One-shot PN532 reader: instantiate with fresh PN532 per read, but reuse I2C bus
class PN532Reader:
    # Class-level tracking for consecutive failures
    _consecutive_failures = 0
    _failure_lock = threading.Lock()
    
    def __init__(self, on_new_uid=None):
        self.on_new_uid = on_new_uid
        self._i2c = None  # Instance reference (from cache)
        self._pn532 = None  # Fresh PN532 instance
        logger.debug("PN532Reader instance created")

    def _init_pn532(self, recovery_level=0):
        """
        Initialize and return a PN532 instance (I2C).
        
        Recovery levels:
        - 0: Normal init (fresh PN532, reuse I2C from cache)
        - 1: Soft reset (fresh PN532, fresh I2C with settling)
        - 2: Hard reset (fresh PN532, force I2C cache reset)
        
        Returns: pn532 object
        Throws: Exception if initialization fails
        """
        from adafruit_pn532.i2c import PN532_I2C
        
        if recovery_level == 0:
            # Normal operation: use cached I2C
            logger.debug("   ├─ Initializing I2C bus (L0: normal, from cache)")
            self._i2c = I2CCache.get_or_create()
        elif recovery_level == 1:
            # L1 Soft reset: fresh PN532, reuse I2C but with extra settling
            logger.debug("   ├─ Initializing I2C bus (L1: soft reset, extra settling)")
            self._i2c = I2CCache.get_or_create()
            time.sleep(0.2)  # Extra settling for L1 recovery
        else:  # recovery_level == 2
            # L2 Hard reset: force I2C cache reset
            logger.debug("   ├─ Initializing I2C bus (L2: hard reset, cache reset)")
            self._i2c = I2CCache.reset()
        
        # Give the bus time to settle after retrieval/creation
        time.sleep(0.1)
        
        logger.debug("   ├─ Creating PN532_I2C instance")
        self._pn532 = PN532_I2C(self._i2c, debug=False)
        
        # Wait for PN532 to be ready
        time.sleep(0.2)
        
        logger.debug("   ├─ Running SAM configuration")
        # Scale SAM retry attempts and delays by recovery level
        max_sam_retries = 1 + recovery_level  # L0=1, L1=2, L2=3 retries
        for sam_attempt in range(max_sam_retries):
            try:
                self._pn532.SAM_configuration()
                logger.debug("   ├─ SAM configuration successful")
                break
            except Exception as e:
                if sam_attempt < max_sam_retries - 1:
                    # Longer wait at higher recovery levels
                    wait_time = 0.15 + (recovery_level * 0.1)
                    logger.warning(f"   ├─ SAM config attempt {sam_attempt + 1}/{max_sam_retries} failed, retrying in {wait_time:.2f}s: {e}")
                    time.sleep(wait_time)
                else:
                    logger.error(f"   ├─ SAM config failed after {max_sam_retries} attempts")
                    raise
        
        # Verify reader is actually responsive before polling for cards
        if not self._verify_i2c_ready(max_retries=2):
            raise Exception("PN532 reader not responsive after SAM configuration")
        
        logger.debug("   └─ PN532 hardware ready and responsive")
        return self._pn532        

    def start_reading(self, result_callback=None):
        """
        Instantiates and initializes the PN532, performs a single read, then reads only configured blocks, then cleans up.
        Includes 3-level recovery: L1 (PN532 soft reset), L2 (I2C hard reset), L3 (system signal).
        
        Recovery strategy:
        - Timeout (no card detected): Not a system error, don't retry
        - Exception (SAM config, auth failure): System error, retry with recovery
        
        Returns UID and named block data in a dict.
        """
        from app.config import Config
        status = None
        
        # Attempt read with retry logic (only for exceptions, not timeouts)
        max_retries = 3
        for attempt in range(max_retries):
            recovery_level = min(attempt, 2)  # 0, 1, 2 for attempts 0, 1, 2+
            
            try:
                if attempt == 0:
                    logger.info("4. HARDWARE READ PROCESS")
                else:
                    logger.info(f"4. HARDWARE READ PROCESS (Retry {attempt}/{max_retries-1}, L{recovery_level} recovery)")
                
                pn532 = self._init_pn532(recovery_level=recovery_level)
                
                logger.info("   ├─ Polling for card (5 second timeout)")
                uid = self._poll_for_card(pn532, timeout=5)
                
                if uid is None:
                    # Timeout is a card issue, not a system error - don't retry
                    logger.warning("   ├─ Timeout: No card detected")
                    status = {"status": "timeout", "error_message": "Card read timeout. Please try again.", "attempt": attempt}
                    break  # Don't retry timeouts - they indicate bad card positioning
                else:
                    uid_number = 0
                    for b in uid:
                        uid_number = (uid_number << 8) | b
                    logger.info(f"   ├─ Card detected with UID: {hex(uid_number)}")
                    
                    MIFARE_CMD_AUTH_A = 0x60
                    key = b'\xFF\xFF\xFF\xFF\xFF\xFF'
                    block_data = {}
                    
                    logger.info("   ├─ Reading configured blocks:")
                    for name, block in Config.RFID_BLOCKS.items():
                        try:
                            logger.debug(f"   │  ├─ Reading block {block} ({name})")
                            data = self._read_block(pn532, uid, block, key, MIFARE_CMD_AUTH_A)
                            block_data[name] = self.decode_block_to_string(data)
                            logger.debug(f"   │  │  └─ Value: {block_data[name]}")
                        except Exception as e:
                            logger.warning(f"   │  ├─ Block {block} ({name}) read failed: {e}")
                            block_data[name] = None
                    
                    logger.info("   └─ All blocks read successfully")
                    status = {"status": "success", "uid": uid_number, "blocks": block_data, "attempt": attempt}
                    self._reset_consecutive_failure()  # Success resets failure counter
                    break
                    
            except Exception as e:
                # Exception indicates system issue (SAM config, auth, etc.) - these get retries
                logger.error(f"   ├─ System error (attempt {attempt}): {e}", exc_info=False)
                status = {"status": "error", "error_message": f"System error: {type(e).__name__}", "attempt": attempt}
                
                # Retry on system errors with escalating recovery
                if attempt < max_retries - 1:
                    logger.info(f"   ├─ Triggering L{recovery_level + 1} recovery on next attempt")
                    continue
                else:
                    # All retries exhausted - this is a cascade
                    self._record_consecutive_failure()
                    status["system_reset_needed"] = self._check_cascade_and_signal()
                    break
        
        if result_callback:
            logger.info("   └─ Calling result_callback()")
            try:
                result_callback(status)
            except Exception as cb_e:
                logger.error(f"   ❌ Result callback error: {cb_e}", exc_info=True)

    def _poll_for_card(self, pn532, timeout=10):
        """Poll for a card with two-stage strategy: aggressive initially, then normal.
        
        Strategy:
        - Settle time: 500ms for magnetic field to stabilize
        - First 500ms: aggressive polling every 50ms (card likely already positioned)
        - After 500ms: normal polling every 100ms (extended wait for late insertions)
        """
        # Wait for magnetic field to stabilize after card insertion
        logger.debug("   ├─ Settling magnetic field (500ms)...")
        time.sleep(0.5)
        logger.debug("   ├─ Field settled, starting polling")
        
        start_time = time.time()
        uid = None
        poll_count = 0
        aggressive_window = 0.5  # First 500ms with tight polling
        poll_responses = []  # Track last few responses for diagnostics
        
        while (time.time() - start_time) < timeout:
            uid = pn532.read_passive_target(timeout=0.5)
            poll_count += 1
            
            if uid is not None:
                elapsed = time.time() - start_time
                logger.info(f"   │  └─ Card found on poll attempt {poll_count} after {elapsed:.2f}s")
                return uid
            
            # Track response (None = no card detected)
            poll_responses.append(None)
            if len(poll_responses) > 5:
                poll_responses.pop(0)  # Keep last 5 responses
            
            elapsed = time.time() - start_time
            if elapsed < aggressive_window:
                # Aggressive phase: tight 50ms polling (card expected soon/already there)
                time.sleep(0.05)
            else:
                # Normal phase: standard 100ms polling (extended wait)
                time.sleep(0.1)
        
        # Timeout - provide detailed diagnostics
        elapsed = time.time() - start_time
        logger.warning(f"   └─ Poll timeout: {poll_count} attempts over {elapsed:.2f}s (limit: {timeout}s)")
        logger.warning(f"   └─ Polling phases: {int(aggressive_window*1000)}ms aggressive + {(timeout-aggressive_window)*1000:.0f}ms normal")
        logger.warning(f"   └─ Last poll responses: none detected (card may not be in field)")
        return None

    def _record_consecutive_failure(self):
        """Record a consecutive failure and check if cascade prevention is needed."""
        with PN532Reader._failure_lock:
            PN532Reader._consecutive_failures += 1
            logger.warning(f"   ├─ Consecutive failure #{PN532Reader._consecutive_failures}")
    
    def _reset_consecutive_failure(self):
        """Reset consecutive failure counter on success."""
        with PN532Reader._failure_lock:
            if PN532Reader._consecutive_failures > 0:
                logger.info(f"   ├─ Reset: consecutive failure counter ({PN532Reader._consecutive_failures} → 0)")
            PN532Reader._consecutive_failures = 0
    
    def _check_cascade_and_signal(self):
        """Check if cascade threshold reached and signal system reset recommendation."""
        with PN532Reader._failure_lock:
            if PN532Reader._consecutive_failures >= 3:
                logger.error(f"   ├─ ⚠️  SYSTEM SIGNAL: {PN532Reader._consecutive_failures} consecutive failures - system reset recommended")
                logger.error(f"   └─ Cascade detected - consider system reboot to clear I2C/PN532 state")
                return True
        return False
    
    def _verify_i2c_ready(self, max_retries=3):
        """Verify I2C/PN532 is actually ready by attempting a non-blocking poll."""
        for attempt in range(max_retries):
            try:
                logger.debug(f"   ├─ Verifying reader responsiveness (attempt {attempt + 1}/{max_retries})")
                # Try a simple non-blocking read to verify reader is communicating
                # This is the actual operation we'll be using, so it's a good litmus test
                self._pn532.read_passive_target(timeout=0.1)
                logger.debug(f"   ├─ Reader responsive: poll command succeeded\")")
                return True
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.debug(f"   ├─ Reader not responsive yet, waiting 50ms before retry: {e}")
                    time.sleep(0.05)
                else:
                    logger.warning(f"   ├─ Reader responsiveness verification FAILED after {max_retries} attempts")
                    return False
        return False

    def _read_block(self, pn532, uid, block_number, key=b'\xFF\xFF\xFF\xFF\xFF\xFF', mifare_cmd=0x60):
        """Authenticate and read a block, return bytes or None."""
        logger.debug(f"   │  ├─ Authenticating block {block_number}")
        auth = pn532.mifare_classic_authenticate_block(uid, block_number, mifare_cmd, key)
        if not auth:
            logger.warning(f"   │  └─ Authentication failed for block {block_number}")
            return None
        return pn532.mifare_classic_read_block(block_number)
    
    def _validate_card_ready(self, pn532, uid, key=b'\xFF\xFF\xFF\xFF\xFF\xFF', mifare_cmd=0x60):
        """
        Pre-write validation: attempt single auth to block 0 to verify card is ready.
        Block 0 is manufacturer block (read-only), uses same default key as user blocks.
        Returns True if auth succeeds, False if key mismatch suspected.
        Raises Exception for unexpected errors.
        
        NOTE: No sleep after validation - auth session must remain fresh for immediate write.
        """
        try:
            logger.debug("   ├─ Pre-write validation: attempting auth on block 0 (manufacturer block)")
            # Try to authenticate block 0 (manufacturer block, should work with default key)
            auth = pn532.mifare_classic_authenticate_block(uid, 0, mifare_cmd, key)
            if auth:
                logger.debug("   ├─ Pre-write validation: SUCCESS - card is ready (auth session active)")
                # NO sleep here - keep auth session fresh for immediate write to user block
                return True
            else:
                # Auth failed - might be wrong key
                logger.warning("   ├─ Pre-write validation: FAILED - authentication failed on block 0")
                logger.warning("   ├─ ⚠️  Possible causes: card has different auth key, or card is locked")
                return False
        except Exception as e:
            logger.error(f"   ├─ Pre-write validation: unexpected error: {e}")
            raise
    
    @staticmethod
    def encode_string_for_block(s):
        """Encode a string to 16 bytes for Mifare Classic block (pad/truncate as needed)."""
        return s.encode("utf-8")[:16].ljust(16, b' ')

    @staticmethod
    def decode_block_to_string(block_bytes):
        """Decode a 16-byte block to a string, stripping padding."""
        if not block_bytes:
            return None
        return block_bytes.decode("utf-8", errors="replace").rstrip(' ')
        
    def _perform_write_operation(self, pn532, data_dict, uid, key=b'\xFF\xFF\xFF\xFF\xFF\xFF'):
        """
        Helper: Perform actual write operation on a detected card.
        Returns: UID number on success, raises Exception on write failure.
        
        Args:
            pn532: PN532 instance
            data_dict: dict of {name: value} to write
            uid: card UID bytes
            key: Mifare authentication key (default: 0xFF*6, factory default)
        """
        from app.config import Config
        MIFARE_CMD_AUTH_A = 0x60
        
        uid_number = 0
        for b in uid:
            uid_number = (uid_number << 8) | b
        
        logger.info(f"   ├─ Card detected with UID: {hex(uid_number)}")
        
        # Pre-write validation: quick auth check before starting write sequence
        logger.info("   ├─ Pre-write validation")
        is_ready = self._validate_card_ready(pn532, uid, key, MIFARE_CMD_AUTH_A)
        if not is_ready:
            raise Exception("Pre-write validation failed: card not ready or wrong authentication key")
        
        # Write each configured block
        block_data = {}
        blocks_written = []  # Track successful writes for better error reporting
        logger.info("   ├─ Writing configured blocks:")
        for name, block_number in Config.RFID_BLOCKS.items():
            try:
                value = data_dict.get(name, "")
                data = self.encode_string_for_block(value)
                
                logger.debug(f"   │  ├─ Authenticating block {block_number} ({name}) for write")
                auth = pn532.mifare_classic_authenticate_block(uid, block_number, MIFARE_CMD_AUTH_A, key)
                
                if not auth:
                    raise Exception(f"Authentication failed for block {block_number} ({name})")
                
                logger.debug(f"   │  ├─ Writing to block {block_number} ({name}): {value}")
                write_ok = pn532.mifare_classic_write_block(block_number, data)
                
                if not write_ok:
                    raise Exception(f"Write operation failed for block {block_number} ({name})")
                
                block_data[name] = value
                blocks_written.append(f"{block_number}({name})")
                logger.debug(f"   │  │  └─ Successfully wrote: {value}")
                
                # Clear auth state between block operations (150ms settle time)
                time.sleep(0.15)
                
            except Exception as e:
                # Log what we've written so far for debugging
                if blocks_written:
                    logger.warning(f"   │  ├─ Partial write detected - succeeded on: {', '.join(blocks_written)}")
                logger.warning(f"   │  ├─ Block {block_number} ({name}) write failed: {e}")
                block_data[name] = None
                raise  # Propagate to retry logic
        
        logger.info(f"   └─ All {len(blocks_written)} blocks written successfully")
        return uid_number, block_data

    def write_data(self, data_dict, timeout=5, result_callback=None):
        """
        Write a dict of {name: value} to the configured RFID blocks.
        Includes 3-level recovery matching read strategy: L0/L1/L2.
        
        Recovery strategy:
        - Timeout (no card detected): Not a system error, don't retry
        - Exception (auth failure, write error, ACK error): System error, retry with recovery
        
        - data_dict: dict with keys matching config.RFID_BLOCKS (e.g., {"album_id": "al-123"})
        - timeout: seconds to wait for card per attempt
        - result_callback: optional callback to receive final status
        
        Returns: dict with status, uid, blocks, and attempt count
        """
        from app.config import Config
        status = None
        
        try:
            # Attempt write with retry logic (only for exceptions, not timeouts)
            max_retries = 3
            for attempt in range(max_retries):
                recovery_level = min(attempt, 2)  # 0, 1, 2 for attempts 0, 1, 2+
                
                try:
                    if attempt == 0:
                        logger.info("4. HARDWARE WRITE PROCESS")
                    else:
                        logger.info(f"4. HARDWARE WRITE PROCESS (Retry {attempt}/{max_retries-1}, L{recovery_level} recovery)")
                    
                    pn532 = self._init_pn532(recovery_level=recovery_level)
                    
                    logger.info(f"   ├─ Polling for card ({timeout} second timeout)")
                    uid = self._poll_for_card(pn532, timeout=timeout)
                    
                    if uid is None:
                        # Timeout is a card issue, not a system error - don't retry
                        logger.warning("   ├─ Timeout: No card detected")
                        status = {"status": "timeout", "error_message": "Card write timeout. Please try again.", "attempt": attempt}
                        break  # Don't retry timeouts - they indicate bad card positioning
                    else:
                        # Card found, perform write operation
                        # Note: key parameter can be extended here if different keys are needed
                        uid_number, block_data = self._perform_write_operation(pn532, data_dict, uid)
                        
                        status = {"status": "success", "uid": uid_number, "blocks": block_data, "attempt": attempt}
                        self._reset_consecutive_failure()  # Success resets failure counter
                        break
                        
                except Exception as e:
                    error_str = str(e)
                    
                    # Check if this is an authentication failure (card issue, not hardware)
                    is_auth_error = "Authentication failed" in error_str or "key mismatch" in error_str.lower()
                    
                    if is_auth_error:
                        # Auth failures are card problems, not recoverable with I2C reset
                        logger.error(f"   ├─ Card authentication failed: {e}")
                        status = {
                            "status": "error",
                            "error_message": f"Card authentication failed - card may have different key or be locked",
                            "error_type": "AUTH_FAILURE",
                            "attempt": attempt
                        }
                        break  # Don't retry auth failures - they won't be fixed by recovery
                    else:
                        # Hardware/system errors get recovery attempts
                        logger.error(f"   ├─ System error (attempt {attempt}): {e}", exc_info=False)
                        status = {"status": "error", "error_message": f"System error: {type(e).__name__}: {str(e)}", "attempt": attempt}
                        
                        # Retry on system errors with escalating recovery
                        if attempt < max_retries - 1:
                            logger.info(f"   ├─ Triggering L{recovery_level + 1} recovery on next attempt")
                            continue
                        else:
                            # All retries exhausted - this is a cascade
                            self._record_consecutive_failure()
                            status["system_reset_needed"] = self._check_cascade_and_signal()
                            break
        
        finally:
            # ALWAYS call result_callback, even if unexpected exception occurs
            if result_callback:
                logger.info("   └─ Calling result_callback()")
                try:
                    result_callback(status)
                except Exception as cb_e:
                    logger.error(f"   ❌ Result callback error: {cb_e}", exc_info=True)
        
    def cleanup(self):
        """
        Clean up PN532 instance (fresh each read).
        Preserve I2C cache for next read - only dereferencing, no deinit.
        """
        try:
            if self._pn532:
                self._pn532 = None
                logger.debug("   ├─ PN532 instance dereferenced")
        except Exception as e:
            logger.warning(f"   ├─ Error cleaning PN532: {e}")
        
        # Give PN532 time to finish any pending operations
        time.sleep(0.05)
        
        # I2C is now cached at class level - don't deinit here
        # This preserves the working I2C state for next read
        logger.debug("   ├─ I2C bus preserved in cache (not deinitialized)")
        
        logger.debug("   └─ Cleanup complete (PN532 fresh, I2C cached for next operation)")