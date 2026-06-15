<#
.SYNOPSIS
    TEA System — PowerShell build/run helper
    Equivalente al Makefile para usuarios de Windows.
.DESCRIPTION
    Uso: .\make.ps1 <target> [-ARGS "..."] [-SERIAL_PORT COM6]
    Ejemplos:
        .\make.ps1 help
        .\make.ps1 server
        .\make.ps1 feedback -ARGS "--camera-a 2 --camera-b 3"
        .\make.ps1 face-gesture -SERIAL_PORT COM6
#>

param(
    [Parameter(Position = 0)]
    [string]$Target = "help",

    [Parameter()]
    [string]$ARGS = "",

    [Parameter()]
    [string]$SERIAL_PORT = "COM6"
)

$ErrorActionPreference = "Stop"
$PY = "uv run python"

# ── Verificar entorno ─────────────────────────────────
function Assert-UVReady {
    if (-not (Get-Command "uv" -ErrorAction SilentlyContinue)) {
        Write-Host "ERROR: 'uv' no encontrado. Instala https://docs.astral.sh/uv/" -ForegroundColor Red
        exit 1
    }
    if (-not (Test-Path ".venv")) {
        Write-Host "ERROR: .venv no encontrado. Ejecuta 'uv sync' primero." -ForegroundColor Red
        exit 1
    }
}

function Exec {
    param([string]$Command)
    Write-Host "> $Command" -ForegroundColor Cyan
    Invoke-Expression $Command
    if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Codigo de salida $LASTEXITCODE" -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

function Show-Help {
    Write-Host @'

Uso: .\make.ps1 <target> [-ARGS "..."] [-SERIAL_PORT COM6]

── Servidor ──
  server            Inicia backend FastAPI (todos los modulos)

── Web ──
  web               Inicia frontend de desarrollo (Vite)
  web-build         Compila frontend para produccion

── Modulo 1 — Reconocimiento de Objetos ──
  mod1              Objetos + emociones + robot

── Modulo 2 — Reaccion Duplicada ──
  mod2              Pipeline completo (cara → gesto → serial)
  face-gesture      face_capture | classify_gesture | gesture_serial
  face-stream       face_capture | set_directions | serial_bridge

── Modulo 2 — Pose ──
  pose-gesture      pose_capture | classify_gesture | gesture_serial
  pose-stream       pose_capture | set_directions | serial_bridge

── Modulo 3 — Lazo Cerrado (PID) ──
  feedback          PID con 2 camaras (valores por defecto)
  feedback-cam      PID con indices de camara explicitos
  feedback-tune     PID con ganancias custom

── Utilidades ──
  classify          Solo clasificador (pipe stdin → stdout)
  bridge            serial_bridge standalone
  test-pipeline     Genera datos de prueba para el pipeline
  clean             Limpia capturas, frames temporales, caches
  help              Muestra esta ayuda

Flags:
  -ARGS "..."       Argumentos extra para el script
  -SERIAL_PORT      Puerto serial (def: COM6)

Ejemplos:
  .\make.ps1 feedback -ARGS "--camera-a 2 --camera-b 3"
  .\make.ps1 face-gesture -SERIAL_PORT COM3
  .\make.ps1 mod2
'@
}

# ── Targets ───────────────────────────────────────────
switch ($Target) {
    "help" {
        Show-Help
    }

    "server" {
        Assert-UVReady
        Exec "$PY server.py $ARGS"
    }

    "web" {
        Push-Location web
        npm run dev
        Pop-Location
    }

    "web-build" {
        Push-Location web
        npm run build
        Pop-Location
    }

    "mod1" {
        Assert-UVReady
        Write-Host "Iniciando backend. Abre http://localhost:8000 y selecciona 'Reconocimiento de Objetos'." -ForegroundColor Yellow
        Exec "$PY server.py $ARGS"
    }

    "mod2" {
        Assert-UVReady
        Exec "$PY run_face_capture.py | $PY classify_gesture.py | $PY gesture_serial.py $ARGS"
    }

    "face-gesture" {
        Assert-UVReady
        Exec "$PY face_capture.py | $PY classify_gesture.py | $PY gesture_serial.py $ARGS"
    }

    "face-stream" {
        Assert-UVReady
        Exec "$PY face_capture.py | $PY set_directions.py | $PY serial_bridge.py $ARGS"
    }

    "pose-gesture" {
        Assert-UVReady
        Exec "$PY pose_capture.py | $PY classify_gesture.py | $PY gesture_serial.py $ARGS"
    }

    "pose-stream" {
        Assert-UVReady
        Exec "$PY pose_capture.py | $PY set_directions.py | $PY serial_bridge.py $ARGS"
    }

    "feedback" {
        Assert-UVReady
        Exec "$PY visual_feedback_controller.py $ARGS"
    }

    "feedback-cam" {
        Assert-UVReady
        Exec "$PY visual_feedback_controller.py --camera-a 0 --camera-b 1 $ARGS"
    }

    "feedback-tune" {
        Assert-UVReady
        Exec "$PY visual_feedback_controller.py --kp 0.8 --ki 0.05 --kd 0.1 $ARGS"
    }

    "classify" {
        Assert-UVReady
        Exec "$PY classify_gesture.py"
    }

    "bridge" {
        Assert-UVReady
        Exec "$PY serial_bridge.py"
    }

    "test-pipeline" {
        Assert-UVReady
        Exec "$PY test_pipeline.py"
    }

    "clean" {
        if (Test-Path "captures") { Remove-Item -Recurse -Force "captures" }
        Get-ChildItem "/tmp/tea_module*_frame.jpg" -ErrorAction SilentlyContinue | Remove-Item -Force
        Get-ChildItem "/tmp/tea_module*_frame.tmp" -ErrorAction SilentlyContinue | Remove-Item -Force
        if (Test-Path "web/dist") { Remove-Item -Recurse -Force "web/dist" }
        Get-ChildItem -Recurse -Directory "__pycache__" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
        Write-Host "Limpieza completada." -ForegroundColor Green
    }

    default {
        Write-Host "Target desconocido: '$Target'. Ejecuta '.\make.ps1 help'." -ForegroundColor Red
        exit 1
    }
}
