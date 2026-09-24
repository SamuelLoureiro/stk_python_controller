#!/usr/bin/env python3
"""
STK_input_server_v2.py

Central modular input hub for SuperTuxKart.
Receives UDP commands (port 6006) from multiple interfaces (phone, Arduino,
voice recognition, camera gestures, etc.).

ARCHITECTURE:
  - STEERING: Controlled exclusively by virtual wheel (ABS_X of Xbox 360 Controller)
    via evdev/uinput for smooth, continuous analog steering.
  - ALL OTHER ACTIONS: Controlled exclusively via keyboard emulation (pynput).
    The virtual controller never triggers buttons, ensuring zero conflicts.
"""

import sys
import socket
import time
from pynput.keyboard import Key, Controller

###############################################################################
## Console Colors
###############################################################################
GREEN  = '\033[92m'
WHITE  = '\x1b[0m'
BLUE   = '\033[94m'
YELLOW = '\033[93m'
RED    = '\033[91m'

stop  = False
DEBUG = False

for arg in sys.argv[1:]:
    if arg in ('-d', '--debug'):
        DEBUG = True
    elif arg in ('-h', '--help'):
        print("Usage: python STK_input_server_v2.py [-d]")
        print("  -d, --debug   Display telemetry and received commands")
        sys.exit(0)

###############################################################################
## UDP Server
###############################################################################
ADDRESS = ('0.0.0.0', 6006)
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
try:
    sock.bind(ADDRESS)
except OSError as e:
    print(f"{RED}Error opening UDP port 6006: {e}{WHITE}")
    print("Check if another server instance is already running.")
    sys.exit(1)

###############################################################################
## Virtual Keyboard (pynput) - Handles 100% of actions except steering
###############################################################################
keyboard = Controller()

def game_tap(key):
    """Holds key for 50ms to ensure registration in the STK game loop."""
    keyboard.press(key)
    time.sleep(0.05)
    keyboard.release(key)

# Official keyboard command table (used by Arduino, Phone, etc.)
bindings = [
    ['UP',           Key.up,        game_tap],
    ['DOWN',         Key.down,      game_tap],
    ['LEFT',         Key.left,      game_tap],
    ['RIGHT',        Key.right,     game_tap],
    ['SELECT',       Key.enter,     game_tap],
    ['CANCEL',       Key.backspace, game_tap],
    ['BACK',         Key.backspace, game_tap],
    ['FIRE',         Key.space,     game_tap],
    ['NITRO',        'n',           game_tap],
    ['P_SKIDDING',   'v',           keyboard.press],
    ['R_SKIDDING',   'v',           keyboard.release],
    ['P_LOOKBACK',   'b',           keyboard.press],
    ['R_LOOKBACK',   'b',           keyboard.release],
    ['RESCUE',       Key.backspace, game_tap],
    ['PAUSE',        Key.esc,       game_tap],
    ['P_UP',         Key.up,        keyboard.press],
    ['R_UP',         Key.up,        keyboard.release],
    ['P_DOWN',       Key.down,      keyboard.press],
    ['R_DOWN',       Key.down,      keyboard.release],
    ['P_LEFT',       Key.left,      keyboard.press],
    ['R_LEFT',       Key.left,      keyboard.release],
    ['P_RIGHT',      Key.right,     keyboard.press],
    ['R_RIGHT',      Key.right,     keyboard.release],
    ['P_ACCELERATE', Key.up,        keyboard.press],
    ['R_ACCELERATE', Key.up,        keyboard.release],
    ['P_BRAKE',      Key.down,      keyboard.press],
    ['R_BRAKE',      Key.down,      keyboard.release],
]

commands = [b[0] for b in bindings]

###############################################################################
## Virtual Gamepad (evdev/uinput) - Recognized by SDL2/STK as Xbox 360
###############################################################################
gamepad = None

