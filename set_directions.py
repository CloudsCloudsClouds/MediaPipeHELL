import sys
import json
import math

# Consider, this isn't the brain. This just takes whats already on the stdout
# and sets the directions based on that.
# Good for serial_bridge.

# Enble to send eyes.
EYE_ENABLED = True
EYE_SCALE = 100

# MediaPipe Face Landmarker (ARKit 52) Blendshape Keys:
# _neutral, browDownLeft, browDownRight, browInnerUp, browOuterUpLeft, browOuterUpRight,
# cheekPuff, cheekSquintLeft, cheekSquintRight, eyeBlinkLeft, eyeBlinkRight,
# eyeLookDownLeft, eyeLookDownRight, eyeLookInLeft, eyeLookInRight, eyeLookOutLeft,
# eyeLookOutRight, eyeLookUpLeft, eyeLookUpRight, eyeSquintLeft, eyeSquintRight,
# eyeWideLeft, eyeWideRight, jawForward, jawLeft, jawOpen, jawRight, mouthClose,
# mouthDimpleLeft, mouthDimpleRight, mouthFrownLeft, mouthFrownRight, mouthFunnel,
# mouthLeft, mouthLowerDownLeft, mouthLowerDownRight, mouthPressLeft, mouthPressRight,
# mouthPucker, mouthRight, mouthRollLower, mouthRollUpper, mouthShrugLower,
# mouthShrugUpper, mouthSmileLeft, mouthSmileRight, mouthStretchLeft, mouthStretchRight,
# mouthUpperUpLeft, mouthUpperUpRight, noseSneerLeft, noseSneerRight
#
# Select what you need. Except EYES.


# For each key:
#   source: blendshape name | "transform" (yaw from matrix) | "direct" (key from JSON root)
#   range: output range for the servos
#   src_range: (optional, for "direct") input range to remap from

DIRECTION_CONFIG = {
    "jaw":    {"source": "jawOpen",        "range": (0, 30)},
    "brow":   {"source": "browInnerUp",    "range": (0, 20)},
    "smileL": {"source": "mouthSmileLeft",  "range": (0, 40)},
    "smileR": {"source": "mouthSmileRight", "range": (0, 40)},
    "blinkL": {"source": "eyeBlinkLeft",    "range": (0, 100)},
    "blinkR": {"source": "eyeBlinkRight",   "range": (0, 100)},
    "yaw":    {"source": "direct",          "src_range": (-180, 180), "range": (-90, 90)},
}

def compute_yaw(matrix):
    m00 = matrix["m00"]; m10 = matrix["m10"]; m20 = matrix["m20"]
    yaw_rad = math.atan2(-m20, math.sqrt(m00**2 + m10**2))
    return math.degrees(yaw_rad)

def lerp(val, src, dst):
    src_lo, src_hi = src
    dst_lo, dst_hi = dst
    clamped = max(src_lo, min(src_hi, val))
    if src_hi == src_lo:
        return (dst_lo + dst_hi) / 2
    ratio = (clamped - src_lo) / (src_hi - src_lo)
    return dst_lo + ratio * (dst_hi - dst_lo)

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue

    try:
        data = json.loads(line)
    except json.JSONDecodeError:
        continue

    blendshapes = data.get("blendshapes", {})
    transform = data.get("transform", {})
    output = {}

    for key, cfg in DIRECTION_CONFIG.items():
        if cfg["source"] == "transform":
            if transform:
                raw = compute_yaw(transform)
            else:
                raw = 0.0
            output[key] = lerp(raw, (-90, 90), cfg["range"])
        elif cfg["source"] == "direct":
            raw = data.get(key, 0.0)
            if "src_range" in cfg:
                output[key] = lerp(raw, cfg["src_range"], cfg["range"])
            else:
                output[key] = raw
        else:
            raw = blendshapes.get(cfg["source"], 0.0)
            output[key] = lerp(raw, (0, 1), cfg["range"])

    if EYE_ENABLED:
        # If the upstream brain (pose_capture) already computed eye override, use it.
        eye_ox = data.get("eye_x")
        eye_oy = data.get("eye_y")
        if eye_ox is not None and eye_oy is not None:
            output["elx"] = eye_ox
            output["ely"] = eye_oy
            output["erx"] = eye_ox
            output["ery"] = eye_oy
        else:
            li = blendshapes.get("eyeLookInLeft", 0)
            lo = blendshapes.get("eyeLookOutLeft", 0)
            lu = blendshapes.get("eyeLookUpLeft", 0)
            ld = blendshapes.get("eyeLookDownLeft", 0)
            output["elx"] = (li - lo) * EYE_SCALE   # + = in (toward nose)
            output["ely"] = (lu - ld) * EYE_SCALE   # + = up

            ri = blendshapes.get("eyeLookInRight", 0)
            ro = blendshapes.get("eyeLookOutRight", 0)
            ru = blendshapes.get("eyeLookUpRight", 0)
            rd = blendshapes.get("eyeLookDownRight", 0)
            output["erx"] = (ri - ro) * EYE_SCALE
            output["ery"] = (ru - rd) * EYE_SCALE

    print(json.dumps(output), flush=True)
