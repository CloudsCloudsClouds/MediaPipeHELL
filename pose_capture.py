import os
import sys
import urllib.request
import time
import json
import math
import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# === Pointing / State Machine Configuration ===
POINT_THRESHOLD = 0.05     # min tip-to-knuckle distance (normalized) to count as pointing
POINT_GAIN = 500            # hand vector -> degrees multiplier for neck yaw/pitch
EYE_GAIN = 50              # hand vector -> eye offset multiplier
HOLD_DURATION = 2.0        # seconds to hold direction after hand drops

# As always, there are more shapes to be selected. Loos at set_directions.
TRACKED_SHAPES = ["jawOpen", "browInnerUp", "eyeBlinkLeft", "eyeBlinkRight", "mouthSmileLeft", "mouthSmileRight"]

# --- Model paths ---
FACE_MODEL = "face_landmarker_v2_with_blendshapes.task"
HAND_MODEL = "hand_landmarker.task"

FACE_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
HAND_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"

if not os.path.exists(FACE_MODEL):
    print("Downloading face model...", file=sys.stderr)
    try:
        urllib.request.urlretrieve(FACE_URL, FACE_MODEL)
        print("Download complete.", file=sys.stderr)
    except Exception as e:
        print(f"Failed to download face model: {e}", file=sys.stderr)
        exit(1)

if not os.path.exists(HAND_MODEL):
    print("Downloading hand model...", file=sys.stderr)
    try:
        urllib.request.urlretrieve(HAND_URL, HAND_MODEL)
        print("Download complete.", file=sys.stderr)
    except Exception as e:
        print(f"Failed to download hand model: {e}", file=sys.stderr)
        exit(1)

# --- Async result globals ---
face_latest = None
hand_latest = None

def face_callback(result: vision.FaceLandmarkerResult, output_image: mp.Image, timestamp_ms: int):
    global face_latest
    face_latest = result

# Pain. Horror. Its so so much better to have it all async now.
def hand_callback(result: vision.HandLandmarkerResult, output_image: mp.Image, timestamp_ms: int):
    global hand_latest
    hand_latest = result

# --- Face detector ---
face_base = python.BaseOptions(model_asset_path=FACE_MODEL)
face_opts = vision.FaceLandmarkerOptions(
    base_options=face_base,
    running_mode=vision.RunningMode.LIVE_STREAM,
    output_face_blendshapes=True,
    output_facial_transformation_matrixes=True,
    result_callback=face_callback,
)
face_detector = vision.FaceLandmarker.create_from_options(face_opts)

# --- Hand detector ---
# It appears that it's the same as gesture. It isn't.
# It only detects one hand, configurable.
hand_base = python.BaseOptions(model_asset_path=HAND_MODEL)
hand_opts = vision.HandLandmarkerOptions(
    base_options=hand_base,
    running_mode=vision.RunningMode.LIVE_STREAM,
    num_hands=1,
    min_hand_detection_confidence=0.5,
    min_tracking_confidence=0.5,
    result_callback=hand_callback,
)
hand_detector = vision.HandLandmarker.create_from_options(hand_opts)

# --- State machine ---
state = "mirror"   # "mirror" | "pointing" | "hold"
hold_until = 0.0
held_yaw = 0.0
held_pitch = 0.0
held_eye_x = 0.0
held_eye_y = 0.0

def compute_yaw(matrix):
    return math.degrees(math.atan2(-matrix[2, 0], math.sqrt(matrix[0, 0]**2 + matrix[1, 0]**2)))

# Pitch is computed but needs up/down neck hardware to be useful.
def compute_pitch(matrix):
    return math.degrees(math.atan2(matrix[2, 1], matrix[2, 2]))

cap = cv2.VideoCapture(0)

