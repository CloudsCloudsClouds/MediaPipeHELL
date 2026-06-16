import os
import sys
import urllib.request
import numpy as np
import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

MODEL_FILE = os.path.join(os.path.dirname(__file__), "face_landmarker_v2_with_blendshapes.task")
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"


def _ensure_model():
    if os.path.exists(MODEL_FILE):
        return
    print("[robot_face_landmarks] Descargando modelo MediaPipe...", file=sys.stderr, flush=True)
    try:
        urllib.request.urlretrieve(MODEL_URL, MODEL_FILE)
        print("[robot_face_landmarks] Descarga completa.", file=sys.stderr, flush=True)
    except Exception as e:
        print(f"[robot_face_landmarks] ERROR: No se pudo descargar modelo: {e}", file=sys.stderr, flush=True)
        sys.exit(1)


class RobotFaceLandmarker:
    def __init__(self):
        _ensure_model()
        base_options = python.BaseOptions(model_asset_path=MODEL_FILE)
        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.IMAGE,
            output_face_blendshapes=True,
            output_facial_transformation_matrixes=True,
        )
        self._detector = vision.FaceLandmarker.create_from_options(options)

    def detect(self, frame: np.ndarray) -> dict:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self._detector.detect(mp_image)

        output: dict = {}

        if result.face_blendshapes:
            output["blendshapes"] = {
                cat.category_name: float(cat.score)
                for cat in result.face_blendshapes[0]
            }

        if result.face_landmarks:
            output["landmarks"] = [
                [(float(lm.x), float(lm.y), float(lm.z)) for lm in face]
                for face in result.face_landmarks
            ]

        if result.facial_transformation_matrixes:
            m = result.facial_transformation_matrixes[0]
            output["transform"] = {
                "m00": float(m[0, 0]), "m01": float(m[0, 1]), "m02": float(m[0, 2]), "m03": float(m[0, 3]),
                "m10": float(m[1, 0]), "m11": float(m[1, 1]), "m12": float(m[1, 2]), "m13": float(m[1, 3]),
                "m20": float(m[2, 0]), "m21": float(m[2, 1]), "m22": float(m[2, 2]), "m23": float(m[2, 3]),
            }

        return output

    def close(self):
        self._detector.close()