try:
    from evdev import UInput, AbsInfo, ecodes

    # Declare standard Xbox 360 layout so SDL2 / SuperTuxKart recognizes
    # the device natively. The script will only manipulate the ABS_X axis (wheel).
    capabilities = {
        ecodes.EV_ABS: [
            (ecodes.ABS_X, AbsInfo(value=0, min=-32767, max=32767, fuzz=16, flat=128, resolution=0)),
            (ecodes.ABS_Y, AbsInfo(value=0, min=-32767, max=32767, fuzz=16, flat=128, resolution=0)),
            (ecodes.ABS_Z, AbsInfo(value=0, min=0, max=255, fuzz=0, flat=0, resolution=0)),
            (ecodes.ABS_RZ, AbsInfo(value=0, min=0, max=255, fuzz=0, flat=0, resolution=0)),
            (ecodes.ABS_HAT0X, AbsInfo(value=0, min=-1, max=1, fuzz=0, flat=0, resolution=0)),
            (ecodes.ABS_HAT0Y, AbsInfo(value=0, min=-1, max=1, fuzz=0, flat=0, resolution=0)),
        ],
        ecodes.EV_KEY: [
            ecodes.BTN_A,
            ecodes.BTN_B,
            ecodes.BTN_X,
            ecodes.BTN_Y,
            ecodes.BTN_TL,
            ecodes.BTN_TR,
            ecodes.BTN_SELECT,
            ecodes.BTN_START,
        ],
    }

    gamepad = UInput(capabilities, name="Xbox 360 Controller", vendor=0x045e, product=0x028e)

except Exception as e:
    print(f"\n{RED}❌ ERROR CREATING VIRTUAL CONTROLLER /dev/uinput: {e}{WHITE}")
    print("To grant permissions, run: sudo chmod 666 /dev/uinput\n")
    sys.exit(1)

def set_steer(float_val):
    """Applies continuous analog value (-1.0 to 1.0) to wheel axis ABS_X."""
    if gamepad:
        clamped = max(-1.0, min(1.0, float_val))
        axis_val = int(clamped * 32767)
        gamepad.write(ecodes.EV_ABS, ecodes.ABS_X, axis_val)
        gamepad.syn()

###############################################################################
## Main Loop
###############################################################################
print()
print("=" * 65)
print("🎮 STK INPUT SERVER (MODULAR)")
print("=" * 65)
print("  * Device: Xbox 360 Controller (Native SDL2 / STK)")
print("  * Steering: Analog Axis ABS_X (Wheel)")
print("  * Acceleration, Brake/Reverse, Drift, Items: 100% Keyboard (pynput)")
print("  * Listening UDP on 0.0.0.0:6006")
if DEBUG:
    print(f"  * Debug: {GREEN}ENABLED{WHITE}")
print("=" * 65)
print()

try:
    while not stop:
        data, addr = sock.recvfrom(1024)
        if isinstance(data, bytes):
            data = data.decode("utf-8").strip().replace(',', '')

        if data == 'STOPSERVEUR':
            stop = True
            break

        # 1. Continuous analog steering command (exclusive to wheel ABS_X)
        if data.startswith("STEER:"):
            try:
                val = float(data.split(":")[1])
                set_steer(val)
                if DEBUG:
                    print(f"{YELLOW}\t{data}{WHITE}")
            except ValueError:
                if DEBUG:
                    print(f"{RED}\t{data} (Invalid STEER value){WHITE}")
            continue

        # 2. All other commands are sent strictly to keyboard
        if data in commands:
            if DEBUG:
                print(f"{YELLOW}\t{data}{WHITE}")
            b = bindings[commands.index(data)]
            b[2](b[1])
        else:
            if DEBUG:
                print(f"{RED}\t{data} (Unknown){WHITE}")

except KeyboardInterrupt:
    print("\nShutting down server...")

finally:
    if gamepad:
        try:
            set_steer(0.0)
            gamepad.close()
        except Exception:
            pass
    sock.close()
    print("STK input server stopped.")