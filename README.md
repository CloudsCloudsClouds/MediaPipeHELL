# Sistema TEA — Aprendizaje Socioemocional con Robot Animatrónico

Sistema de reconocimiento de objetos y expresión facial para un robot animatrónico,
diseñado para trabajar habilidades socioemocionales en niños con TEA (Trastorno del Espectro Autista).

## Arquitectura del Sistema

```
                    ┌────────────────────────────────────────┐
                    │           Frontend Web (React)         │
                    │          localhost:5173 (dev)          │
                    │          localhost:8000  (prod)        │
                    └──────────────────┬─────────────────────┘
                                       │ WebSocket + REST API
                    ┌──────────────────▼─────────────────────┐
                    │         Backend (FastAPI + Python)     │
                    │         server.py — localhost:8000     │
                    │                                        │
                    │  ┌────────┐ ┌─────────┐ ┌────────────┐ │
                    │  │ Mód. 1 │ │ Mód. 2  │ │  Mód. 3    │ │
                    │  │ YOLO   │ │MediaPipe│ │Lazo Cerrado│ │
                    │  │ Objetos│ │Rostro   │ │PID + 2 cams│ │
                    │  └────────┘ └─────────┘ └────────────┘ │
                    └──────────────────┬─────────────────────┘
                                       │ Serial (9600 baud)
                    ┌──────────────────▼─────────────────────┐
                    │         Arduino Uno + PCA9685          │
                    │         Servos × 6+ (cara + brazos)    │
                    └────────────────────────────────────────┘
```

## Hardware Requerido

| Componente             | Especificación                           |
|------------------------|------------------------------------------|
| Cámara A (escena)      | Webcam USB 720p mínimo (índice 0)        |
| Cámara B (robot)       | Webcam USB 720p mínimo (índice 1)        |
| Microcontrolador       | Arduino Uno (o compatible)               |
| Driver PWM             | PCA9685 (módulo I2C)                     |
| Servos cara            | 6 servos (mandíbula, cejas, ojos, boca)  |
| Servo brazo            | 1 servo (CHECK / DESAPRUEBO)             |
| PC                     | Linux o Windows, CPU con AVX (YOLO v11)  |

> El Módulo 1 funciona con 1 cámara. El Módulo 2 funciona con 1 cámara.
> El Módulo 3 requiere **2 cámaras** (una apuntando a la persona, otra al robot).

## Instalación

### 1. Clonar e instalar dependencias

```bash
git clone <repo>
cd MediaPipeHELL
uv sync                 # instala el entorno virtual con todas las dependencias
```

### 2. Verificar modelo MediaPipe

El modelo `face_landmarker_v2_with_blendshapes.task` (~10 MB) se descarga
automáticamente la primera vez que se ejecuta cualquier módulo que lo requiera.

### 3. Verificar modelo YOLO

YOLO v11 descarga `yolo11s.pt` automáticamente al iniciar el Módulo 1.

### 4. (Opcional) Compilar frontend

```bash
cd web
npm install
npm run build          # produce dist/
```

En desarrollo, usar `npm run dev` (Vite en puerto 5173).

## Uso

### Servidor backend (siempre necesario)

```bash
.venv/bin/python server.py
# o
make server
```

Esto levanta:
- **API REST** en `http://localhost:8000`
- **WebSocket** en `ws://localhost:8000/ws`
- **Streams MJPEG** en `/stream/1`, `/stream/2`, `/stream/3`

### Interfaz web

```bash
cd web
npm run dev            # desarrollo (proxy al backend)
# o abre http://localhost:8000 en el navegador (frontend servido por FastAPI)
```

## Módulos

### Módulo 1 — Reconocimiento de Objetos

```bash
make mod1     # lanza el backend internamente
# o desde la web: selecciona "Reconocimiento de Objetos"
```

- **Modelo**: YOLO v11 (`yolo11s.pt`)
- **Pipeline**: `server.py` → `run_module1.py` → `tea_object_emotion.py`
- **Detecta**: 30+ objetos (manzana, libro, tijeras, pelota, etc.)
- **Reacciona**: asigna emoción al objeto detectado y envía gesto al robot
- **Capturas**: guarda automáticamente la reacción del objeto detectado

**Mapeo objeto → emoción** (parcial):

| Objetos               | Emoción  | Gesto brazo |
|-----------------------|----------|-------------|
| apple, banana, book   | feliz    | CHECK       |
| knife, scissors, gun  | miedo    | DESAPRUEBO  |
| battery, trash        | enojo    | DESAPRUEBO  |
| clock, vase, balloon  | asombro  | CHECK       |
| bottle, cup, spoon    | neutral  | CHECK       |

**Entrenamiento personalizado**: presiona `t` en la ventana YOLO para entrenar
un detector de objetos de enojo (pilas, vidrio roto) tras capturar 10-20 muestras.

### Módulo 2 — Reacción Duplicada

```bash
make mod2     # lanza el backend internamente
# o desde la web: selecciona "Reacción Duplicada"
```

- **Modelo**: MediaPipe FaceLandmarker (LIVE_STREAM)
- **Pipeline**: `run_face_capture.py` → `classify_gesture.py` → `gesture_serial.py`
- **Blendshapes**: 52 coeficientes ARKit (jawOpen, browInnerUp, eyeBlinkLeft, etc.)
- **Gestos clasificados**: sonrisa, ceño, sorpresa, párpados, etc.
- **Salida serial**: número de gesto (`0\n`–`10\n`), Arduino ejecuta la expresión

### Módulo 3 — Lazo Cerrado (PID)

```bash
make feedback  # lanza servidor + visual_feedback_controller
# o desde la web: selecciona "Lazo Cerrado"
```

