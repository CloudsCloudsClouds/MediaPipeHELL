@echo off
title Sistema TEA
echo.
echo  ====================================================
echo    Sistema TEA - Iniciando...
echo  ====================================================
echo.

cd /d "%~dp0"

echo  [1/2] Iniciando backend Python (puerto 8000)...
start "TEA Backend" cmd /k ".venv\Scripts\python.exe server.py"

echo  Esperando que el backend arranque...
timeout /t 4 /nobreak >nul

echo  [2/2] Iniciando frontend React (puerto 5173)...
start "TEA Frontend" cmd /k "cd web && npm run dev"

echo.
echo  ====================================================
echo    Abre en el navegador: http://localhost:5173
echo  ====================================================
echo.
pause
