#!/usr/bin/env python3
"""
classify_gesture.py — reads blendshape JSON from stdin, classifies facial
expressions into Arduino gesture commands, outputs gesture JSON to stdout.

Pipeline: face_capture.py | classify_gesture.py | gesture_serial.py
"""

import sys
import json
import time
import io

# readline() por línea evita el chunk-read de 8 KB del iterador de TextIOWrapper
sys.stdin = io.TextIOWrapper(sys.stdin.buffer, line_buffering=True)

# ===================== CONFIGURATION =====================

# Thresholds ajustados para webcam real (antes estaban al doble y nunca disparaban)
BLINK_THRESHOLD       = 0.35   # era 0.7
BROW_UP_THRESHOLD     = 0.22   # era 0.5
SMILE_THRESHOLD       = 0.18   # era 0.35
JAW_OPEN_THRESHOLD    = 0.25   # era 0.5
BROW_DOWN_THRESHOLD   = 0.18   # era 0.4
MOUTH_PRESS_THRESHOLD = 0.12   # era 0.3
EYE_LOOK_THRESHOLD    = 0.28   # era 0.5
TALK_JAW_THRESHOLD    = 0.12   # era 0.3
TALK_OSCILLATIONS     = 2      # era 3
TALK_RESET_JAW        = 0.08   # era 0.15
TALK_RESET_SECONDS    = 0.6    # era 1.0

# Cooldowns por gesto en segundos
GESTURE_COOLDOWN = {
    1: 0.4,  2: 0.4,  3: 0.7,
    4: 1.0,  5: 1.0,
    6: 1.0,  7: 1.0,
    8: 1.5,  9: 1.5, 10: 1.5,
    13: 0.8, 14: 0.4,
}

# Auto-blink si no hay gesto activo
AUTO_BLINK_ENABLED  = True
AUTO_BLINK_INTERVAL = 5.0

# Prioridad de gestos (mayor prioridad primero)
GESTURE_PRIORITY = [
    (3,  "parpadeo_doble"),
    (10, "sonrisa"),
    (8,  "enojo"),
    (9,  "sorpresa"),
    (14, "hablar"),
    (13, "abrir_mandibula"),
    (1,  "parpadeo_der"),
    (2,  "parpadeo_izq"),
    (6,  "cejas_arriba"),
    (7,  "cejas_abajo"),
    (4,  "ojos_arriba"),
    (5,  "ojos_abajo"),
]

# ===================== ESTADO =====================

state             = "idle"
cooldown_until    = 0.0
last_gesture_time = time.time()
last_sent_gesture = -1

prev_jaw          = None
oscillation_count = 0
jaw_direction     = None
last_jaw_motion   = time.time()

# ===================== HELPERS =====================

def avg(a, b):
    return (a + b) / 2.0

# ===================== MAIN LOOP =====================

DEBUG = "--debug" in sys.argv

