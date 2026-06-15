> [!NOTE] Ejecutar para el ultimo codigo de arduino

> El ultimo codigo de arduino utiliza comandos, no stream de datos

> Para ejecutar el codigo actual, utiliza:

> `uv run face_capture.py | uv run classify_gesture.py | uv run gesture_serial.py`

> Este utiliza 3 scripts

> `face_capture` es "el cerebro", detecta rostros.

>   `pose_capture.py` tambien funciona, detecta rostros y apuntar con el dedo

> `classify_gesture` interpreta los datos del cerebro a comandos para el arduino

> `gesture_serial` manda los comandos por serial

---

# Experimentos de mediapipe para el proyecto del robot

Utilizo [`uv`](https://docs.astral.sh/uv/). Instalenlo. Tambien utilizo venv por buena medida

Sel setup para tener esto corriendo es.

1. [Instalar `uv`](https://docs.astral.sh/uv/getting-started/installation/)
2. Crear venv y usarlo
```
uv venv
source .venv/bin/activate
# O el que utilizen segun su OS, o cmd
```
3. Correr las demos

- [x] Deteccion de cabeza en general - `uv run face_detection.py`
- ~~[x] Deteccion de gestos de el rostro - `uv run face_gestures.py`~~
  - ~~[-] Enviar informacion sobre los gestos mediante serial - `uv run face_gestures_servo.py`~~
  - ~~Mejor utilizar `uv run face_capture.py`, este desacopla la logica de deteccion de rostros.~~
  - ~~[x] Añadido `serial_bridge.py`, que decide QUE mandar por serial. Desacoplamiento.~~
- [x] Deteccion de rostro, conversion de datos a grados y envio por serial.
  - `uv run face_capture.py set_directions.py serial_bridge.py`
  - `face_capture.py` Deteccion de gestos, y  "dumpea" los datos en stdout en formato json
  - `set_directions.py` Lee datos de stdout y los convierte en grados. Configurable de que llaves, ojos, rangos, eso.
  - `serial_bridge.py` Envio de datos mediante serial. Configurable del puerto, baud, etc.
- [-] Deteccion de gestos del brazo
  - Postergado por el momento
- [x] Deteccion de apuntar a direccion con los ~~brazos~~ indice
- [x] Clasificador de gestos faciales para control por comandos
  - `uv run face_capture.py | uv run classify_gesture.py | uv run gesture_serial.py`
  - `classify_gesture.py` Lee datos del rostro y clasifica la expresion en un comando de gesto (parpadeo, sonrisa, sorpresa, etc.)
  - `gesture_serial.py` Envia el comando como texto plano por serial al Arduino (9600 baud)
  - Los comandos corresponden a los gestos preprogramados en el firmware del Arduino
  - `uv run pose_capture.py set_directions.py serial_bridge.py`
  - Nomas funciona con el indice, y hay un error que no distingue entre mano plana y apuntar. 
    - Probablemente corregible con ese landmark de pistola.

Notar que esto por ahora son demos y no hay comunicacion con el robot mediante serial. Esto esta reservado un proyecto distinto utilizando ros (no viable por ahora).
