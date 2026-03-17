import threading
import time
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class QueuedScreen:
	def __init__(self, screen_type: str, context: Dict[str, Any], duration: float):
		self.screen_type = screen_type
		self.context = context
		self.duration = duration

class ScreenQueue:
	"""
	Simple screen queue for timed feedback.
	- Manages a list of screens with durations.
	- No background tasks.
	- When queue is empty, shows home or idle screen based on playback state.
	"""
	def __init__(self, screen_manager):
		self.screen_manager = screen_manager
		self.queue: List[QueuedScreen] = []
		self.current_screen: Optional[QueuedScreen] = None
		self.timer_thread: Optional[threading.Thread] = None
		self.lock = threading.Lock()
		self.running = False

	def add_screen(self, screen_type: str, context: Dict[str, Any], duration: float):
		with self.lock:
			self.queue.append(QueuedScreen(screen_type, context, duration))
			logger.info(f"[ScreenQueue] Added to queue: {screen_type} (duration: {duration}s, queue length: {len(self.queue)})")
			if not self.running:
				logger.info("[ScreenQueue] Starting queue processing thread.")
				self._start_processing()

	def _start_processing(self):
		self.running = True
		logger.info("[ScreenQueue] Queue processing started.")
		self.timer_thread = threading.Thread(target=self._process_queue, daemon=True)
		self.timer_thread.start()

	def _process_queue(self):
		logger.info("[ScreenQueue] Processing queue...")
		while True:
			with self.lock:
				if not self.queue:
					logger.info("[ScreenQueue] Queue empty. Showing fallback screen.")
					self.running = False
					self._show_fallback_screen()
					break
				next_screen = self.queue.pop(0)
				self.current_screen = next_screen
				logger.info(f"[ScreenQueue] Displaying screen: {next_screen.screen_type} (duration: {next_screen.duration}s)")
			self._show_screen(next_screen)
			# If duration is None or 0, stay until next screen is queued
			if next_screen.duration is None or next_screen.duration == 0:
				logger.info(f"[ScreenQueue] No duration for {next_screen.screen_type}, waiting for next screen to be queued.")
				# Wait until a new screen is queued
				while True:
					with self.lock:
						if self.queue:
							logger.info("[ScreenQueue] New screen queued, moving on.")
							break
					time.sleep(0.1)
			else:
				logger.info(f"[ScreenQueue] Sleeping for {next_screen.duration}s after showing {next_screen.screen_type}.")
				time.sleep(next_screen.duration)
		logger.info("[ScreenQueue] Queue processing finished.")
		self.current_screen = None

	def _show_screen(self, queued_screen: QueuedScreen):
		screen_type = queued_screen.screen_type
		context = queued_screen.context
		logger.info(f"[ScreenQueue] Calling screen manager for type: {screen_type}")
		if screen_type == "message":
			self.screen_manager.show_message_screen(context)
		elif screen_type == "idle":
			self.screen_manager.show_idle_screen(context)
		elif screen_type == "home":
			self.screen_manager.show_home_screen(context)
		else:
			logger.warning(f"[ScreenQueue] Unknown screen type: {screen_type}")

	def _show_fallback_screen(self):
		# Show home if music is playing, else idle
		# Note: HomeScreen now fetches fresh data directly from MediaPlayer,
		# so passing empty context is fine - it will query player.current_track, etc.
		if self.screen_manager.is_music_playing():
			logger.info("[ScreenQueue] Fallback: Showing home screen (music playing)")
			self.screen_manager.show_home_screen({})
		else:
			logger.info("[ScreenQueue] Fallback: Showing idle screen (music not playing)")
			self.screen_manager.show_idle_screen({})

	def clear(self):
		with self.lock:
			self.queue.clear()
			logger.info(f"[ScreenQueue] Queue cleared. Current length: {len(self.queue)}")

	def skip_current(self):
		with self.lock:
			if self.timer_thread and self.timer_thread.is_alive():
				# Interrupt current sleep by restarting thread
				self.queue = self.queue[1:]  # Remove next screen if exists
				logger.info("[ScreenQueue] Skipped current screen. Restarting processing.")
				self._start_processing()

	def get_queue_status(self):
		with self.lock:
			status = {
				"current_screen": self.current_screen.screen_type if self.current_screen else None,
				"queue_length": len(self.queue),
				"queued_screens": [s.screen_type for s in self.queue]
			}
			logger.info(f"[ScreenQueue] Queue status: {status}")
			return status

	def cleanup(self):
		self.clear()
		self.running = False
		logger.info("[ScreenQueue] Cleanup complete.")
