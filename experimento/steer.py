"""
steer.py

Continuous Analog Controller for SuperTuxKart (Mario Kart Wii / Wii Wheel Style)

IMPLEMENTED IMPROVEMENTS:
  1. Real Analog Steering (No PWM / No Jitter):
     - Replaces key PWM with a continuous value (-1.0 to +1.0).
     - Sent via UDP to STK_input_server_v2.py, which maps to ABS_X axis of virtual joystick.
     - Kart wheels turn with complete fluidity at any angle.
  2. Exponential Sensitivity Curve (Expo Curve - x^1.4):
     - Stable center (3.5° dead zone) for micro-corrections and straight-line stability.
     - Progressively stronger turns at higher tilt, reaching 100% steering at 30°.
  3. Zero-Lag Adaptive Filter:
     - Fast arm movements have near-instant response (<15ms).
     - Slow movements or steady hands are filtered to eliminate sensor jitter.
  4. Quick 2-Finger Center Recalibration:
     - Touching with two fingers on screen (or both sides simultaneously) recalibrates neutral center.
     - Can also press ENTER or SPACE in PC terminal.

SETUP:
  1. On PC: python STK_input_server_v2.py
  2. On Phone (MultiSense Osc): Enable "Orientation" and "Pad" widget.
  3. On PC: python steer.py
  4. Hold phone in LANDSCAPE with screen facing you.
     Initial center is calibrated on first received value.
     Recalibrate anytime by tapping with 2 fingers on screen!
"""

import sys
import math
import socket
import threading
import time

from oscpy.server import OSCThreadServer

# ---------------------------------------------------------------------------
# Network Configuration UDP -> STK_input_server_v2.py
# ---------------------------------------------------------------------------
STK_ADDRESS   = ('localhost', 6006)
client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


def send_command(command):
    """Sends discrete commands (buttons) via UDP."""
    client_socket.sendto(command.encode('utf8'), STK_ADDRESS)
    if DEBUG_LOGS:
        print("Sent: {}".format(command))


def send_steer(value):
    """Sends continuous steering value from -1.0 (left) to +1.0 (right)."""
    cmd = "STEER:{:.4f}".format(value)
    client_socket.sendto(cmd.encode('utf8'), STK_ADDRESS)
    if DEBUG_LOGS:
        print("Sent: {}".format(cmd))


# ---------------------------------------------------------------------------
# SuperTuxKart Button Command Table
# ---------------------------------------------------------------------------
COMMANDS = {
    "ACCELERATE": ("P_ACCELERATE", "R_ACCELERATE"),
    "BRAKE":      ("P_BRAKE",      "R_BRAKE"),
}

# ---------------------------------------------------------------------------
# Fine-Tuning Parameters (Mario Kart Wii Style)
# ---------------------------------------------------------------------------
DEAD_ZONE            = 3.5    # Neutral tilt degrees (straight line stability without jitter)
MAX_STEER_ANGLE      = 30.0   # Degrees for max steering (100% axis deflection)
EXPO_GAMMA           = 1.4    # Exponential curve (1.4: smooth center, firm edges)
STEER_SEND_THRESHOLD = 0.005  # Minimum change (0.5%) to send UDP packet (avoids flood without lag)

# Steering and sensitivity
STEER_SIGN           = 1      # Change to -1 if left/right are inverted
TOUCH_TIMEOUT        = 0.35   # Seconds without touch message before releasing gas/brake
RECAL_COOLDOWN       = 0.8    # Minimum seconds between recalibrations

DEBUG_STEER          = False  # Display real-time angle and analog value telemetry
DEBUG_LOGS           = False  # Display sent UDP commands in console

# ---------------------------------------------------------------------------
# Shared State (Thread-Safe)
# ---------------------------------------------------------------------------
lock = threading.Lock()

pitch_origin     = None   # Calibrated neutral position (degrees)
smoothed_pitch   = None   # Dynamically filtered angle
last_sent_steer  = 0.0    # Last sent analog value (-1.0 to 1.0)

current_vertical = None   # "ACCELERATE" | "BRAKE" | None
last_touch_time  = 0.0

# Two-finger detection / double touch
last_left_touch  = 0.0
last_right_touch = 0.0
last_touch_x     = None
last_recal_time  = 0.0

# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------
def normalize_angle(angle):
    """Keeps angle difference within (-180, 180]."""
    while angle > 180:
        angle -= 360
    while angle <= -180:
        angle += 360
    return angle


