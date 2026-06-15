import sys
import json
import serial
import time

# Hiper simplificado. Ahora depende tambien de set_directions.py
# Hecho con poca verguenza con IA. Puras mamadas.
ser = serial.Serial('/dev/ttyUSB0', 115200, timeout=0.1)
last_send_time = 0
send_interval = 0.2

def to_hex(val):
    n = round(val)
    if n < 0:
        return "-" + format(-n, "x")
    return format(n, "x")

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue

    try:
        data = json.loads(line)
    except json.JSONDecodeError:
        continue

    current_time = time.time()
    if current_time - last_send_time < send_interval:
        continue

    parts = [f"{k}:{to_hex(v)}" for k, v in data.items()]
    packet = "$" + ";".join(parts) + "#"
    ser.write(packet.encode("utf-8"))
    last_send_time = current_time
