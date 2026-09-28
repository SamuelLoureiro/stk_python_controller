"""
Legacy runner for direct keyboard control (no UDP server needed).
Requires SuperTuxKart to be focused in the foreground.
"""

import time

from input_controller import KeyboardController
from face_module import FaceWorker
from voice_module import VoiceWorker


def main():
    controller = KeyboardController()
    face_worker = FaceWorker(controller)
    voice_worker = VoiceWorker(controller)

    print("Starting face + voice modules... (Ctrl+C to stop)")
    face_worker.start()
    voice_worker.start()

    try:
        while face_worker.is_alive():
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\nShutdown requested...")
    finally:
        face_worker.stop()
        voice_worker.stop()
        face_worker.join(timeout=2)
        voice_worker.join(timeout=2)
        controller.release_all()
        print("Clean shutdown, no keys left pressed.")


if __name__ == "__main__":
    main()