def trigger_recalibrate(reason=""):
    """Resets the center (steering zero) to current orientation."""
    global pitch_origin, smoothed_pitch, last_recal_time
    global current_vertical, last_sent_steer

    now = time.time()
    if now - last_recal_time < RECAL_COOLDOWN:
        return

    with lock:
        last_recal_time = now
        if smoothed_pitch is not None:
            pitch_origin = smoothed_pitch

        # Temporarily release any active command for safety
        if current_vertical is not None:
            send_command(COMMANDS[current_vertical][1])
            current_vertical = None

        # Reset steering to center immediately
        send_steer(0.0)
        last_sent_steer = 0.0

    print("\n" + "=" * 55)
    print("🎯 CENTER RECALIBRATED! (New neutral: {:.1f}°) [{}]".format(
        pitch_origin if pitch_origin is not None else 0.0, reason))
    print("=" * 55 + "\n")


# ---------------------------------------------------------------------------
# Watchdog Thread: Releases Gas / Brake when finger is lifted
# ---------------------------------------------------------------------------
def release_watchdog():
    global current_vertical
    while True:
        time.sleep(0.04)
        with lock:
            if current_vertical is not None:
                if time.time() - last_touch_time > TOUCH_TIMEOUT:
                    send_command(COMMANDS[current_vertical][1])
                    print("👉 Touch: ⚪ RELEASED")
                    current_vertical = None


# ---------------------------------------------------------------------------
# Thread to recalibrate via Terminal Keyboard (Enter / Space)
# ---------------------------------------------------------------------------
def keyboard_listener_thread():
    while True:
        try:
            line = sys.stdin.readline()
            if line:
                trigger_recalibrate("PC terminal command")
        except Exception:
            break


# ---------------------------------------------------------------------------
# OSC Callbacks (Sensor and Touch Processing)
# ---------------------------------------------------------------------------
def on_pitch(*values):
    """
    Receives phone tilt, applies zero-lag adaptive filter,
    and sends continuous analog value (-1.0 to +1.0) to joystick axis.
    """
    global pitch_origin, smoothed_pitch, last_sent_steer

    if not values:
        return
    value = float(values[0])

    # Automatic calibration on first received value
    if pitch_origin is None:
        pitch_origin   = value
        smoothed_pitch = value
        print("\n🎮 Initial calibration complete! Neutral center at {:.1f}°.".format(pitch_origin))
        print("💡 Tip: Tap with 2 fingers on screen at any time to recalibrate the center.\n")
        return

    # Zero-Lag Adaptive Filter:
    # - Fast hand movement: alpha up to 0.85 (instant response, no lag).
    # - Still hand: alpha ~0.35 (eliminates sensor noise and tremors).
    diff = abs(value - smoothed_pitch)
    adaptive_alpha = min(0.85, max(0.35, 0.35 + (diff / 12.0) * 0.50))
    smoothed_pitch = adaptive_alpha * value + (1.0 - adaptive_alpha) * smoothed_pitch

    # Delta relative to calibrated neutral center
    delta = normalize_angle(smoothed_pitch - pitch_origin) * STEER_SIGN
    adelta = abs(delta)

    if adelta <= DEAD_ZONE:
        new_dir = None
        intensity = 0.0
        steer_value = 0.0
    else:
        new_dir = "RIGHT" if delta > 0 else "LEFT"
        # Normalization between 0.0 and 1.0 from deadzone to maximum angle
        norm = min(1.0, (adelta - DEAD_ZONE) / (MAX_STEER_ANGLE - DEAD_ZONE))
        # Exponential curve Mario Kart Wii style
        intensity = norm ** EXPO_GAMMA
        steer_value = intensity if delta > 0 else -intensity

    # Send with threshold filter to avoid flooding UDP, while ensuring exact return to center
    should_send = (abs(steer_value - last_sent_steer) >= STEER_SEND_THRESHOLD) or (steer_value == 0.0 and last_sent_steer != 0.0)
    if should_send:
        send_steer(steer_value)
        last_sent_steer = steer_value

    if DEBUG_STEER:
        bar_len = int(intensity * 20)
        bar = ("[" + "=" * bar_len + " " * (20 - bar_len) + "]") if new_dir else "[       CENTER       ]"
        print("delta={:+5.1f}° | steer={:+6.3f} | dir={:5s} | force={:4.0f}% {}".format(
            delta, steer_value, new_dir or "OFF", intensity * 100, bar))