while True:
    line = sys.stdin.readline()
    if not line:
        break
    line = line.strip()
    if not line:
        continue

    try:
        data = json.loads(line)
    except json.JSONDecodeError:
        continue

    blendshapes = data.get("blendshapes", {})
    if not blendshapes:
        continue

    now      = time.time()
    jaw_open = blendshapes.get("jawOpen", 0)

    # --- Detección de habla (acumula oscilaciones entre frames) ---
    if prev_jaw is not None:
        diff = jaw_open - prev_jaw
        if abs(diff) > 0.02:
            new_dir = "up" if diff > 0 else "down"
            if jaw_direction is not None and new_dir != jaw_direction:
                oscillation_count += 1
            jaw_direction = new_dir
            last_jaw_motion = now
        elif jaw_open < TALK_RESET_JAW and (now - last_jaw_motion) > TALK_RESET_SECONDS:
            oscillation_count = 0
            jaw_direction     = None
    prev_jaw = jaw_open

    is_talking = (jaw_open > TALK_JAW_THRESHOLD and oscillation_count >= TALK_OSCILLATIONS)

    if DEBUG:
        bl = blendshapes.get("eyeBlinkLeft", 0)
        br = blendshapes.get("eyeBlinkRight", 0)
        bu = blendshapes.get("browInnerUp", 0)
        bd = max(blendshapes.get("browDownLeft", 0), blendshapes.get("browDownRight", 0))
        sm = max(blendshapes.get("mouthSmileLeft", 0), blendshapes.get("mouthSmileRight", 0))
        print(
            f"[debug] blink L={bl:.2f} R={br:.2f} | brow_up={bu:.2f} brow_dn={bd:.2f} | "
            f"jaw={jaw_open:.2f} | smile={sm:.2f} | talk={is_talking}({oscillation_count}) | state={state}",
            file=sys.stderr, flush=True
        )

    # --- Máquina de estados ---
    if state == "cooldown":
        if now >= cooldown_until:
            state = "idle"
        else:
            continue

    # --- Leer blendshapes ---
    blink_l     = blendshapes.get("eyeBlinkLeft", 0)
    blink_r     = blendshapes.get("eyeBlinkRight", 0)
    brow_up     = blendshapes.get("browInnerUp", 0)
    smile_l     = blendshapes.get("mouthSmileLeft", 0)
    smile_r     = blendshapes.get("mouthSmileRight", 0)
    brow_down_l = blendshapes.get("browDownLeft", 0)
    brow_down_r = blendshapes.get("browDownRight", 0)
    press_l     = blendshapes.get("mouthPressLeft", 0)
    press_r     = blendshapes.get("mouthPressRight", 0)
    look_up_l   = blendshapes.get("eyeLookUpLeft", 0)
    look_up_r   = blendshapes.get("eyeLookUpRight", 0)
    look_down_l = blendshapes.get("eyeLookDownLeft", 0)
    look_down_r = blendshapes.get("eyeLookDownRight", 0)

    # --- Evaluar gestos por prioridad ---
    chosen_id   = -1
    chosen_name = None

    for gid, gname in GESTURE_PRIORITY:
        triggered = False

        if gid == 3:
            triggered = (blink_l > BLINK_THRESHOLD and blink_r > BLINK_THRESHOLD)
        elif gid == 10:
            triggered = (avg(smile_l, smile_r) > SMILE_THRESHOLD)
        elif gid == 8:
            triggered = (brow_up > BROW_UP_THRESHOLD and avg(press_l, press_r) > MOUTH_PRESS_THRESHOLD)
        elif gid == 9:
            triggered = (jaw_open > JAW_OPEN_THRESHOLD and brow_up > BROW_UP_THRESHOLD * 0.8)
        elif gid == 14:
            triggered = is_talking
        elif gid == 13:
            triggered = (jaw_open > JAW_OPEN_THRESHOLD + 0.15)
        elif gid == 1:
            triggered = (blink_r > BLINK_THRESHOLD and blink_l < BLINK_THRESHOLD * 0.6)
        elif gid == 2:
            triggered = (blink_l > BLINK_THRESHOLD and blink_r < BLINK_THRESHOLD * 0.6)
        elif gid == 6:
            triggered = (brow_up > BROW_UP_THRESHOLD)
        elif gid == 7:
            triggered = (max(brow_down_l, brow_down_r) > BROW_DOWN_THRESHOLD)
        elif gid == 4:
            triggered = (max(look_up_l, look_up_r) > EYE_LOOK_THRESHOLD)
        elif gid == 5:
            triggered = (max(look_down_l, look_down_r) > EYE_LOOK_THRESHOLD)

        if triggered:
            chosen_id   = gid
            chosen_name = gname
            break

    # --- Auto-blink si no hay gesto ---
    if chosen_id == -1 and AUTO_BLINK_ENABLED and (now - last_gesture_time) > AUTO_BLINK_INTERVAL:
        chosen_id   = 3
        chosen_name = "parpadeo_doble"

    # --- Reposo: solo enviar la transición una vez ---
    if chosen_id == -1:
        if last_sent_gesture not in (-1, 0):
            chosen_id   = 0
            chosen_name = "reposo"
        else:
            continue

    # --- Aplicar cooldown y emitir ---
    state             = "cooldown"
    cooldown_until    = now + GESTURE_COOLDOWN.get(chosen_id, 1.5)
    last_gesture_time = now
    last_sent_gesture = chosen_id

    print(json.dumps({"gesture": chosen_id, "name": chosen_name}), flush=True)
