import logging
import board
import keypad
import threading
import time

logger = logging.getLogger(__name__)

# BCM to board pin mapping
_BCM_PIN_MAP = {
    4: board.D4, 5: board.D5, 6: board.D6, 7: board.D7,
    8: board.D8, 9: board.D9, 10: board.D10, 11: board.D11,
    12: board.D12, 13: board.D13, 14: board.D14, 15: board.D15,
    16: board.D16, 17: board.D17, 18: board.D18, 19: board.D19,
    20: board.D20, 21: board.D21, 22: board.D22, 23: board.D23,
    24: board.D24, 25: board.D25, 26: board.D26, 27: board.D27,
}


class ButtonManager:
    """Singleton managing all buttons with single keypad instance and thread."""
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._buttons = {}
        self._pin_to_index = {}
        self._keys = None
        self._monitor_thread = None
        self._running = False
        self._initialized = True
        logger.info("ButtonManager initialized")
    
    def register_all_buttons(self, button_configs):
        """Register multiple buttons at once (preferred method)."""
        with self._lock:
            for pin, config in button_configs:
                self._buttons[pin] = {
                    'callback': config.get('callback'),
                    'press_callback': config.get('press_callback'),
                    'long_press_callback': config.get('long_press_callback'),
                    'long_press_threshold': config.get('long_press_threshold', 3.0),
                    'bouncetime': config.get('bouncetime', 200),
                    'pull_up_down': config.get('pull_up_down', True),
                    'press_time': None
                }
            logger.info(f"Registered {len(button_configs)} buttons: GPIOs {sorted([p for p, _ in button_configs])}")
        
        self._initialize_keypad()
    
    def register_button(self, pin, callback=None, press_callback=None, long_press_callback=None, 
                       long_press_threshold=1.5, bouncetime=200, pull_up_down=True):
        """Register single button (use register_all_buttons for batch)."""
        with self._lock:
            is_new = pin not in self._buttons
            self._buttons[pin] = {
                'callback': callback,
                'press_callback': press_callback,
                'long_press_callback': long_press_callback,
                'long_press_threshold': long_press_threshold,
                'bouncetime': bouncetime,
                'pull_up_down': pull_up_down,
                'press_time': None
            }
        
        if is_new:
            self._initialize_keypad()
    
    def _initialize_keypad(self):
        """Initialize keypad with all registered buttons."""
        if not self._buttons:
            return
        
        if self._running:
            self._stop_monitoring()
        
        try:
            pins = []
            self._pin_to_index.clear()
            
            for idx, pin in enumerate(sorted(self._buttons.keys())):
                pins.append(_BCM_PIN_MAP[pin])
                self._pin_to_index[pin] = idx
            
            bouncetime = max(btn['bouncetime'] for btn in self._buttons.values())
            
            self._keys = keypad.Keys(
                pins=tuple(pins),
                value_when_pressed=False,
                pull=True,
                interval=bouncetime / 1000.0
            )
            
            logger.info(f"Keypad initialized: {len(pins)} buttons on GPIOs {sorted(self._buttons.keys())}")
            
            self._running = True
            self._monitor_thread = threading.Thread(target=self._event_loop, daemon=True)
            self._monitor_thread.start()
            
        except Exception as e:
            logger.error(f"Keypad init failed: {e}", exc_info=True)
            self._running = False
            self._keys = None
            raise
    
    def _event_loop(self):
        """Monitor button events."""
        logger.info("Button monitoring started")
        
        while self._running and self._keys:
            try:
                # Non-blocking check with small sleep for clean shutdown
                event = self._keys.events.get()
                if not event:
                    time.sleep(0.05)  # 50ms - responsive but low CPU
                    continue
                
                # Find which button triggered the event
                pin = next((p for p, idx in self._pin_to_index.items() if idx == event.key_number), None)
                if not pin or pin not in self._buttons:
                    continue
                
                btn = self._buttons[pin]
                
                if event.pressed:
                    btn['press_time'] = time.monotonic()
                    if btn['press_callback']:
                        try:
                            btn['press_callback']()
                        except Exception as e:
                            logger.error(f"Press callback error GPIO {pin}: {e}")
                
                elif event.released and btn['press_time']:
                    duration = time.monotonic() - btn['press_time']
                    btn['press_time'] = None
                    
                    if duration >= btn['long_press_threshold'] and btn['long_press_callback']:
                        logger.info(f"GPIO {pin} long press ({duration:.2f}s)")
                        try:
                            btn['long_press_callback']()
                        except Exception as e:
                            logger.error(f"Long press callback error GPIO {pin}: {e}")
                    elif btn['callback']:
                        logger.info(f"GPIO {pin} short press ({duration:.2f}s)")
                        try:
                            btn['callback']()
                        except Exception as e:
                            logger.error(f"Callback error GPIO {pin}: {e}")
                    
            except Exception as e:
                logger.error(f"Event loop error: {e}")
                time.sleep(0.1)
        
        logger.info("Button monitoring stopped")
    
    def _stop_monitoring(self):
        """Stop monitoring thread."""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=1.0)
        if self._keys:
            try:
                self._keys.deinit()
            except Exception as e:
                logger.error(f"Keypad deinit error: {e}")
            self._keys = None
    
    def cleanup(self):
        """Clean up resources."""
        self._stop_monitoring()
        self._buttons.clear()
        self._pin_to_index.clear()


class PushButton:
    """Lightweight wrapper for ButtonManager. Register via manager.register_all_buttons() first."""
    
    def __init__(self, pin, callback=None, press_callback=None, long_press_callback=None, 
                 long_press_threshold=3.0, bouncetime=200, pull_up_down=True):
        self.pin = pin
        manager = ButtonManager()
        
        # Only register if not already registered (via register_all_buttons)
        if pin not in manager._buttons:
            manager.register_button(pin, callback, press_callback, long_press_callback,
                                  long_press_threshold, bouncetime, pull_up_down)
