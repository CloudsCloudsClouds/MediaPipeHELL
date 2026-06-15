import os
import urllib.request
import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

mod_path = "face_detector.tflite"
url = "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite"
if not os.path.exists(mod_path):
    print(f"Downloading model...")
    try:
        urllib.request.urlretrieve(url, mod_path)
        print("Download complete.")
    except Exception as e:
        print(f"Failed to download model: {e}")
        exit(1)

base_options = python.BaseOptions(model_asset_path=mod_path)
options = vision.FaceDetectorOptions(base_options=base_options)
detector = vision.FaceDetector.create_from_options(options)


cap = cv2.VideoCapture(0)

while cap.isOpened():
    success, frame = cap.read()
    if not success:
        break

    image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=image_rgb)

    # Detect here
    detection_result = detector.detect(mp_img)

    # Visualization
    if detection_result.detections:
        for detections in detection_result.detections:
            bbox = detections.bounding_box
            start_point = int(bbox.origin_x), int(bbox.origin_y)
            end_point = int(bbox.origin_x + bbox.width), int(bbox.origin_y + bbox.height)
            cv2.rectangle(frame, start_point, end_point, (0, 255, 0), 2)

    cv2.imshow("Mediapipe Face detector", cv2.flip(frame, 1))

    # Quit with esc
    if cv2.waitKey(5) & 0xFF == 27:
            break

cap.release()
cv2.destroyAllWindows()
