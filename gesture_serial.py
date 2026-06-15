#!/usr/bin/env python3
"""
gesture_serial.py — reads gesture JSON from stdin, sends plain text
commands over serial to the Arduino.

Protocol: sends the gesture number as a decimal string + newline.
  "3\\n"  -> Arduino triggers double blink
  "0\\n"  -> Arduino goes to rest position

Pipeline: face_capture.py | classify_gesture.py | gesture_serial.py
"""

import sys
import json
import serial
import time
import io

sys.stdin = io.TextIOWrapper(sys.stdin.buffer, line_buffering=True)

SERIAL_PORT = "COM6"
BAUD_RATE = 9600
SEND_INTERVAL = 0.2

try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
    # El Arduino se resetea al abrir el puerto serial.
    # Esperar a que arranque para no perder los primeros comandos.
    print(f"[gesture_serial] Puerto {SERIAL_PORT} abierto a {BAUD_RATE} baud", file=sys.stderr, flush=True)
    time.sleep(2)
    ser.reset_input_buffer()
except serial.SerialException as e:
    print(f"[gesture_serial] ERROR al abrir {SERIAL_PORT}: {e}", file=sys.stderr)
    sys.exit(1)

last_send_time = 0.0

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
        print(f"[gesture_serial] JSON inválido: {line!r}", file=sys.stderr, flush=True)
        continue

    gesture = data.get("gesture", -1)
    if gesture < 0:
        continue

    now = time.time()
    if now - last_send_time < SEND_INTERVAL:
        continue

    cmd = f"{gesture}\n"
    ser.write(cmd.encode("utf-8"))
    last_send_time = now
    print(f"[gesture_serial] -> '{cmd.strip()}' ({data.get('name', '?')})", file=sys.stderr, flush=True)
