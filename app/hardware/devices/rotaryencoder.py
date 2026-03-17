import board
from ruhrohrotaryio import IncrementalEncoder as rotaryio_IncrementalEncoder
import threading
import time
import logging

logger = logging.getLogger(__name__)

class RotaryEncoder:
    """
    Rotary encoder using CircuitPython rotaryio module.
    
    Relies entirely on rotaryio's built-in detent detection and debouncing.
    The IncrementalEncoder handles all quadrature decoding and only reports
    position changes when a complete detent is registered.
    """
    def __init__(self, pin_a, pin_b, callback=None, bouncetime=80):
        self.pin_a = pin_a
        self.pin_b = pin_b
        self.callback = callback
        self.position = 0
        self.bouncetime = bouncetime / 1000.0  # Convert ms to seconds
        
        self._lock = threading.Lock()
        self._last_position = 0
        self._last_reported_position = 0  # Position of last *reported* event
        self._last_reported_direction = 0  # Last direction we fired a callback for
        self._position_changed_time = None
        self._direction_lock_time = None  # When we lock into current direction
        
        self._monitor_thread = None
        self._running = False
        self.encoder = None
        
        try:
            # Convert BCM pin numbers to board pins
            board_pin_a = self._bcm_to_board_pin(pin_a)
            board_pin_b = self._bcm_to_board_pin(pin_b)
            
            # Create IncrementalEncoder
            # divisor=4 means 1 click per detent for KY-040
            # rotaryio handles all debouncing and detent logic internally
            self.encoder = rotaryio_IncrementalEncoder(board_pin_a, board_pin_b, divisor=4)
            self._last_position = self.encoder.position
            
            self.initialized = True
            logger.info(f"RotaryEncoder initialized on GPIO {self.pin_a}/{self.pin_b} using rotaryio (divisor=4)")
            logger.debug(f"Initial position: {self._last_position}")
            
            # Start monitoring thread
            self._running = True
            self._monitor_thread = threading.Thread(target=self._poll_position, daemon=True)
            self._monitor_thread.start()
            logger.debug("Polling thread started")
            
        except Exception as e:
            logger.error(f"Failed to initialize rotary encoder: {e}", exc_info=True)
            self.initialized = False

    def _bcm_to_board_pin(self, bcm_pin):
        """Convert BCM GPIO number to board.D pin."""
        bcm_map = {
            4: board.D4, 5: board.D5, 6: board.D6, 7: board.D7,
            8: board.D8, 9: board.D9, 10: board.D10, 11: board.D11,
            12: board.D12, 13: board.D13, 14: board.D14, 15: board.D15,
            16: board.D16, 17: board.D17, 18: board.D18, 19: board.D19,
            20: board.D20, 21: board.D21, 22: board.D22, 23: board.D23,
            24: board.D24, 25: board.D25, 26: board.D26, 27: board.D27,
        }
        return bcm_map[bcm_pin]

    def _poll_position(self):
        """Poll encoder position for detent clicks with debouncing and direction locking.
        
        Strategy:
        1. Detect position changes and start debounce window
        2. After debounce, check for net movement from last reported position
        3. Lock into current direction, filtering out brief opposite-direction oscillations
        4. Only switch directions after sufficient quiet time (800ms no opposite-direction movement)
        """
        direction_lock_timeout = 0.8  # 800ms - time to allow direction reversal
        
        while self._running and self.initialized:
            try:
                current_position = self.encoder.position
                current_time = time.time()
                
                with self._lock:
                    if current_position != self._last_position:
                        # Position changed - start debounce timer
                        if self._position_changed_time is None:
                            self._position_changed_time = current_time
                            logger.debug(
                                f"Position change detected: {self._last_position} -> {current_position} "
                                f"(starting debounce window: {self.bouncetime*1000:.0f}ms)"
                            )
                    
                    elif self._position_changed_time is not None:
                        # Position stable now - check if debounce window elapsed
                        time_elapsed = current_time - self._position_changed_time
                        
                        if time_elapsed >= self.bouncetime:
                            # Debounce complete - check for net movement
                            net_delta = self._last_position - self._last_reported_position
                            
                            if net_delta != 0:
                                new_direction = 1 if net_delta > 0 else -1
                                
                                # Check if we're in direction-locked state
                                if self._last_reported_direction != 0:
                                    # We have a locked direction
                                    time_since_lock = current_time - self._direction_lock_time if self._direction_lock_time else 0
                                    
                                    if new_direction == self._last_reported_direction:
                                        # Same direction - continue, refresh lock time
                                        self._direction_lock_time = current_time
                                        logger.info(
                                            f"Continuing {'+CW' if new_direction > 0 else '-CCW'}: {self._last_reported_position} -> {self._last_position} "
                                            f"(net_delta={net_delta:+d})"
                                        )
                                    
                                    elif time_since_lock >= direction_lock_timeout:
                                        # Opposite direction after timeout - allow reversal
                                        self._last_reported_direction = new_direction
                                        self._direction_lock_time = current_time
                                        logger.info(
                                            f"Direction reversal allowed: switching to {'+CW' if new_direction > 0 else '-CCW'} "
                                            f"(locked for {time_since_lock*1000:.0f}ms)"
                                        )
                                    else:
                                        # Opposite direction too soon - ignore (oscillation filter)
                                        logger.debug(
                                            f"Opposite direction ignored (in lock): {'+CW' if new_direction > 0 else '-CCW'} "
                                            f"(only {time_since_lock*1000:.0f}ms since lock, need {direction_lock_timeout*1000:.0f}ms)"
                                        )
                                        self._position_changed_time = None
                                        self._last_position = current_position
                                        time.sleep(0.01)
                                        continue
                                else:
                                    # First direction - establish lock
                                    self._last_reported_direction = new_direction
                                    self._direction_lock_time = current_time
                                    logger.info(
                                        f"Direction locked: {'+CW' if new_direction > 0 else '-CCW'} "
                                        f"({self._last_reported_position} -> {self._last_position})"
                                    )
                                
                                # Fire callback for locked direction
                                self.position = self._last_position
                                if self.callback:
                                    self.callback(self._last_reported_direction, self.position)
                                
                                self._last_reported_position = self._last_position
                            else:
                                logger.debug(f"Position oscillated back to {self._last_position} (net_delta=0, ignoring)")
                            
                            self._position_changed_time = None
                    
                    self._last_position = current_position
                        
            except Exception as e:
                logger.error(f"Error reading rotary encoder: {e}", exc_info=True)
            
            time.sleep(0.01)  # Poll every 10ms

    def get_position(self):
        """Get the current encoder position."""
        with self._lock:
            return self.position if self.initialized else 0

    def cleanup(self):
        """Stop the polling thread and clean up resources."""
        if not self.initialized:
            return
        try:
            logger.info(f"Cleaning up RotaryEncoder on GPIO {self.pin_a}/{self.pin_b}")
            self._running = False
            if self._monitor_thread:
                self._monitor_thread.join(timeout=1.0)
            if self.encoder:
                self.encoder.deinit()
            logger.info(f"RotaryEncoder cleanup complete (final position: {self.position})")
        except Exception as e:
            logger.error(f"Encoder cleanup error: {e}", exc_info=True)
