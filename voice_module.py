"""
Voice control module using Vosk for offline keyword spotting.
Maps spoken trigger words ("turbo", "fire") to game actions.
"""

import json
import queue
import threading
import time

import sounddevice as sd
import vosk

import config
from config import VOICE_ACTION_MAP, VOICE_COOLDOWN_S, VOICE_SAMPLE_RATE


class VoiceWorker(threading.Thread):
    def __init__(self, send_fn):
        super().__init__(daemon=True)
        self._send_fn = send_fn
        self._stop_event = threading.Event()
        self._audio_queue = queue.Queue()
        self._last_trigger_time = {}

    def stop(self):
        self._stop_event.set()

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            print(f"[voice] audio status: {status}")
        self._audio_queue.put(bytes(indata))

    def run(self):
        vosk.SetLogLevel(-1)
        model = vosk.Model(config.VOSK_MODEL_PATH)

        # Restrict grammar to only our trigger words so detection stays fast
        grammar_words = list(VOICE_ACTION_MAP.keys()) + ["[unk]"]
        grammar = json.dumps(grammar_words)
        recognizer = vosk.KaldiRecognizer(model, VOICE_SAMPLE_RATE, grammar)

        with sd.RawInputStream(
            samplerate=VOICE_SAMPLE_RATE,
            blocksize=4000,
            dtype="int16",
            channels=1,
            callback=self._audio_callback,
        ):
            while not self._stop_event.is_set():
                try:
                    data = self._audio_queue.get(timeout=0.5)
                except queue.Empty:
                    continue

                if recognizer.AcceptWaveform(data):
                    text = json.loads(recognizer.Result()).get("text", "")
                else:
                    text = json.loads(recognizer.PartialResult()).get("partial", "")

                self._check_keywords(text)

    def _check_keywords(self, text: str):
        if not text:
            return
        now = time.monotonic()
        words = text.lower().split()
        for word in words:
            udp_command = VOICE_ACTION_MAP.get(word)
            if udp_command:
                last = self._last_trigger_time.get(word, 0.0)
                if now - last >= VOICE_COOLDOWN_S:
                    self._last_trigger_time[word] = now
                    self._send_fn(udp_command)
                    print(f"[voice] '{word}' -> {udp_command}")
