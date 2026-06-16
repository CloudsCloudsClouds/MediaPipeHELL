import math

SERVO_MAP = {
    "jaw":       "jawOpen",
    "brow":      "browInnerUp",
    "eye_l":     "eyeBlinkLeft",
    "eye_r":     "eyeBlinkRight",
    "smile_l":   "mouthSmileLeft",
    "smile_r":   "mouthSmileRight",
    "brow_dn_l": "browDownLeft",
    "brow_dn_r": "browDownRight",
    "press_l":   "mouthPressLeft",
    "press_r":   "mouthPressRight",
}

SERVO_RANGES = {
    "jaw":       (0.0, 20.0),
    "brow":      (-5.0, 10.0),
    "eye_l":     (0.0, 15.0),
    "eye_r":     (0.0, 15.0),
    "smile_l":   (-3.0, 8.0),
    "smile_r":   (-3.0, 8.0),
    "brow_dn_l": (0.0, 8.0),
    "brow_dn_r": (0.0, 8.0),
    "press_l":   (0.0, 5.0),
    "press_r":   (0.0, 5.0),
}


def blendshape_to_angle(blendshapes: dict, servo: str) -> float:
    bs_name = SERVO_MAP.get(servo)
    if bs_name is None:
        return 0.0
    score = blendshapes.get(bs_name, 0.0)
    score = max(0.0, min(1.0, score))
    lo, hi = SERVO_RANGES.get(servo, (0.0, 0.0))
    return lo + score * (hi - lo)


def get_all_angles(blendshapes: dict) -> dict:
    return {s: round(blendshape_to_angle(blendshapes, s), 2) for s in SERVO_MAP}


def get_yaw_deg(transform: dict) -> float:
    if not transform:
        return 0.0
    return math.degrees(math.atan2(
        -transform.get("m20", 0),
        math.sqrt(transform.get("m00", 0)**2 + transform.get("m10", 0)**2)
    ))


TRACKED_SHAPES = [
    "jawOpen", "browInnerUp", "eyeBlinkLeft", "eyeBlinkRight",
    "mouthSmileLeft", "mouthSmileRight",
    "browDownLeft", "browDownRight",
    "mouthPressLeft", "mouthPressRight",
    "eyeLookUpLeft", "eyeLookUpRight",
    "eyeLookDownLeft", "eyeLookDownRight",
]
