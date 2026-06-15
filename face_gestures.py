import os
import urllib.request
import time
import cv2
import time
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

TRACKED_SHAPES = ["jawOpen", "browInnerUp", "eyeBlinkLeft", "eyeBlinkRight", "mouthSmileLeft", "mouthSmileRight"]

mod_path = "face_landmarker_v2_with_blendshapes.task"
url = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
if not os.path.exists(mod_path):
    print("Downloading model...")
    try:
        urllib.request.urlretrieve(url, mod_path)
        print("Download complete.")
    except Exception as e:
        print(f"Failed to download model: {e}")
        exit(1)

# Global variable to store latest results
latest_result = None

def result_callback(result: vision.FaceLandmarkerResult, output_image: mp.Image, timestamp_ms: int):
    global latest_result
    latest_result = result

# Configure Options
base_options = python.BaseOptions(model_asset_path=mod_path)
options = vision.FaceLandmarkerOptions(
    base_options=base_options,
    running_mode=vision.RunningMode.LIVE_STREAM,
    output_face_blendshapes=True,
    result_callback=result_callback
)

# Main Loop
detector = vision.FaceLandmarker.create_from_options(options)
cap = cv2.VideoCapture(0)

while cap.isOpened():
    success, frame = cap.read()
    if not success: break

    frame = cv2.flip(frame, 1)

    timestamp = int(time.time() * 1000)

    # Convert to MediaPipe Image
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

    # Trigger asynchronous detection
    detector.detect_async(mp_image, timestamp)
    # I hate async

    # Use the global latest_result for visualization
    if latest_result and latest_result.face_landmarks:
        for face_landmarks in latest_result.face_landmarks:
            for landmark in face_landmarks:
                x = int(landmark.x * frame.shape[1])
                y = int(landmark.y * frame.shape[0])
                cv2.circle(frame, (x, y), 1, (0, 255, 0), -1)

        # Accessing Blendshapes (The "Gesture" part)
        if latest_result.face_blendshapes:
            blendshape_dict = {category.category_name: category.score for category in latest_result.face_blendshapes[0]}

            # And display
            y_offset = 30
            for shape in TRACKED_SHAPES:
                score = blendshape_dict.get(shape, 0)
                test = f"{shape}: {score:.2f}"

                cv2.putText(frame, test, (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                y_offset += 20

    cv2.imshow("Cabezon", frame)
    if cv2.waitKey(1) & 0xFF == 27: break

detector.close()
cap.release()
cv2.destroyAllWindows()