def on_pad_x(*values):
    """
    Controls Gas / Brake and detects 2-finger touch for recalibration.
    """
    global current_vertical, last_touch_time, last_left_touch, last_right_touch, last_touch_x

    if not values:
        return

    # Case 1: MultiSense sends multiple touches in same OSC message
    if len(values) >= 2:
        trigger_recalibrate("Multi-touch detected (2 fingers)")
        return

    val = float(values[0])
    now = time.time()

    # Register touched side
    if val < -0.2:
        last_left_touch = now
    elif val > 0.2:
        last_right_touch = now

    # Case 2: Two fingers touching both sides of screen simultaneously (<120ms difference)
    # or abrupt jump from one side to the other (<80ms)
    is_bilateral = (abs(last_left_touch - last_right_touch) < 0.12 and
                    (now - min(last_left_touch, last_right_touch)) < 0.25)
    is_jump = (last_touch_x is not None and
               ((last_touch_x < -0.3 and val > 0.3) or (last_touch_x > 0.3 and val < -0.3)) and
               (now - last_touch_time < 0.08))

    last_touch_x    = val
    last_touch_time = now

    if is_bilateral or is_jump:
        trigger_recalibrate("2 fingers on screen (left + right)")
        return

    # Acceleration (right) / Brake (left)
    new_cmd = None
    if val < -0.15:
        new_cmd = "BRAKE"
    elif val > 0.15:
        new_cmd = "ACCELERATE"

    with lock:
        if new_cmd != current_vertical:
            if current_vertical is not None:
                send_command(COMMANDS[current_vertical][1])
            if new_cmd is not None:
                send_command(COMMANDS[new_cmd][0])
                print(f"👉 Touch: {'🟢 ACCELERATE' if new_cmd == 'ACCELERATE' else '🔴 BRAKE/REVERSE'}")
            elif current_vertical is not None:
                print("👉 Touch: ⚪ RELEASED")
            current_vertical = new_cmd


def on_multitouch_event(*values):
    """Captures any multi-touch event sent by MultiSense."""
    trigger_recalibrate("Multi-touch detected")


# ---------------------------------------------------------------------------
# OSC Server Initialization and Main Execution
# ---------------------------------------------------------------------------
def main():
    # Start auxiliary background threads (no PWM thread)
    threading.Thread(target=release_watchdog, daemon=True).start()
    threading.Thread(target=keyboard_listener_thread, daemon=True).start()

    PITCH_ADDRESS = b'/multisense/orientation/pitch'
    PAD_ADDRESS_X = b'/multisense/pad/x'

    osc  = OSCThreadServer()
    sock = osc.listen(address='0.0.0.0', port=8000, default=True)

    osc.bind(PITCH_ADDRESS, on_pitch)
    osc.bind(PAD_ADDRESS_X, on_pad_x)
    osc.bind(b'/multisense/pad/1/x', on_pad_x)

    # Additional bindings in case MultiSense sends specific multi-touch addresses
    osc.bind(b'/multisense/pad/touches', on_multitouch_event)
    osc.bind(b'/multisense/pad/2/x', on_multitouch_event)
    osc.bind(b'/multisense/pad/2/y', on_multitouch_event)
    osc.bind(b'/multisense/multitouch', on_multitouch_event)

    print()
    print("=" * 65)
    print("🏎️  SUPERTUXKART ANALOG CONTROLLER (VIRTUAL JOYSTICK)")
    print("=" * 65)
    print("  OSC Server listening on 0.0.0.0:8000 -> Sending to {}:{}".format(*STK_ADDRESS))
    print("  Mode: Continuous Analog Axis (No PWM / Zero-Lag)")
    print()
    print("  DRIVING INSTRUCTIONS:")
    print("    * Turn phone like a steering wheel to steer.")
    print("    * Straights: Neutral dead zone of {:.1f}° (no jitter).".format(DEAD_ZONE))
    print("    * Turns: Continuous exponential analog response (smooth center, firm edges).")
    print("    * Tap RIGHT half of screen -> ACCELERATE.")
    print("    * Tap LEFT half of screen  -> BRAKE / REVERSE.")
    print()
    print("  🎯 CENTER RECALIBRATION:")
    print("    * Tap with TWO FINGERS on screen at any time.")
    print("    * Or press ENTER / SPACE in this terminal.")
    print("=" * 65)
    print()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        with lock:
            if current_vertical is not None:
                send_command(COMMANDS[current_vertical][1])
                current_vertical = None
            send_steer(0.0)
        time.sleep(0.05)
        osc.stop()
        client_socket.close()
        print("\nsteer.py shut down successfully.")


if __name__ == '__main__':
    main()
