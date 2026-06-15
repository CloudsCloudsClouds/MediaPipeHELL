import argparse
import json
import os
import platform
import signal
import sys
import tempfile
import time
from pathlib import Path

import cv2
import numpy as np

from robot_face_landmarks import RobotFaceLandmarker
import robot_face_state

FRAME_FILE = Path(tempfile.gettempdir()) / "tea_module3_frame.jpg"
JPEG_PARAMS = [cv2.IMWRITE_JPEG_QUALITY, 72]


class PID:
    def __init__(self, Kp=1.0, Ki=0.0, Kd=0.0, output_limits=(0.0, 20.0)):
        self.Kp = Kp
        self.Ki = Ki
        self.Kd = Kd
        self.output_limits = output_limits
        self.reset()

    def reset(self):
        self._integral = 0.0
        self._prev_error = 0.0
        self._last_time = None

    def update(self, measurement: float, setpoint: float, dt: float | None = None) -> float:
        now = time.time()
        if dt is None:
            if self._last_time is not None:
                dt = now - self._last_time
            else:
                dt = 1.0 / 30.0
        self._last_time = now

        error = setpoint - measurement
        self._integral += error * dt
        derivative = (error - self._prev_error) / dt if dt > 0 else 0.0
        self._prev_error = error

        output = self.Kp * error + self.Ki * self._integral + self.Kd * derivative
        lo, hi = self.output_limits
        return max(lo, min(hi, output))


def _save_frame(frame: np.ndarray):
    try:
        ok, buf = cv2.imencode(".jpg", frame, JPEG_PARAMS)
        if ok:
            FRAME_FILE.write_bytes(buf.tobytes())
    except Exception:
        pass


def _draw_face(frame: np.ndarray, result: dict):
    landmarks = result.get("landmarks")
    if not landmarks:
        return
    h, w = frame.shape[:2]
    for face_lms in landmarks:
        for lm in face_lms:
            x = int(lm[0] * w)
            y = int(lm[1] * h)
            cv2.circle(frame, (x, y), 1, (0, 255, 0), -1)


def _draw_info(frame: np.ndarray, lines: list[str], color=(255, 255, 0)):
    for i, line in enumerate(lines):
        cv2.putText(frame, line, (10, 30 + i * 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)


def _open_camera(index: int, label: str):
    cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        print(f"[vfc] ERROR: No se pudo abrir camara {label} (indice {index})",
              file=sys.stderr, flush=True)
        sys.exit(1)
    print(f"[vfc] Camara {label} (indice {index}) abierta",
          file=sys.stderr, flush=True)
    return cap


def _open_serial(port: str, baud: int):
    try:
        import serial as pyserial
        ser = pyserial.Serial(port, baud, timeout=0.1)
        time.sleep(2)
        ser.reset_input_buffer()
        print(f"[vfc] Serial {port} ({baud} baud) abierto",
              file=sys.stderr, flush=True)
        return ser
    except Exception as e:
        print(f"[vfc] Serial no disponible: {e}", file=sys.stderr, flush=True)
        return None


def _send_serial(ser, jaw_angle: float):
    if ser is None:
        return
    packet = f"${jaw_angle:.2f},0,0,0,0,0#\n"
    try:
        ser.write(packet.encode("utf-8"))
    except Exception as e:
        print(f"[vfc] Error serial: {e}", file=sys.stderr, flush=True)


def main():
    parser = argparse.ArgumentParser(description="Controlador de lazo cerrado con retroalimentacion visual")
    parser.add_argument("--camera-a", type=int, default=0, help="Indice camara A (escena externa)")
    parser.add_argument("--camera-b", type=int, default=1, help="Indice camara B (robot)")
    _IS_WINDOWS = platform.system() == "Windows"
    _DEF_PORT = "COM6" if _IS_WINDOWS else "/dev/ttyUSB0"
    parser.add_argument("--serial-port", default=_DEF_PORT)
    parser.add_argument("--baud", type=int, default=9600)
    parser.add_argument("--kp", type=float, default=0.8)
    parser.add_argument("--ki", type=float, default=0.05)
    parser.add_argument("--kd", type=float, default=0.1)
    args = parser.parse_args()

    print("[vfc] Iniciando controlador de lazo cerrado...", file=sys.stderr, flush=True)

    cap_a = _open_camera(args.camera_a, "A (escena)")
    cap_b = _open_camera(args.camera_b, "B (robot)")

    landmarker = RobotFaceLandmarker()
    pid = PID(Kp=args.kp, Ki=args.ki, Kd=args.kd)
    ser = _open_serial(args.serial_port, args.baud)

    stop = False

    def _on_sig(signum, frame):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGINT, _on_sig)
    try:
        signal.signal(signal.SIGTERM, _on_sig)
    except ValueError:
        pass  # Windows no permite registrar handler para SIGTERM

    frame_count = 0

    while not stop:
        ret_a, frame_a = cap_a.read()
        if not ret_a:
            print("[vfc] Error leyendo camara A", file=sys.stderr, flush=True)
            break

        ret_b, frame_b = cap_b.read()
        if not ret_b:
            print("[vfc] Error leyendo camara B", file=sys.stderr, flush=True)
            break

        result_a = landmarker.detect(frame_a)
        result_b = landmarker.detect(frame_b)

        bs_a = result_a.get("blendshapes", {})
        bs_b = result_b.get("blendshapes", {})

        target_jaw = bs_a.get("jawOpen", 0.0)
        feedback_jaw = bs_b.get("jawOpen", 0.0)

        correction = pid.update(feedback_jaw, setpoint=target_jaw)

        _draw_face(frame_b, result_b)
        _draw_info(frame_b, [
            f"Blanco (cam A): jaw={target_jaw:.2f}",
            f"Retro (cam B):  jaw={feedback_jaw:.2f}",
            f"Correccion PID:  {correction:.2f}  (Kp={pid.Kp} Ki={pid.Ki} Kd={pid.Kd})",
            f"Servos: {robot_face_state.get_all_angles(bs_b)}",
        ])

        _save_frame(frame_b)

        _send_serial(ser, correction)

        if frame_count % 10 == 0:
            yaw = robot_face_state.get_yaw_deg(result_b.get("transform", {}))
            state = {
                "type": "feedback_state",
                "target_jaw": round(target_jaw, 3),
                "feedback_jaw": round(feedback_jaw, 3),
                "correction": round(correction, 3),
                "yaw_deg": round(yaw, 1),
                "pid": {"Kp": pid.Kp, "Ki": pid.Ki, "Kd": pid.Kd},
            }
            sys.stdout.write(json.dumps(state) + "\n")
            sys.stdout.flush()

        frame_count += 1
        time.sleep(1 / 30)

    print("[vfc] Deteniendo...", file=sys.stderr, flush=True)
    landmarker.close()
    cap_a.release()
    cap_b.release()
    if ser:
        ser.close()
    print("[vfc] Detenido", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
