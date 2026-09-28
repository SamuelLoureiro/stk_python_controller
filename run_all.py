"""
Unified runner: launches steer, face tracking, and voice input threads.
Forwards all commands over UDP to STK_input_server_v2.
"""

import socket
import time
import sys

from config import STK_SERVER_ADDRESS

# Reused socket for all outgoing UDP commands
_udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


def send_command(command: str):
    """Sends a UDP command packet to the server."""
    try:
        _udp_socket.sendto(command.encode('utf8'), STK_SERVER_ADDRESS)
    except Exception as e:
        print(f"[run_all] Error sending command '{command}': {e}")


from steer_module import start_steer
from face_module import FaceWorker
from voice_module import VoiceWorker


def main():
    print()
    print("=" * 65)
    print("🏎️  SUPER TUX KART — UNIFIED CONTROLLER")
    print("=" * 65)
    print(f"  Target server: {STK_SERVER_ADDRESS[0]}:{STK_SERVER_ADDRESS[1]}")
    print("  * 📱 Phone (OSC :8000)   -> Analog Wheel (STEER) & Accelerate/Brake")
    print("  * 🎤 Voice (Microphone)  -> 'turbo' (NITRO) & 'fire' (FIRE)")
    print("  * 📷 Face (Webcam)       -> Eyebrows (LOOK_BACK), Head Tilt (DRIFT), Nod (RESCUE)")
    print()
    print("  Press Ctrl+C at any time to shut down safely.")
    print("=" * 65)
    print()

    # Spin up input workers
    steer_stop = start_steer(send_command)

    face_worker = FaceWorker(send_command)
    face_worker.start()

    voice_worker = VoiceWorker(send_command)
    voice_worker.start()

    print(">>> All modules started successfully! <<<\n")

    try:
        # Keep main thread alive while workers run
        while face_worker.is_alive():
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n\n[run_all] Shutdown requested by user (Ctrl+C)...")
    finally:
        print("[run_all] Stopping modules...")
        steer_stop()
        face_worker.stop()
        voice_worker.stop()

        face_worker.join(timeout=2.0)
        voice_worker.join(timeout=2.0)

        # Center wheel and drop any held keys so the kart doesn't keep moving
        print("[run_all] Centering steering wheel and releasing active keys...")
        send_command("STEER:0.0000")
        for cmd in ["R_ACCELERATE", "R_BRAKE", "R_LOOKBACK", "R_SKIDDING"]:
            send_command(cmd)

        _udp_socket.close()
        print("✅ System shut down successfully! No keys remained stuck.\n")


if __name__ == "__main__":
    main()
