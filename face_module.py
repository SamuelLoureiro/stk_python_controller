"""
Tracks facial landmarks and head pose using MediaPipe.
Detects eyebrow raise (look back), head tilt (drift), and head nod (rescue).
"""

import math
import threading
import time

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

import config


def _blendshape_dict(result) -> dict:
    if not result.face_blendshapes:
        return {}
    return {c.category_name: c.score for c in result.face_blendshapes[0]}


def _decompose_head_pose(matrix) -> tuple[float, float, float]:
    """Decomposes the 4x4 face transformation matrix into pitch, yaw, roll (degrees)."""
    r = np.array(matrix).reshape(4, 4)[:3, :3]
    angles, _, _, _, _, _ = cv2.RQDecomp3x3(r)
    pitch = float(angles[0])
    yaw   = float(angles[1])
    roll  = float(angles[2])
    return pitch, yaw, roll


class _NodDetector:
    """Detects a quick downward nod (pitch dip) returning within max_duration_s."""

    def __init__(self, dip_threshold_deg: float, max_duration_s: float):
        self.dip_threshold_deg = dip_threshold_deg
        self.max_duration_s = max_duration_s
        self._dip_start = None

    def reset(self):
        self._dip_start = None

    def update(self, pitch_deg: float) -> bool:
        now = time.monotonic()
        if pitch_deg < -self.dip_threshold_deg:
            if self._dip_start is None:
                self._dip_start = now
        else:
            if self._dip_start is not None:
                duration = now - self._dip_start
                self._dip_start = None
                if duration <= self.max_duration_s:
                    return True
        return False


class FaceWorker(threading.Thread):
    def __init__(self, send_fn):
        super().__init__(daemon=True)
        self._send_fn = send_fn
        self._stop_event = threading.Event()
        self._lookback_active = False
        self._drift_active = False
        self._last_rescue_time = 0.0

    def stop(self):
        self._stop_event.set()

    def run(self):
        base_options = mp_python.BaseOptions(model_asset_path=config.FACE_MODEL_PATH)
        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            output_face_blendshapes=True,
            output_facial_transformation_matrixes=True,
            running_mode=vision.RunningMode.VIDEO,
            num_faces=1,
        )
        landmarker = vision.FaceLandmarker.create_from_options(options)

        cap = cv2.VideoCapture(config.CAMERA_INDEX)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)

        nod_detector = _NodDetector(config.NOD_PITCH_DIP_DEG, config.NOD_MAX_DURATION_S)
        start_time = time.monotonic()

        try:
            while not self._stop_event.is_set():
                ok, frame = cap.read()
                if not ok:
                    continue

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                timestamp_ms = int((time.monotonic() - start_time) * 1000)
                result = landmarker.detect_for_video(mp_image, timestamp_ms)

                shapes = _blendshape_dict(result)
                if shapes:
                    self._process_look_back_eyebrows(shapes)

                pitch, roll = 0.0, 0.0
                if result.facial_transformation_matrixes:
                    pitch, _, roll = _decompose_head_pose(result.facial_transformation_matrixes[0])
                    self._process_head_pose(pitch, roll, nod_detector)

                if config.DEBUG_WINDOW:
                    self._draw_debug(frame, shapes, pitch, roll)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break
        finally:
            # make sure held keys are released when stopping camera thread
            if self._lookback_active:
                self._send_fn("R_LOOKBACK")
                self._lookback_active = False
            if self._drift_active:
                self._send_fn("R_SKIDDING")
                self._drift_active = False
            cap.release()
            if config.DEBUG_WINDOW:
                cv2.destroyAllWindows()

    def _process_look_back_eyebrows(self, shapes: dict):
        outer = (shapes.get("browOuterUpLeft", 0.0) + shapes.get("browOuterUpRight", 0.0)) / 2.0
        inner = shapes.get("browInnerUp", 0.0)
        brow = max(outer, inner)

        if brow > config.EYEBROW_ENGAGE and not self._lookback_active:
            self._send_fn("P_LOOKBACK")
            self._lookback_active = True
            print(f"[face] Look Back ACTIVATED (eyebrows: {brow:.2f})")
        elif brow < config.EYEBROW_RELEASE and self._lookback_active:
            self._send_fn("R_LOOKBACK")
            self._lookback_active = False
            print("[face] Look Back DEACTIVATED")

    def _process_head_pose(self, pitch: float, roll: float, nod_detector: _NodDetector):
        abs_roll = abs(roll)

        # lateral tilt triggers drift
        if abs_roll > config.DRIFT_ROLL_ENGAGE and not self._drift_active:
            self._send_fn("P_SKIDDING")
            self._drift_active = True
            side = "right" if roll > 0 else "left"
            print(f"[face] Drift ACTIVATED ({side} tilt: {abs_roll:.1f}°)")
        elif abs_roll < config.DRIFT_ROLL_RELEASE and self._drift_active:
            self._send_fn("R_SKIDDING")
            self._drift_active = False
            print("[face] Drift DEACTIVATED")

        # safety lockout: don't allow rescue nods while drifting
        if self._drift_active:
            nod_detector.reset()
        else:
            if nod_detector.update(pitch):
                now = time.monotonic()
                if now - self._last_rescue_time >= config.RESCUE_COOLDOWN_S:
                    self._last_rescue_time = now
                    self._send_fn("RESCUE")
                    print(f"[face] RESCUE sent (vertical head nod: {pitch:.1f}°)")

    def _draw_debug(self, frame, shapes: dict, pitch: float, roll: float):
        outer = (shapes.get("browOuterUpLeft", 0.0) + shapes.get("browOuterUpRight", 0.0)) / 2.0
        inner = shapes.get("browInnerUp", 0.0)
        brow = max(outer, inner)

        lb_text = "LOOK_BACK: ON" if self._lookback_active else "LOOK_BACK: off"
        lb_color = (0, 0, 255) if self._lookback_active else (0, 255, 0)

        drift_text = "DRIFT: ON" if self._drift_active else "DRIFT: off"
        drift_color = (0, 0, 255) if self._drift_active else (0, 255, 0)

        cv2.putText(frame, f"Eyebrows:       {brow:.2f} | {lb_text}", (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.52, lb_color, 2)
        cv2.putText(frame, f"Tilt (Roll Z):  {roll:+5.1f}* | {drift_text}", (10, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.52, drift_color, 2)
        cv2.putText(frame, f"Vertical (X):   {pitch:+5.1f}* | Downward NOD = Rescue", (10, 75),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255, 255, 0), 2)
        cv2.imshow("Face Module (q to exit)", frame)
