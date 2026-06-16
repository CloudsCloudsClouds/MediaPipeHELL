# Módulo 3 — Modelo de Planta y Control de Lazo Cerrado

## 1. Arquitectura del Sistema

```
                ┌──────────────────────────────────────────────────────────┐
                │                    Computadora                           │
                │                                                          │
r(t)  ──►  ┌──────────┐   ┌────────────┐   jawOpen_A  ┌──────┐  e(t)  ┌───┴───┐  u(t)  ┌────────┐  ┌────────┐  ┌──────┐
           │ Cámara A │──►│  MediaPipe  │─────────────►│  (+) │──────►│  PID  │──────►│ Serial │─►│Arduino │─►│PCA9685│──► jaw° │
           │(escena)  │   │FaceLandmark │              │  ∧   │       │       │       │  USB   │  │  Uno   │  │PWM    │     │
           └──────────┘   └────────────┘               │  │   │       └───────┘       └────────┘  └────────┘  └──────┘     │
                                                        │  │   │                                                        │
           ┌──────────┐   ┌────────────┐   jawOpen_B   │  │   │                                                     ┌──┴───┐
           │ Cámara B │──►│  MediaPipe  │───────────────┘  │   │                                                     │Robot │
           │ (robot)  │   │FaceLandmark │                  │   │                                                     │Face  │
           └──────────┘   └────────────┘   y(t)            │   │                                                     └──────┘
                │                                          │   │
                └────── frame_B ───► overlay ──► /stream/3 ┘   │
                                                                │
                ───► stdout ──► feedback_state ──► WebSocket    │
                                                                │
                r(t) : setpoint (jawOpen de la escena)          │
                y(t) : medición  (jawOpen del robot)            │
                e(t) : error  =  r(t) - y(t)                    │
                u(t) : corrección PID (grados de servo)         │
                └───────────────────────────────────────────────┘
```

El sistema utiliza **dos cámaras** para cerrar el lazo de control:

- **Cámara A (escena)**: captura el rostro humano de referencia → produce el **setpoint** $r(t)$
- **Cámara B (robot)**: captura el rostro del robot → produce la **medición** $y(t)$

Ambas cámaras se procesan con el mismo modelo MediaPipe FaceLandmarker en modo `IMAGE` (síncrono), garantizando homogeneidad en la extracción de *blendshapes*. La variable controlada es `jawOpen`, el *blendshape* que describe la apertura mandibular.

---

## 2. Modelo de Planta

### 2.1 Actuador

```python
packet = f"${jaw_angle:.2f},0,0,0,0,0#\n"   # visual_feedback_controller.py:107
```

| Componente     | Especificación                               |
|----------------|----------------------------------------------|
| Microcontrolador | Arduino Uno                                  |
| Driver PWM     | PCA9685 (16 canales, 12-bit, 1.6 kHz)        |
| Actuador       | Servomotor de rotación continua/limitada      |
| Transmisión    | Cable USB (serial virtual a 9600 baud)        |
| Protocolo      | `$jaw,smileL,smileR,blinkL,blinkR,yaw#\n`    |

La planta convierte un ángulo deseado $u(t)$ (en grados) en una posición física de la mandíbula del robot. La dinámica agregada incluye:

- Retardo de comunicación serial: $\tau_{tx} \approx 1\text{--}2\,\text{ms}$ a 9600 baud
- Ciclo PWM del PCA9685: $T_{PWM} = 1/1600 \approx 0.625\,\text{ms}$
- Tiempo de asentamiento del servo: $\tau_{servo} \approx 50\text{--}150\,\text{ms}$ (según carga y modelo)
- Retardo de procesamiento MediaPipe: $\tau_{MP} \approx 15\text{--}30\,\text{ms}$ (modo IMAGE)

### 2.2 Modelo Dinámico Agregado

Para propósitos de control, la planta completa (incluyendo servo, transmisión y procesamiento de imagen) se modela como un sistema de **primer orden con retardo**:

$$G_p(s) = \frac{K_p}{\tau s + 1} e^{-sL}$$

donde:

- $K_p$: ganancia estática (adimensional, $\approx 1.0$ si el mapeo blendshape→ángulo es lineal)
- $\tau$: constante de tiempo agregada ($\approx 50\text{--}150\,\text{ms}$)
- $L$: retardo de transporte ($\tau_{tx} + \tau_{MP} \approx 20\text{--}50\,\text{ms}$)

### 2.3 Mapeo Blendshape → Ángulo

El puente entre el *blendshape* `jawOpen` (valor en $[0, 1]$) y el ángulo del servo se define en `robot_face_state.py`:

```python
SERVO_MAP    = {"jaw": "jawOpen"}
SERVO_RANGES = {"jaw": (0.0, 20.0)}   # (mín, máx) en grados
```