- **Modelo**: MediaPipe FaceLandmarker (IMAGE — síncrono)
- **Control**: PID digital sobre `jawOpen`
- **2 cámaras**: cámara A = referencia humana, cámara B = robot
- **Documentación detallada**: ver [control.md](control.md)

```python
# PID: valores por defecto ajustables por flag
Kp=0.8, Ki=0.05, Kd=0.1
```

## Protocolo Serial

### Módulo 1 y 2 (gestos discretos)

```
cmd = f"{gesture_id}\n"         # gesture_serial.py:60
# gesture_id: 0=neutro, 8=enojo, 9=sorpresa, 10=feliz
```

### Módulo 3 (ángulos continuos)

```
packet = f"${jaw:.2f},0,0,0,0,0#\n"   # visual_feedback_controller.py:107
# Formato: $jaw,smileL,smileR,blinkL,blinkR,yaw#
# jaw en grados [0.0, 20.0]
```

Velocidad: **9600 baud**, 8N1.

### Módulo 3 (legacy bridge)

```
packet = "$" + ";".join(parts) + "#"   # serial_bridge.py:33
# Formato: $key:hex;key:hex;...#  (115200 baud)
```

## Makefile

### Targets principales

| Comando            | Acción                                        |
|--------------------|-----------------------------------------------|
| `make help`        | Muestra ayuda completa con todos los targets  |
| `make server`      | Inicia servidor backend FastAPI               |
| `make web`         | Inicia frontend de desarrollo (Vite)          |
| `make web-build`   | Compila frontend para producción              |

### Módulo 1 — Reconocimiento de Objetos

| Comando | Acción |
|---------|--------|
| `make mod1` | Lanza server + módulo, abre interfaz web |

### Módulo 2 — Reacción Duplicada

| Comando         | Pipeline                                    |
|-----------------|---------------------------------------------|
| `make mod2`     | `run_face_capture` → `classify` → `serial` (wrapper web) |
| `make face-gesture` | `face_capture` → `classify` → `serial` (legacy)    |
| `make face-stream`  | `face_capture` → `set_directions` → `serial_bridge` |
| `make pose-gesture` | `pose_capture` → `classify` → `serial`             |
| `make pose-stream`  | `pose_capture` → `set_directions` → `serial_bridge` |

### Módulo 3 — Lazo Cerrado (PID)

| Comando            | Acción                                      |
|--------------------|---------------------------------------------|
| `make feedback`    | PID con 2 cámaras (valores por defecto)     |
| `make feedback-cam`| Índices de cámara custom                    |
| `make feedback-tune`| Ganancias PID custom                       |

### Utilidades

| Comando             | Acción                                      |
|---------------------|---------------------------------------------|
| `make classify`     | Solo clasificador (pipe stdin → stdout)     |
| `make bridge`       | `serial_bridge` standalone                  |
| `make test-pipeline`| Datos de prueba                             |
| `make clean`        | Capturas, frames temporales, `__pycache__`  |
| `make lint`         | Verifica sintaxis de todos los `.py`        |

### Flags comunes

```bash
ARGS="..."             # Argumentos extra para el script
make feedback ARGS="--camera-a 2 --camera-b 3"
make face-gesture SERIAL_PORT=COM6
```

## Estructura del Proyecto

```
MediaPipeHELL/
├── server.py                       # Backend FastAPI (orquestador)
├── run_module1.py                  # Wrapper Módulo 1 (captura frames YOLO)
├── run_face_capture.py             # Wrapper Módulo 2 (captura frames MediaPipe)
├── visual_feedback_controller.py   # Módulo 3 (PID + 2 cámaras)
├── tea_object_emotion.py           # YOLO + emociones (legacy)
├── face_capture.py                 # MediaPipe FaceLandmarker (LIVE_STREAM)
├── classify_gesture.py             # Clasificador de gestos faciales
├── gesture_serial.py               # Envío serial de gestos
├── robot_face_landmarks.py         # FaceLandmarker en modo IMAGE (Módulo 3)
├── robot_face_state.py             # Mapeo blendshapes → ángulos servo
├── face_gestures_servo.py          # Prototipo original (LIVE_STREAM + serial)
├── set_directions.py               # Mapeo de direcciones (legacy)
├── serial_bridge.py                # Bridge serial a 115200 baud (legacy)
├── test_pipeline.py                # Genera datos de prueba para el pipeline
├── Makefile                        # Comandos de uso común
├── control.md                      # Documentación del lazo cerrado (Módulo 3)
├── pyproject.toml                  # Dependencias Python
├── captures/                       # Capturas automáticas (Módulo 1)
└── web/
    ├── package.json
    ├── vite.config.js
    └── src/
        ├── App.jsx                 # Componente principal React
        ├── App.css                 # Sistema de diseño (tema oscuro)
        └── Icon.jsx                # Componente de iconos (Font Awesome)
```

## Solución de Problemas

| Problema                     | Causa probable                         | Solución                                      |
|------------------------------|----------------------------------------|-----------------------------------------------|
| `SerialException`            | Puerto ocupado (Arduino IDE abierto)   | Cerrar Serial Monitor, verificar `/dev/ttyUSB0`|
| Cámara no abre               | Índice incorrecto                      | Probar `--camera-a 1 --camera-b 0`            |
| PID no corrige               | Cámara B no ve al robot                | Asegurar rostro del robot en cuadro            |
| Backend crashea al detener   | Falta `start_new_session` (fixed)      | `git pull`, actualizar server.py               |
| YOLO lento                   | CPU sin AVX                            | Usar modelo más pequeño (`yolo11n.pt`)         |
| `uv sync` falla              | Python < 3.9                           | Actualizar Python                              |

## Licencia

```
Derechos reservados — Proyecto académico
Osea usalo, pero ya pues.
```
