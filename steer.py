"""
Standalone steering script using high-frequency keyboard PWM.
Listens for phone orientation via OSC and pulses arrow keys to emulate analog turning.
"""

import sys
import math
import socket
import threading
import time

from oscpy.server import OSCThreadServer

STK_ADDRESS   = ('localhost', 6006)
client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


def send_command(command):
    client_socket.sendto(command.encode('utf8'), STK_ADDRESS)
    if DEBUG_LOGS:
        print("Sent: {}".format(command))


COMMANDS = {
    "LEFT":       ("P_LEFT",       "R_LEFT"),
    "RIGHT":      ("P_RIGHT",      "R_RIGHT"),
    "ACCELERATE": ("P_ACCELERATE", "R_ACCELERATE"),
    "BRAKE":      ("P_BRAKE",      "R_BRAKE"),
}

# Steering tuning
DEAD_ZONE           = 4.5    # ignore tilt below this to keep straight lines stable
MAX_STEER_ANGLE     = 30.0   # angle for 100% steering lock
EXPO_GAMMA          = 1.4    # exponential curve for finer control near center
FULL_LOCK_THRESHOLD = 0.88   # hold key continuously above 88% steering duty
MIN_DUTY_THRESHOLD  = 0.05   # completely release below 5%

# Micro-PWM settings (~18 Hz pulse rate)
PWM_PERIOD          = 0.055
MIN_PRESS_MS        = 0.022  # shortest press duration the game loop reliably detects

STEER_SIGN          = 1      # flip to -1 if left/right is inverted
TOUCH_TIMEOUT       = 0.20
RECAL_COOLDOWN      = 0.8

DEBUG_STEER         = False
DEBUG_LOGS          = False

lock = threading.Lock()

pitch_origin            = None
smoothed_pitch          = None
current_steer_dir       = None
current_steer_intensity = 0.0

current_vertical        = None
last_touch_time         = 0.0

# Tracking for 2-finger recalibration
last_left_touch         = 0.0
last_right_touch        = 0.0
last_touch_x            = None
last_recal_time         = 0.0


def normalize_angle(angle):
    while angle > 180:
        angle -= 360
    while angle <= -180:
        angle += 360
    return angle


def trigger_recalibrate(reason=""):
    """Resets neutral steering center to current phone tilt."""
    global pitch_origin, smoothed_pitch, last_recal_time
    global current_vertical, current_steer_dir, current_steer_intensity

    now = time.time()
    if now - last_recal_time < RECAL_COOLDOWN:
        return

    with lock:
        last_recal_time = now
        if smoothed_pitch is not None:
            pitch_origin = smoothed_pitch

        # drop active pedal during recalibration
        if current_vertical is not None:
            send_command(COMMANDS[current_vertical][1])
            current_vertical = None

        current_steer_dir = None
        current_steer_intensity = 0.0

    print("\n" + "=" * 55)
    print("🎯 CENTER RECALIBRATED! (New neutral: {:.1f}°) [{}]".format(
        pitch_origin if pitch_origin is not None else 0.0, reason))
    print("=" * 55 + "\n")


def steering_thread():
    """Worker thread generating micro-PWM pulses on arrow keys."""
    pressed_dir = None

    def press(direction):
        nonlocal pressed_dir
        if pressed_dir != direction:
            if pressed_dir is not None:
                send_command(COMMANDS[pressed_dir][1])
            send_command(COMMANDS[direction][0])
            pressed_dir = direction

    def release():
        nonlocal pressed_dir
        if pressed_dir is not None:
            send_command(COMMANDS[pressed_dir][1])
            pressed_dir = None

    def interruptible_sleep(duration_sec, target_dir):
        # poll in short steps so direction changes break out immediately
        step = 0.004
        elapsed = 0.0
        while elapsed < duration_sec:
            with lock:
                if current_steer_dir != target_dir or current_steer_intensity <= MIN_DUTY_THRESHOLD:
                    return False
            time.sleep(step)
            elapsed += step
        return True

    while True:
        with lock:
            dir_now = current_steer_dir
            duty    = current_steer_intensity

        # neutral or in deadband: release both
        if dir_now is None or duty <= MIN_DUTY_THRESHOLD:
            release()
            time.sleep(0.008)
            continue

        # full lock: hold key continuously
        if duty >= FULL_LOCK_THRESHOLD:
            press(dir_now)
            time.sleep(0.010)
            continue

        # proportional pulse width modulation
        if duty >= 0.45:
            t_press   = duty * PWM_PERIOD
            t_release = PWM_PERIOD - t_press
        else:
            t_press   = MIN_PRESS_MS
            t_release = max(0.010, (t_press / max(0.03, duty)) - t_press)

        press(dir_now)
        if not interruptible_sleep(t_press, dir_now):
            release()
            continue

        release()
        interruptible_sleep(t_release, dir_now)


