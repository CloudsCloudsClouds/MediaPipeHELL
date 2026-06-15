import os
import urllib.request
import time
import cv2
import serial
import math
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

TRACKED_SHAPES = ["jawOpen", "browInnerUp", "eyeBlinkLeft", "eyeBlinkRight", "mouthSmileLeft", "mouthSmileRight"]

ser = serial.Serial('/dev/ttyUSB0', 115200, timeout = 0.1)
last_send_time = 1
send_interval = 0.2 # 10 Hz

# 1. Update the send function to accept yaw
def send_to_serial(jaw, ex, ey, bl, br, yaw):
    # Format: $JAW,EX,EY,BL,BR,YAW#
    packet = f"${jaw:.2f},{ex:.2f},{ey:.2f},{bl:.2f},{br:.2f},{yaw:.2f}#"
    ser.write(packet.encode('utf-8'))

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

# 2. Configure Options to include the transformation matrix
base_options = python.BaseOptions(model_asset_path=mod_path)
options = vision.FaceLandmarkerOptions(
    base_options=base_options,
    running_mode=vision.RunningMode.LIVE_STREAM,
    output_face_blendshapes=True,
    output_facial_transformation_matrixes=True, # Added this flag
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

    # Use the global latest_result for visualization
    if latest_result and latest_result.face_landmarks:
        for face_landmarks in latest_result.face_landmarks:
            for landmark in face_landmarks:
                x = int(landmark.x * frame.shape[1])
                y = int(landmark.y * frame.shape[0])
                cv2.circle(frame, (x, y), 1, (0, 255, 0), -1)

        y_offset = 30

        # 3. Extract Yaw for screen visualization
        if latest_result.facial_transformation_matrixes:
            matrix = latest_result.facial_transformation_matrixes[0]
            # Calculate Yaw (Y-axis rotation) from the rotation matrix
            yaw_rad = math.atan2(-matrix[2, 0], math.sqrt(matrix[0, 0]**2 + matrix[1, 0]**2))
            yaw_deg = math.degrees(yaw_rad)

            cv2.putText(frame, f"Yaw: {yaw_deg:.2f} deg", (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
            y_offset += 20

        # Accessing Blendshapes (The "Gesture" part)
        if latest_result.face_blendshapes:
            blendshape_dict = {category.category_name: category.score for category in latest_result.face_blendshapes[0]}

            # And display
            for shape in TRACKED_SHAPES:
                score = blendshape_dict.get(shape, 0)
                test = f"{shape}: {score:.2f}"

                cv2.putText(frame, test, (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                y_offset += 20

    # 4. Send Logic
    current_time = time.time()
    if current_time - last_send_time > send_interval:
        if latest_result and latest_result.face_blendshapes:
            blendshape_dict = {category.category_name: category.score for category in latest_result.face_blendshapes[0]}

            jaw = blendshape_dict.get("jawOpen", 0)
            blink_l = blendshape_dict.get("eyeBlinkLeft", 0)
            blink_r = blendshape_dict.get("eyeBlinkRight", 0)
            smile_l = blendshape_dict.get("mouthSmileLeft", 0)
            smile_r = blendshape_dict.get("mouthSmileRight", 0)

            # Default yaw to 0 if the matrix fails to generate for a frame
            yaw = 0.0
            if latest_result.facial_transformation_matrixes:
                matrix = latest_result.facial_transformation_matrixes[0]
                yaw_rad = math.atan2(-matrix[2, 0], math.sqrt(matrix[0, 0]**2 + matrix[1, 0]**2))
                yaw = math.degrees(yaw_rad)

            # Pass the new yaw variable
            send_to_serial(jaw, blink_l, blink_r, smile_l, smile_r, yaw)

            last_send_time = current_time

    cv2.imshow("Cabezon", frame)
    if cv2.waitKey(1) & 0xFF == 27: break

detector.close()
cap.release()
cv2.destroyAllWindows()
