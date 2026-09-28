"""
Thread-safe keyboard controller for direct input emulation (legacy).
Supports continuous held keys and timed impulse taps.
"""

import threading
import time

from pynput.keyboard import Controller

from config import KEY_MAP, PULSE_HOLD_S


class KeyboardController:
    def __init__(self):
        self._keyboard = Controller()
        self._lock = threading.Lock()
        # Track which inputs are currently holding each key (OR logic)
        self._active_sources = {}
        self._currently_pressed = set()
        self._last_pulse_time = {}

    def set_continuous(self, action: str, source: str, active: bool):
        """Holds key as long as at least one source requests it."""
        if action not in KEY_MAP:
            return
        with self._lock:
            sources = self._active_sources.setdefault(action, set())
            if active:
                sources.add(source)
            else:
                sources.discard(source)

            should_be_pressed = len(sources) > 0
            is_pressed = action in self._currently_pressed

            if should_be_pressed and not is_pressed:
                self._keyboard.press(KEY_MAP[action])
                self._currently_pressed.add(action)
            elif not should_be_pressed and is_pressed:
                self._keyboard.release(KEY_MAP[action])
                self._currently_pressed.discard(action)

    def pulse(self, action: str, cooldown_s: float):
        """Brief press and release with an anti-spam cooldown."""
        if action not in KEY_MAP:
            return
        now = time.monotonic()
        with self._lock:
            last = self._last_pulse_time.get(action, 0.0)
            if now - last < cooldown_s:
                return
            self._last_pulse_time[action] = now

        # Release is handled via timer outside the lock to avoid blocking other threads
        key = KEY_MAP[action]
        self._keyboard.press(key)
        threading.Timer(PULSE_HOLD_S, lambda: self._keyboard.release(key)).start()

    def release_all(self):
        """Ensures all pressed keys are released on shutdown."""
        with self._lock:
            for action in list(self._currently_pressed):
                self._keyboard.release(KEY_MAP[action])
            self._currently_pressed.clear()
            self._active_sources.clear()
