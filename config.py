"""
Configuration settings for the controller pipeline.
Key bindings must match the controls set in SuperTuxKart options.
"""

from pynput.keyboard import Key

# UDP port where STK_input_server_v2 is listening
STK_SERVER_ADDRESS = ('localhost', 6006)

# Default keyboard mapping for legacy/standalone mode
KEY_MAP = {
    "accelerate": Key.up,
    "brake": Key.down,
    "left": Key.left,
    "right": Key.right,
    "fire": Key.space,
    "turbo": "n",
    "drift": "v",
    "rescue": Key.backspace,
    "look_back": "b",
}

# Pre-trained models (kept out of git due to size)
FACE_MODEL_PATH = "models/face_landmarker.task"
VOSK_MODEL_PATH = "models/vosk-model-small-en-us-0.15"

# Camera input
CAMERA_INDEX = 0
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
DEBUG_WINDOW = True  # set False during races to save CPU/GPU cycles

# Legacy blendshape thresholds (for main.py direct keyboard mode)
SMILE_ENGAGE = 0.50
SMILE_RELEASE = 0.35

WINK_LEFT_ENGAGE = 0.40
WINK_LEFT_RELEASE_OTHER_EYE = 0.30

WINK_RIGHT_ENGAGE = 0.25
WINK_RIGHT_RELEASE_OTHER_EYE = 0.30

JAW_OPEN_THRESHOLD = 0.60
JAW_OPEN_COOLDOWN_S = 0.6

# Face module thresholds (using engage/release hysteresis to prevent jitter)
EYEBROW_ENGAGE = 0.45   # look back
EYEBROW_RELEASE = 0.30

DRIFT_ROLL_ENGAGE = 18.0   # head tilt (degrees) to trigger drift
DRIFT_ROLL_RELEASE = 10.0

# Head nod detection (quick dip down then back up)
LOOK_BACK_YAW_THRESHOLD_DEG = 35.0
NOD_PITCH_DIP_DEG = 15.0
NOD_MAX_DURATION_S = 0.8
RESCUE_COOLDOWN_S = 1.5

# Voice settings (restricted grammar keeps Vosk recognition fast)
VOICE_SAMPLE_RATE = 16000

VOICE_ACTION_MAP = {
    "turbo": "NITRO",
    "fire": "FIRE",
}

VOICE_COOLDOWN_S = 1.0

# Tap duration for impulse actions so the game loop catches the keypress
PULSE_HOLD_S = 0.15