$$ \theta(t) = \theta_{\min} + s(t) \cdot (\theta_{\max} - \theta_{\min}) $$
$$ \theta(t) = 0 + s(t) \cdot 20^{\circ} $$

donde $s(t) \in [0, 1]$ es el blendshape `jawOpen` y $\theta(t)$ es el ángulo físico de la mandíbula.

---

## 3. Sensor / Observador

### 3.1 MediaPipe FaceLandmarker

```python
# robot_face_landmarks.py — RunningMode.IMAGE (síncrono)
result = self._detector.detect(mp_image)   # línea 41
```

A diferencia del Módulo 2 (que usa `LIVE_STREAM` con callback asíncrono), el Módulo 3 utiliza el modo `IMAGE`:

| Modo           | Llamada          | Threading      | Latencia |
|----------------|------------------|----------------|----------|
| `LIVE_STREAM`  | `detect_async()` | Callback thread| Variable  |
| `IMAGE`        | `detect()`       | Síncrono       | Predecible |

**Ventaja**: al ser síncrono, no hay condiciones de carrera al leer el resultado. El lazo de control lee ambas cámaras secuencialmente sin necesidad de *locks* ni variables compartidas.

### 3.2 Extracción de la Variable Medida

```python
# visual_feedback_controller.py:159-163
bs_a = result_a.get("blendshapes", {})
bs_b = result_b.get("blendshapes", {})
target_jaw   = bs_a.get("jawOpen", 0.0)
feedback_jaw = bs_b.get("jawOpen", 0.0)
```

$r(t)$ y $y(t)$ provienen del mismo extractor de *blendshapes* sobre frames diferentes, lo que elimina sesgos sistemáticos entre setpoint y medición.

---

## 4. Controlador PID

### 4.1 Forma Ideal (Continua)

$$ u(t) = K_p\, e(t) + K_i \int_0^{t} e(\tau)\,d\tau + K_d\, \frac{d}{dt}e(t) $$

$$ e(t) = r(t) - y(t) $$

### 4.2 Discretización (Tustin / Euler hacia atrás)

El controlador se implementa en tiempo discreto (`visual_feedback_controller.py:20-49`) con paso variable:

$$ t_k = \text{timestamp actual},\qquad \Delta t_k = t_k - t_{k-1} $$

$$ e_k = r_k - y_k $$

$$ I_k = I_{k-1} + e_k \cdot \Delta t_k $$

$$ D_k = \frac{e_k - e_{k-1}}{\Delta t_k} $$

$$ u_k = K_p\, e_k + K_i\, I_k + K_d\, D_k $$

con saturación:

$$ u_k^{\text{sat}} = \text{clamp}(u_k,\, u_{\min},\, u_{\max}) $$
$$ u_{\min} = 0.0^{\circ},\quad u_{\max} = 20.0^{\circ} $$

**Nota**: No se implementa *anti-windup* explícito. El término integral sigue acumulando incluso cuando la salida está saturada. Para la aplicación (mandíbula de robot animatrónico), el sobrepaso es aceptable y la saturación es poco frecuente porque el rango de operación normal $[0, 1]$ → $[0, 20]^{\circ}$ coincide con los límites.

### 4.3 Valores Nominales

| Parámetro | Valor  | Efecto                                    |
|-----------|--------|-------------------------------------------|
| $K_p$     | 0.80   | Respuesta proporcional, corrección inmediata |
| $K_i$     | 0.05   | Eliminación de error en estado estacionario  |
| $K_d$     | 0.10   | Amortiguamiento, reduce sobrepaso         |
| Período   | 30 Hz ($\approx 33\,\text{ms}$) | Limitado por MediaPipe + cámara |

### 4.4 Análisis Estabilidad

La función de transferencia del lazo cerrado (asumiendo $G_p(s) \approx \frac{1}{\tau s + 1}$ sin retardo para un análisis simplificado):

$$ C(s) = K_p + \frac{K_i}{s} + K_d s $$

$$ G_{LC}(s) = \frac{C(s) G_p(s)}{1 + C(s) G_p(s)} = \frac{K_d s^2 + K_p s + K_i}{\tau s^2 + (1 + K_d) s + K_p + \frac{K_i}{s}} $$

Para los valores nominales y $\tau \approx 0.1$:

$$ \text{Polos de lazo cerrado} \approx \text{estables (margen de fase > 45}^{\circ}) $$

El sistema es estable para variaciones razonables de $\tau$ y $L$ dado el período de muestreo lento (30 Hz) comparado con la dinámica del servo (50–150 ms).

---

## 5. Diagrama de Flujo del Lazo