while cap.isOpened():
    success, frame = cap.read()
    if not success:
        break

    frame = cv2.flip(frame, 1)
    timestamp = int(time.time() * 1000)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

    face_detector.detect_async(mp_img, timestamp)
    hand_detector.detect_async(mp_img, timestamp)

    # --- Face overlay ---
    if face_latest and face_latest.face_landmarks:
        for flm in face_latest.face_landmarks:
            for lm in flm:
                x = int(lm.x * frame.shape[1])
                y = int(lm.y * frame.shape[0])
                cv2.circle(frame, (x, y), 1, (0, 255, 0), -1)

        y_off = 30
        if face_latest.face_blendshapes:
            bd = {c.category_name: c.score for c in face_latest.face_blendshapes[0]}
            for shape in TRACKED_SHAPES:
                cv2.putText(frame, f"{shape}: {bd.get(shape, 0):.2f}",
                            (10, y_off), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                y_off += 20

    # --- Hand overlay ---
    hand_visible = hand_latest and hand_latest.hand_landmarks
    if hand_visible:
        for hlm in hand_latest.hand_landmarks:
            # draw wrist (0), index knuckle (5), index tip (8)
            for idx in (0, 5, 8):
                lm = hlm[idx]
                x = int(lm.x * frame.shape[1])
                y = int(lm.y * frame.shape[0])
                color = (255, 0, 255) if idx == 8 else (0, 255, 255)
                cv2.circle(frame, (x, y), 6, color, -1)

            # line from knuckle to tip
            x5 = int(hlm[5].x * frame.shape[1])
            y5 = int(hlm[5].y * frame.shape[0])
            x8 = int(hlm[8].x * frame.shape[1])
            y8 = int(hlm[8].y * frame.shape[0])
            cv2.arrowedLine(frame, (x5, y5), (x8, y8), (0, 0, 255), 2)

    # --- Pointing state machine ---
    is_pointing = False
    dx = dy = 0.0
    if hand_visible:
        lm = hand_latest.hand_landmarks[0]
        dx = lm[8].x - lm[5].x
        dy = lm[8].y - lm[5].y
        is_pointing = math.sqrt(dx*dx + dy*dy) > POINT_THRESHOLD

    if state == "mirror":
        if is_pointing:
            state = "pointing"

    elif state == "pointing":
        if is_pointing:
            held_yaw = dx * POINT_GAIN
            held_pitch = -dy * POINT_GAIN   # negated: image y points down
            held_eye_x = dx * EYE_GAIN
            held_eye_y = -dy * EYE_GAIN
        else:
            state = "hold"
            hold_until = time.time() + HOLD_DURATION

    elif state == "hold":
        if is_pointing:
            state = "pointing"
            held_yaw = dx * POINT_GAIN
            held_pitch = -dy * POINT_GAIN
            held_eye_x = dx * EYE_GAIN
            held_eye_y = -dy * EYE_GAIN
        elif time.time() >= hold_until:
            state = "mirror"

    cv2.putText(frame, f"State: {state}", (10, frame.shape[0] - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    # --- Build JSON output ---
    output = {}

    if face_latest:
        if face_latest.face_blendshapes:
            bd = {c.category_name: float(c.score) for c in face_latest.face_blendshapes[0]}
            output["blendshapes"] = bd

        # Matrix.
        # Its just to calculate the yaw from the matrix, not used for anything else.
        # The yaw is the current Y rotation of the face.
        # Anyways, calculus done in set_direction
        if face_latest.facial_transformation_matrixes:
            m = face_latest.facial_transformation_matrixes[0]
            output["transform"] = {
                "m00": float(m[0, 0]), "m01": float(m[0, 1]), "m02": float(m[0, 2]), "m03": float(m[0, 3]),
                "m10": float(m[1, 0]), "m11": float(m[1, 1]), "m12": float(m[1, 2]), "m13": float(m[1, 3]),
                "m20": float(m[2, 0]), "m21": float(m[2, 1]), "m22": float(m[2, 2]), "m23": float(m[2, 3]),
            }

    output["state"] = state

    if state == "mirror":
        if face_latest and face_latest.facial_transformation_matrixes:
            m = face_latest.facial_transformation_matrixes[0]
            output["yaw"] = compute_yaw(m)
            # output["pitch"] = compute_pitch(m)  # needs up/down neck hardware
        else:
            output["yaw"] = 0.0
    else:
        output["yaw"] = held_yaw
        output["pitch"] = held_pitch
        output["eye_x"] = held_eye_x
        output["eye_y"] = held_eye_y

    if output:
        print(json.dumps(output), flush=True)

    cv2.imshow("Pose Capture", frame)
    if cv2.waitKey(1) & 0xFF == 27:
        break

face_detector.close()
hand_detector.close()
cap.release()
cv2.destroyAllWindows()
