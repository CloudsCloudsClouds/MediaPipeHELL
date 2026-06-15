#!/usr/bin/env python3
"""
Wrapper de face_capture.py: captura frames para stream web.
Resistente a pipe roto (gesture_serial falla si el robot no está conectado).
face_capture.py NO se modifica.
"""
import os
import sys
import pathlib
import tempfile
import builtins
import cv2

_FRAME_FILE = pathlib.Path(tempfile.gettempdir()) / "tea_module2_frame.jpg"
_FRAME_TMP  = _FRAME_FILE.with_suffix('.tmp')
_PARAMS     = [cv2.IMWRITE_JPEG_QUALITY, 72]

# Interceptar imshow → guardar frame en archivo temporal
def _cap_imshow(winname, mat):
    try:
        ret, buf = cv2.imencode('.jpg', mat, _PARAMS)
        if ret:
            _FRAME_FILE.write_bytes(buf.tobytes())
    except Exception:
        pass

cv2.imshow            = _cap_imshow
cv2.waitKey           = lambda _=1: 0    # nunca retorna ESC → loop infinito
cv2.destroyAllWindows = lambda: None

# print() seguro: si el pipe se rompe (gesture_serial sale), seguimos corriendo
_orig_print = builtins.print
def _safe_print(*args, **kwargs):
    try:
        return _orig_print(*args, **kwargs)
    except (OSError, BrokenPipeError):
        pass

# Ejecutar face_capture.py en este proceso con print seguro
_src = (pathlib.Path(__file__).parent / "face_capture.py").read_text(encoding="utf-8")
exec(
    compile(_src, "face_capture.py", "exec"),
    {"__name__": "__main__", "__file__": "face_capture.py", "print": _safe_print},
)