```
                        ┌─────────┐
                        │ t = 0   │
                        └────┬────┘
                             │
                   ┌─────────▼─────────┐
                   │  cap_a.read()      │
                   │  frame_a           │
                   └─────────┬─────────┘
                             │
                   ┌─────────▼─────────┐
                   │  cap_b.read()      │
                   │  frame_b           │
                   └─────────┬─────────┘
                             │
            ┌────────────────▼────────────────┐
            │  result_a = detect(frame_a)      │  ← MediaPipe síncrono
            │  result_b = detect(frame_b)      │
            └────────────────┬────────────────┘
                             │
            ┌────────────────▼────────────────┐
            │  r = jawOpen_A  (blendshape)     │
            │  y = jawOpen_B  (blendshape)     │
            └────────────────┬────────────────┘
                             │
            ┌────────────────▼────────────────┐
            │  e = r - y                      │
            │  I += e * dt                    │
            │  D = (e - e_prev) / dt          │
            │  u = Kp*e + Ki*I + Kd*D         │
            │  u = clamp(u, 0, 20)            │
            └────────────────┬────────────────┘
                             │
            ┌────────────────▼────────────────┐
            │  send_serial(u)                  │  → " $5.32,0,0,0,0,0# "
            │  save_frame(frame_b)              │  → /stream/3
            │  (cada 10) stdout(feedback_state) │  → WebSocket
            └────────────────┬────────────────┘
                             │
                    ┌────────▼────────┐
                    │  sleep(33 ms)   │
                    │  t += 1         │
                    └────────┬────────┘
                             │
                   ┌─────────▼──────────┐
                   │  ¿ stop || error?   │─── Sí ──► cleanup ──► fin
                   └─────────┬──────────┘
                             │
                             ▼
                        (siguiente iteración)
```

---

## 6. Protocolo Serial

### 6.1 Trama de Salida (PC → Arduino)

```
$ jaw, smileL, smileR, blinkL, blinkR, yaw #
│  │     │       │       │       │       │
│  │     │       │       │       │       └── Delimitador fin
│  │     │       │       │       └────────── Yaw (no usado en PID)
│  │     │       │       └────────────────── Blink derecho
│  │     │       └────────────────────────── Blink izquierdo
│  │     └────────────────────────────────── Sonrisa derecha
│  └──────────────────────────────────────── Sonrisa izquierda
└─────────────────────────────────────────── Delimitador inicio
```

El Módulo 3 solo utiliza la posición `jaw`; los demás campos se envían como `0` pero están disponibles para expansión futura.

### 6.2 Tasa de Envío

Cada iteración del lazo (30 Hz aprox.), sin throttling adicional.

---

## 7. Limitaciones y Trabajo Futuro

### 7.1 Limitaciones Actuales

| Limitación | Impacto | Causa |
|-----------|---------|-------|
| Saturaciones sin *anti-windup* | Sobrepaso en cambios bruscos de setpoint | $I_k$ sigue acumulando durante saturación |
| Sin *feedforward* | Respuesta lenta a cambios de escena | $u_k$ depende solo del error |
| Sin modelo dinámico del servo | $K_p/K_i/K_d$ se sintonizan empíricamente | No hay identificación formal de $G_p(s)$ |
| Una sola variable controlada (jawOpen) | El resto de DOFs no tienen lazo cerrado | Complejidad del setup de calibración |
| Sin filtro en la medición | Ruido de MediaPipe pasa directo al término derivativo | $D_k$ amplifica variaciones entre frames |

### 7.2 Posibles Mejoras

$$ \text{ARW: } I_k = I_{k-1} + e_k \cdot \Delta t_k - \frac{1}{K_i K_{aw}} (u_k - u_k^{\text{sat}}) $$

1. **Anti-windup** con *back-calculation* (ecuación arriba)
2. **Feedforward** desde el setpoint: $u_k = K_{ff} \cdot r_k + \text{PID}(e_k)$
3. **Filtro pasa-bajos** en $y_k$: $\bar{y}_k = \alpha y_k + (1-\alpha) \bar{y}_{k-1}$ con $\alpha \in (0, 1)$
4. **Identificación en línea** de $\tau$ y $L$ mediante escalón
5. **Lazo cerrado multi-DOF** agregando los blendshapes adicionales (`browInnerUp`, `eyeBlinkLeft/Right`, `mouthSmileLeft/Right`, `yaw`)
6. **Control por *feedack linearization*** usando el modelo inverso de la cinemática del servo si se caracteriza su curva posición vs. PWM

---

## 8. Referencias

- MediaPipe Face Landmarker: https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker
- ARKit Blendshapes (52 coeficientes faciales): https://developer.apple.com/documentation/arkit/arfaceanchor/2926050-blendshapes
- Åström, K. J., & Murray, R. M. (2021). *Feedback Systems: An Introduction for Scientists and Engineers*. Princeton University Press.
- Åström, K. J., & Hägglund, T. (2006). *Advanced PID Control*. ISA.
