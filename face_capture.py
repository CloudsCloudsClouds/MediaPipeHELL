import os
import sys
import io
import urllib.request
import time
import json
import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# Forzar flush por línea en stdout para que el pipe reciba datos de inmediato
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, line_buffering=True)

TRACKED_SHAPES = ["jawOpen", "browInnerUp", "eyeBlinkLeft", "eyeBlinkRight", "mouthSmileLeft", "mouthSmileRight"]

mod_path = "face_landmarker_v2_with_blendshapes.task"
url = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
if not os.path.exists(mod_path):
    print("Downloading model...", file=sys.stderr)
    try:
        urllib.request.urlretrieve(url, mod_path)
        print("Download complete.", file=sys.stderr)
    except Exception as e:
        print(f"Failed to download model: {e}", file=sys.stderr)
        exit(1)

latest_result = None

def result_callback(result: vision.FaceLandmarkerResult, output_image: mp.Image, timestamp_ms: int):
    global latest_result
    latest_result = result

base_options = python.BaseOptions(model_asset_path=mod_path)
options = vision.FaceLandmarkerOptions(
    base_options=base_options,
    running_mode=vision.RunningMode.LIVE_STREAM,
    output_face_blendshapes=True,
    output_facial_transformation_matrixes=True,
    result_callback=result_callback
)

detector = vision.FaceLandmarker.create_from_options(options)
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("[face_capture] ERROR: no se pudo abrir la cámara", file=sys.stderr, flush=True)
    sys.exit(1)

print("[face_capture] Cámara abierta, esperando cara...", file=sys.stderr, flush=True)
frames_sent = 0

while cap.isOpened():
    success, frame = cap.read()
    if not success:
        break

    frame = cv2.flip(frame, 1)
    timestamp = int(time.time() * 1000)
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
    detector.detect_async(mp_image, timestamp)

    if latest_result and latest_result.face_landmarks:
        for face_landmarks in latest_result.face_landmarks:
            for landmark in face_landmarks:
                x = int(landmark.x * frame.shape[1])
                y = int(landmark.y * frame.shape[0])
                cv2.circle(frame, (x, y), 1, (0, 255, 0), -1)

        y_offset = 30
        if latest_result.face_blendshapes:
            blendshape_dict = {cat.category_name: cat.score for cat in latest_result.face_blendshapes[0]}
            for shape in TRACKED_SHAPES:
                score = blendshape_dict.get(shape, 0)
                cv2.putText(frame, f"{shape}: {score:.2f}", (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                y_offset += 20

    output = {}
    if latest_result:
        if latest_result.face_blendshapes:
            blendshape_dict = {cat.category_name: float(cat.score) for cat in latest_result.face_blendshapes[0]}
            output["blendshapes"] = blendshape_dict

        if latest_result.facial_transformation_matrixes:
            matrix = latest_result.facial_transformation_matrixes[0]
            output["transform"] = {
                "m00": float(matrix[0, 0]), "m01": float(matrix[0, 1]), "m02": float(matrix[0, 2]), "m03": float(matrix[0, 3]),
                "m10": float(matrix[1, 0]), "m11": float(matrix[1, 1]), "m12": float(matrix[1, 2]), "m13": float(matrix[1, 3]),
                "m20": float(matrix[2, 0]), "m21": float(matrix[2, 1]), "m22": float(matrix[2, 2]), "m23": float(matrix[2, 3]),
            }

    if output:
        print(json.dumps(output), flush=True)
        frames_sent += 1
        if frames_sent == 1:
            print("[face_capture] Primera detección enviada", file=sys.stderr, flush=True)
        elif frames_sent % 150 == 0:
            print(f"[face_capture] {frames_sent} frames enviados", file=sys.stderr, flush=True)

    cv2.imshow("Cabezon", frame)
    if cv2.waitKey(1) & 0xFF == 27:
        break

detector.close()
cap.release()
cv2.destroyAllWindows()