def release_watchdog():
    # safety timeout: releases gas/brake if touch up packet is lost
    global current_vertical
    while True:
        time.sleep(0.04)
        with lock:
            if current_vertical is not None:
                if time.time() - last_touch_time > TOUCH_TIMEOUT:
                    send_command(COMMANDS[current_vertical][1])
                    current_vertical = None


def keyboard_listener_thread():
    while True:
        try:
            line = sys.stdin.readline()
            if line:
                trigger_recalibrate("PC terminal command")
        except Exception:
            break


def on_pitch(*values):
    global pitch_origin, smoothed_pitch, current_steer_dir, current_steer_intensity

    if not values:
        return
    value = float(values[0])

    if pitch_origin is None:
        pitch_origin   = value
        smoothed_pitch = value
        print("\n🎮 Initial calibration complete! Neutral center at {:.1f}°.".format(pitch_origin))
        print("💡 Tip: Tap with 2 fingers on screen at any time to recalibrate the center.\n")
        return

    # adaptive filter: quick turns lower smoothing for snappy response
    diff = abs(value - smoothed_pitch)
    adaptive_alpha = min(0.85, max(0.35, 0.35 + (diff / 12.0) * 0.50))
    smoothed_pitch = adaptive_alpha * value + (1.0 - adaptive_alpha) * smoothed_pitch

    delta = normalize_angle(smoothed_pitch - pitch_origin) * STEER_SIGN
    adelta = abs(delta)

    if adelta <= DEAD_ZONE:
        new_dir       = None
        new_intensity = 0.0
    else:
        new_dir = "RIGHT" if delta > 0 else "LEFT"
        norm = min(1.0, (adelta - DEAD_ZONE) / (MAX_STEER_ANGLE - DEAD_ZONE))
        new_intensity = norm ** EXPO_GAMMA

    if DEBUG_STEER:
        bar_len = int(new_intensity * 20)
        bar = ("[" + "=" * bar_len + " " * (20 - bar_len) + "]") if new_dir else "[       CENTER       ]"
        print("delta={:+5.1f}° | dir={:5s} | force={:4.0f}% {}".format(
            delta, new_dir or "OFF", new_intensity * 100, bar))

    with lock:
        current_steer_dir       = new_dir
        current_steer_intensity = new_intensity


def on_pad_x(*values):
    global current_vertical, last_touch_time, last_left_touch, last_right_touch, last_touch_x

    if not values:
        return

    if len(values) >= 2:
        trigger_recalibrate("Multi-touch detected (2 fingers)")
        return

    val = float(values[0])
    now = time.time()

    if val < -0.2:
        last_left_touch = now
    elif val > 0.2:
        last_right_touch = now

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
            current_vertical = new_cmd


def on_multitouch_event(*values):
    trigger_recalibrate("Multi-touch detected")


def main():
    threading.Thread(target=steering_thread, daemon=True).start()
    threading.Thread(target=release_watchdog, daemon=True).start()
    threading.Thread(target=keyboard_listener_thread, daemon=True).start()

    PITCH_ADDRESS = b'/multisense/orientation/pitch'
    PAD_ADDRESS_X = b'/multisense/pad/x'

    osc  = OSCThreadServer()
    sock = osc.listen(address='0.0.0.0', port=8000, default=True)

    osc.bind(PITCH_ADDRESS, on_pitch)
    osc.bind(PAD_ADDRESS_X, on_pad_x)

    osc.bind(b'/multisense/pad/touches', on_multitouch_event)
    osc.bind(b'/multisense/pad/2/x', on_multitouch_event)
    osc.bind(b'/multisense/pad/2/y', on_multitouch_event)
    osc.bind(b'/multisense/multitouch', on_multitouch_event)

    print()
    print("=" * 65)
    print("🏎️  SUPERTUXKART CONTROLLER (MARIO KART WII STYLE) STARTED")
    print("=" * 65)
    print("  OSC Server listening on 0.0.0.0:8000 -> Sending to {}:{}".format(*STK_ADDRESS))
    print()
    print("  DRIVING INSTRUCTIONS:")
    print("    * Turn phone like a steering wheel to steer.")
    print("    * Straights: Stable neutral dead zone of {:.1f}° (no jitter).".format(DEAD_ZONE))
    print("    * Turns: Exponential progressive response (smooth center, sharp edges).")
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
            current_steer_dir       = None
            current_steer_intensity = 0.0
            if current_vertical is not None:
                send_command(COMMANDS[current_vertical][1])
                current_vertical = None
            send_command("R_LEFT")
            send_command("R_RIGHT")
        time.sleep(0.05)
        osc.stop()
        client_socket.close()
        print("\nsteer.py shut down successfully.")


if __name__ == '__main__':
    main()
