#!/usr/bin/env python3
"""
Genera blendshapes falsos para probar classify_gesture.py + gesture_serial.py
sin necesitar cámara ni MediaPipe.

Uso: python test_pipeline.py | python classify_gesture.py | python gesture_serial.py
"""
import json, sys, time

NEUTRAL = {
    "jawOpen": 0.0, "browInnerUp": 0.0,
    "eyeBlinkLeft": 0.0, "eyeBlinkRight": 0.0,
    "mouthSmileLeft": 0.0, "mouthSmileRight": 0.0,
    "browDownLeft": 0.0, "browDownRight": 0.0,
    "mouthPressLeft": 0.0, "mouthPressRight": 0.0,
    "eyeLookUpLeft": 0.0, "eyeLookUpRight": 0.0,
    "eyeLookDownLeft": 0.0, "eyeLookDownRight": 0.0,
}

def send(shapes, n=10, delay=0.1):
    for _ in range(n):
        print(json.dumps({"blendshapes": shapes}), flush=True)
        time.sleep(delay)

print("[test] Cara neutra 3s -> auto-blink deberia disparar a los 5s", file=sys.stderr, flush=True)
send(NEUTRAL, n=30, delay=0.1)

print("[test] Sonrisa fuerte", file=sys.stderr, flush=True)
send({**NEUTRAL, "mouthSmileLeft": 0.6, "mouthSmileRight": 0.6}, n=15, delay=0.1)

print("[test] Parpadeo doble", file=sys.stderr, flush=True)
send({**NEUTRAL, "eyeBlinkLeft": 0.8, "eyeBlinkRight": 0.8}, n=15, delay=0.1)

print("[test] Boca abierta", file=sys.stderr, flush=True)
send({**NEUTRAL, "jawOpen": 0.6}, n=15, delay=0.1)

print("[test] Cejas arriba", file=sys.stderr, flush=True)
send({**NEUTRAL, "browInnerUp": 0.4}, n=15, delay=0.1)

print("[test] FIN", file=sys.stderr, flush=True)
