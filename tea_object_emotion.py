#!/usr/bin/env python3
"""
tea_emociones_completo.py - Reconocimiento de objetos con YOLO
Con VOZ FUNCIONAL, SIN REPETICIONES, y con ENTRENAMIENTO PERSONALIZADO para ENOJO
"""

from ultralytics import YOLO
import cv2
import json
import time
import serial
import numpy as np
import threading
import queue
import os
import yaml
from pathlib import Path

# ==================== CONFIGURACIÓN ====================
SERIAL_PORT = "/dev/ttyUSB0"  # Cambia a "COM3" en Windows
BAUD_RATE = 9600

# Umbral de confianza para detección
CONFIANZA_MINIMA = 0.25

# Resolución de cámara
ANCHO_CAMARA = 1280
ALTO_CAMARA = 720

# ==================== MAPEO DE OBJETOS A EMOCIONES ====================
OBJETOS_CONFIG = {

    # ===== ENOJO (objetos que generan enojo - se pueden entrenar) =====
    "battery": {
        "emocion": "enojo",
        "gesto_brazo": "DESAPRUEBO",
        "frase": "¡Las pilas usadas contaminan! Me enoja que no las reciclen",
        "color": (255, 100, 0)
    },
    "broken_glass": {
        "emocion": "enojo",
        "gesto_brazo": "DESAPRUEBO",
        "frase": "¡Vidrio roto! Qué peligroso e irresponsable",
        "color": (255, 50, 0)
    },
    "trash": {
        "emocion": "enojo",
        "gesto_brazo": "DESAPRUEBO",
        "frase": "¡Qué feo! La basura debe ir al bote",
        "color": (255, 100, 0)
    },
    
    # ===== PELIGROSOS → MIEDO =====
    "knife": {
        "emocion": "miedo",
        "gesto_brazo": "DESAPRUEBO",
        "frase": "¡Cuidado! Un cuchillo es muy peligroso",
        "color": (0, 0, 255)
    },
    "scissors": {
        "emocion": "miedo",
        "gesto_brazo": "DESAPRUEBO",
        "frase": "Ten cuidado con las tijeras, pueden cortar",
        "color": (0, 0, 255)
    },
    "hammer": {
        "emocion": "miedo",
        "gesto_brazo": "DESAPRUEBO",
        "frase": "Un martillo puede lastimar si no se usa bien",
        "color": (0, 0, 255)
    },
    "saw": {
        "emocion": "miedo",
        "gesto_brazo": "DESAPRUEBO",
        "frase": "¡Qué peligro! Una sierra es muy filosa",
        "color": (0, 0, 255)
    },
    "gun": {
        "emocion": "miedo",
        "gesto_brazo": "DESAPRUEBO",
        "frase": "Las armas son muy peligrosas",
        "color": (0, 0, 255)
    },
    
    # ===== OBJETOS SORPRENDENTES → ASOMBRO =====
    "clock": {
        "emocion": "asombro",
        "gesto_brazo": "CHECK",
        "frase": "¡Mira! Un reloj. El tiempo es importante",
        "color": (255, 0, 255)
    },
    "vase": {
        "emocion": "asombro",
        "gesto_brazo": "CHECK",
        "frase": "¡Qué bonito florero! Me sorprende su belleza",
        "color": (255, 0, 255)
    },
    "cake": {
        "emocion": "asombro",
        "gesto_brazo": "CHECK",
        "frase": "¡Wow! Un pastel, qué sorpresa más deliciosa",
        "color": (255, 0, 255)
    },
    "balloon": {
        "emocion": "asombro",
        "gesto_brazo": "CHECK",
        "frase": "¡Oh! Un globo de colores, qué sorpresa",
        "color": (255, 0, 255)
    },
    "gift": {
        "emocion": "asombro",
        "gesto_brazo": "CHECK",
        "frase": "¡Qué emoción! Un regalo sorpresa",
        "color": (255, 0, 255)
    },
    
    # ===== OBJETOS BUENOS → FELIZ =====
    "book": {
        "emocion": "feliz",
        "gesto_brazo": "CHECK",
        "frase": "¡Qué bien! Leer es divertido",
        "color": (0, 255, 0)
    },
    "notebook": {
        "emocion": "feliz",
        "gesto_brazo": "CHECK",
        "frase": "Un cuaderno para dibujar, ¡me gusta!",
        "color": (0, 255, 0)
    },
    "laptop": {
        "emocion": "feliz",
        "gesto_brazo": "CHECK",
        "frase": "Computadora, podemos aprender jugando",
        "color": (0, 255, 0)
    },
    "cell phone": {
        "emocion": "feliz",
        "gesto_brazo": "CHECK",
        "frase": "Un teléfono para comunicarnos",
        "color": (0, 255, 0)
    },
    "remote": {
        "emocion": "feliz",
        "gesto_brazo": "CHECK",
        "frase": "El control remoto, podemos ver dibujos",
        "color": (0, 255, 0)
    },
    "pen": {
        "emocion": "feliz",
        "gesto_brazo": "CHECK",
        "frase": "Un lápiz para escribir",
        "color": (0, 255, 0)
    },
    "pencil": {
        "emocion": "feliz",
        "gesto_brazo": "CHECK",
        "frase": "Lápiz para dibujar",
        "color": (0, 255, 0)
    },
    
    # ===== COMIDA → FELIZ =====
    "apple": {
        "emocion": "feliz",
        "gesto_brazo": "CHECK",
        "frase": "Una manzana, qué rica y saludable",
        "color": (0, 255, 0)
    },
    "banana": {
        "emocion": "feliz",
        "gesto_brazo": "CHECK",
        "frase": "Plátano, lleno de energía",
        "color": (0, 255, 0)
    },
    "orange": {
        "emocion": "feliz",
        "gesto_brazo": "CHECK",
        "frase": "Naranja, llena de vitamina C",
        "color": (0, 255, 0)
    },
    "carrot": {
        "emocion": "feliz",
        "gesto_brazo": "CHECK",
        "frase": "Zanahoria, buena para la vista",
        "color": (0, 255, 0)
    },
    
    # ===== NEUTROS =====
    "bottle": {
        "emocion": "neutral",
        "gesto_brazo": "CHECK",
        "frase": "Una botella de agua",
        "color": (255, 255, 0)
    },
    "cup": {
        "emocion": "neutral",
        "gesto_brazo": "CHECK",
        "frase": "Un vaso para beber",
        "color": (255, 255, 0)
    },
    "spoon": {
        "emocion": "neutral",
        "gesto_brazo": "CHECK",
        "frase": "Una cuchara",
        "color": (255, 255, 0)
    },
    "fork": {
        "emocion": "neutral",
        "gesto_brazo": "CHECK",
        "frase": "Un tenedor",
        "color": (255, 255, 0)
    },
    
    # ===== JUGUETES → FELIZ =====
    "ball": {
        "emocion": "feliz",
        "gesto_brazo": "CHECK",
        "frase": "¡Una pelota! Podemos jugar",
        "color": (0, 255, 0)
    },
    "teddy bear": {
        "emocion": "feliz",
        "gesto_brazo": "CHECK",
        "frase": "Un peluche, qué suavecito",
        "color": (0, 255, 0)
    },
    "toy": {
        "emocion": "feliz",
        "gesto_brazo": "CHECK",
        "frase": "Un juguete para divertirnos",
        "color": (0, 255, 0)
    }
}

# Mapeo de emociones a gestos de cara
EMOCION_A_GESTO_CARA = {
    "feliz": 10,
    "asombro": 9,
    "miedo": 9,
    "enojo": 8,
    "triste": 7,
    "neutral": 0
}

# ==================== CLASE PARA ENTRENAMIENTO PERSONALIZADO ====================

class EntrenadorPersonalizado:
    """Gestiona la captura y entrenamiento de nuevos objetos (pilas, vidrio roto)"""
    
    def __init__(self):
        self.dataset_path = Path("mi_dataset_enojo")
        self.modelo_base = "yolo11s.pt"
        self._crear_estructura()
        
    def _crear_estructura(self):
        for split in ["train", "val"]:
            (self.dataset_path / split / "images").mkdir(parents=True, exist_ok=True)
            (self.dataset_path / split / "labels").mkdir(parents=True, exist_ok=True)
    
    def capturar_objeto(self, frame, nombre_objeto, bbox):
        """Captura un objeto para entrenamiento"""
        if bbox is None:
            return False
        
        x1, y1, x2, y2 = map(int, bbox)
        h, w = frame.shape[:2]
        
        # Calcular coordenadas YOLO
        x_center = ((x1 + x2) / 2) / w
        y_center = ((y1 + y2) / 2) / h
        width = (x2 - x1) / w
        height = (y2 - y1) / h
        
        # Mapeo de clases
        clases = {"bateria": 0, "vidrio_roto": 1, "basura": 2, "objeto_roto": 3}
        clase_id = clases.get(nombre_objeto, 0)
        
        timestamp = int(time.time() * 1000)
        nombre = f"{nombre_objeto}_{timestamp}"
        
        # 80% train, 20% val
        import random
        split = "train" if random.random() < 0.8 else "val"
        
        img_path = self.dataset_path / split / "images" / f"{nombre}.jpg"
        label_path = self.dataset_path / split / "labels" / f"{nombre}.txt"
        
        cv2.imwrite(str(img_path), frame)
        with open(label_path, "w") as f:
            f.write(f"{clase_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}")
        
        print(f"📸 Capturada {nombre} para {split}")
        return True
    
    def entrenar(self, epochs=50):
        """Entrena el modelo personalizado"""
        train_images = list((self.dataset_path / "train" / "images").glob("*.jpg"))
        if len(train_images) < 10:
            print(f"❌ Solo {len(train_images)} imágenes. Necesitas al menos 10 para entrenar.")
            return None
        
        print("🚀 Iniciando entrenamiento personalizado...")
        print(f"   📊 Imágenes: {len(train_images)}")
        print(f"   ⏱️  Esto tomará varios minutos...")
        
        # Crear data.yaml
        data_yaml = {
            'path': str(self.dataset_path.absolute()),
            'train': 'train/images',
            'val': 'val/images',
            'nc': 4,
            'names': ['bateria', 'vidrio_roto', 'basura', 'objeto_roto']
        }
        
        with open(self.dataset_path / 'data.yaml', 'w') as f:
            yaml.dump(data_yaml, f)
        
        # Entrenar
        model = YOLO(self.modelo_base)
        resultados = model.train(
            data=str(self.dataset_path / 'data.yaml'),
            epochs=epochs,
            imgsz=640,
            batch=8,
            device='cpu',
            patience=10,
            lr0=0.01,
            augment=True,
            verbose=True
        )
        
        model.save("modelo_enojo_personalizado.pt")
        print("✅ Modelo personalizado guardado como 'modelo_enojo_personalizado.pt'")
        return model

# ==================== DETECTOR CON MÚLTIPLES MODELOS ====================

class DetectorYOLOConEnojo:
    """Detector que usa modelo estándar + modelo personalizado para enojo"""
    
    def __init__(self, modelo="yolo11s.pt"):
        print(f"📦 Cargando modelo estándar: {modelo}")
        self.modelo_std = YOLO(modelo)
        
        self.modelo_enojo = None
        if os.path.exists("modelo_enojo_personalizado.pt"):
            print("📦 Cargando modelo personalizado (detecta objetos de ENOJO)...")
            self.modelo_enojo = YOLO("modelo_enojo_personalizado.pt")
        else:
            print("⚠️ Modelo personalizado no encontrado. Usa 't' para entrenar.")
        
        print(f"✅ Modelos listos. Clases estándar: {len(self.modelo_std.names)}")
    
    def detectar(self, frame):
        """Detecta objetos usando ambos modelos"""
        objetos_detectados = []
        
        # Detectar con modelo estándar
        resultados_std = self.modelo_std(frame, conf=CONFIANZA_MINIMA, iou=0.45, verbose=False)
        
        for r in resultados_std:
            if r.boxes:
                for box in r.boxes:
                    clase_id = int(box.cls[0])
                    nombre = self.modelo_std.names[clase_id]
                    confianza = float(box.conf[0])
                    bbox = box.xyxy[0].tolist()
                    
                    if nombre in OBJETOS_CONFIG:
                        objetos_detectados.append({
                            "nombre": nombre,
                            "confianza": confianza,
                            "bbox": bbox,
                            "info": OBJETOS_CONFIG[nombre]
                        })
                        if confianza > 0.3:
                            print(f"   🔍 Detectado: {nombre} ({confianza:.0%})")
        
        # Detectar con modelo personalizado (para enojo)
        if self.modelo_enojo:
            resultados_enojo = self.modelo_enojo(frame, conf=CONFIANZA_MINIMA, iou=0.45, verbose=False)
            
            # Mapeo para modelo personalizado
            emociones_personalizadas = {
                "bateria": {"emocion": "enojo", "gesto_brazo": "DESAPRUEBO",
                           "frase": "¡Las pilas usadas contaminan! Me enoja que no las reciclen",
                           "color": (255, 100, 0)},
                "vidrio_roto": {"emocion": "enojo", "gesto_brazo": "DESAPRUEBO",
                               "frase": "¡Vidrio roto! Qué peligroso e irresponsable",
                               "color": (255, 50, 0)},
                "basura": {"emocion": "enojo", "gesto_brazo": "DESAPRUEBO",
                          "frase": "¡La basura debe ir al bote! Me molesta",
                          "color": (255, 80, 0)},
                "objeto_roto": {"emocion": "enojo", "gesto_brazo": "DESAPRUEBO",
                               "frase": "Algo roto... qué fastidio",
                               "color": (255, 60, 0)}
            }
            
            for r in resultados_enojo:
                if r.boxes:
                    for box in r.boxes:
                        clase_id = int(box.cls[0])
                        nombres_personalizados = {0: "bateria", 1: "vidrio_roto", 2: "basura", 3: "objeto_roto"}
                        nombre = nombres_personalizados.get(clase_id, f"clase_{clase_id}")
                        confianza = float(box.conf[0])
                        bbox = box.xyxy[0].tolist()
                        
                        if nombre in emociones_personalizadas:
                            objetos_detectados.append({
                                "nombre": nombre,
                                "confianza": confianza,
                                "bbox": bbox,
                                "info": emociones_personalizadas[nombre]
                            })
                            if confianza > 0.3:
                                print(f"   🔍 Detectado (ENOJO): {nombre} ({confianza:.0%})")
        
        return objetos_detectados

# ==================== MOTOR DE VOZ ====================

class MotorVoz:
    _instance = None
    _speaker = None
    _cola_frases = queue.Queue()
    _hilo_activo = False
    _hilo = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._inicializar()
        return cls._instance
    
    def _inicializar(self):
        try:
            import win32com.client
            self._speaker = win32com.client.Dispatch("SAPI.SpVoice")
            self._speaker.Rate = 0
            self._speaker.Volume = 100
            print("🔊 Motor de voz (win32com) inicializado correctamente")
        except ImportError:
            print("⚠️ pip install pywin32")
            self._speaker = None
        except Exception as e:
            print(f"⚠️ Error inicializando voz: {e}")
            self._speaker = None
    
    def hablar(self, frase, es_nuevo_objeto=True):
        if self._speaker is None:
            print(f"🔊 (simulación): {frase}")
            return
        
        if es_nuevo_objeto:
            while not self._cola_frases.empty():
                try:
                    self._cola_frases.get_nowait()
                except queue.Empty:
                    break
        
        self._cola_frases.put(frase)
        
        if not self._hilo_activo:
            self._hilo_activo = True
            self._hilo = threading.Thread(target=self._procesar_cola, daemon=True)
            self._hilo.start()
    
    def _procesar_cola(self):
        while self._hilo_activo:
            try:
                frase = self._cola_frases.get(timeout=0.5)
                if frase and self._speaker:
                    print(f"🔊 ROBOT: \"{frase}\"")
                    self._speaker.Speak(frase)
                self._cola_frases.task_done()
            except queue.Empty:
                self._hilo_activo = False
                break
            except Exception as e:
                print(f"⚠️ Error en voz: {e}")
                self._hilo_activo = False
                break

# ==================== CLASE ROBOT ====================

class RobotTEA:
    def __init__(self, puerto_serial=None):
        self.ser = None
        self.ultimo_objeto = None
        self.ultimo_tiempo = 0
        self.cooldown = 2.0
        self.voz = MotorVoz()
        
        if puerto_serial and puerto_serial != "None":
            try:
                self.ser = serial.Serial(puerto_serial, BAUD_RATE, timeout=0.5)
                print(f"✅ Robot conectado en {puerto_serial}")
            except:
                print(f"⚠️ No se pudo conectar al robot - modo simulación")
    
    def reaccionar(self, objeto, confianza, info):
        ahora = time.time()
        es_nuevo_objeto = (objeto != self.ultimo_objeto)
        
        if not es_nuevo_objeto and (ahora - self.ultimo_tiempo) < self.cooldown:
            return
        
        self.ultimo_objeto = objeto
        self.ultimo_tiempo = ahora
        
        print("\n" + "="*60)
        print(f"📦 Objeto: {objeto} (confianza: {confianza:.0%})")
        print(f"😊 Emoción: {info['emocion']}")
        print(f"🦾 Gesto brazo: {info['gesto_brazo']}")
        print(f"💬 \"{info['frase']}\"")
        print("="*60)
        
        self._gesto_brazo(info['gesto_brazo'])
        self._expresion_cara(info['emocion'])
        self.voz.hablar(info['frase'], es_nuevo_objeto)
    
    def _gesto_brazo(self, gesto):
        comandos = {"CHECK": "OK\n", "DESAPRUEBO": "NO\n"}
        cmd = comandos.get(gesto, "OK\n")
        
        if self.ser:
            self.ser.write(cmd.encode())
            print(f"🦾 BRAZO: {gesto} (enviado: {cmd.strip()})")
        else:
            if gesto == "CHECK":
                print("🦾 [SIMULACIÓN] BRAZO hace: ✅ CHECK")
            else:
                print("🦾 [SIMULACIÓN] BRAZO hace: ❌ DESAPRUEBO")
    
    def _expresion_cara(self, emocion):
        gesture_id = EMOCION_A_GESTO_CARA.get(emocion, 0)
        salida = json.dumps({"gesture": gesture_id, "emocion": emocion, "source": "objeto"})
        print(f"😊 CARA: {emocion} (gesto {gesture_id})")
        print(f"   Enviado: {salida}")
        
        if self.ser:
            self.ser.write(f"F{gesture_id}\n".encode())

# ==================== PROGRAMA PRINCIPAL ====================

def main():
    global CONFIANZA_MINIMA
    print("="*60)
    print("🧠 SISTEMA TEA - TEORÍA DE LA MENTE 🧠")
    print("="*60)
    print("""
    CONTROLES:
    - 'c' : Capturar objeto de ENOJO (pila, vidrio roto) para entrenamiento
    - 't' : Entrenar modelo personalizado (después de capturar 10-20 imágenes)
    - '+' : Aumentar confianza
    - '-' : Disminuir confianza
    - 'q' : Salir
    
    PARA DETECTAR PILAS/VIDRIO ROTO COMO ENOJO:
    1. Coloca una pila frente a la cámara
    2. Presiona 'c' y luego ESPACIO para capturarla (hazlo 10-20 veces)
    3. Presiona 't' para entrenar (toma 5-10 minutos)
    4. ¡Listo! Ahora detecta pilas como ENOJO
    """)
    
    # Inicializar detector (con soporte para modelo personalizado)
    detector = DetectorYOLOConEnojo("yolo11s.pt")
    
    # Inicializar robot
    robot = RobotTEA(SERIAL_PORT)
    
    # Inicializar entrenador
    entrenador = EntrenadorPersonalizado()
    
    # Configurar cámara
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, ANCHO_CAMARA)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, ALTO_CAMARA)
    
    if not cap.isOpened():
        print("❌ No se pudo abrir la cámara")
        return
    
    print(f"\n🎥 Cámara configurada a {ANCHO_CAMARA}x{ALTO_CAMARA}")
    print(f"🎯 Umbral de confianza: {CONFIANZA_MINIMA*100:.0f}%")
    print(f"⏱️  Cooldown entre objetos: {robot.cooldown} segundos")
    print("\n👉 Acerca un objeto a la cámara\n")
    
    # Variables para control de repeticiones
    ultimo_objeto_procesado = None
    ultimo_tiempo_procesado = 0
    modo_captura = False
    objeto_actual_captura = "bateria"
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        frame = cv2.flip(frame, 1)
        
        # Modo captura para entrenamiento
        if modo_captura:
            cv2.putText(frame, f"MODO CAPTURA - {objeto_actual_captura.upper()}", 
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            cv2.putText(frame, "Presiona ESPACIO para capturar, ESC para salir", 
                       (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            cv2.imshow("TEA - Modo Captura", frame)
            
            key_cap = cv2.waitKey(1) & 0xFF
            if key_cap == 32:  # ESPACIO
                # Usar detección automática para obtener el bbox
                detecciones = detector.detectar(frame)
                if detecciones:
                    mejor = max(detecciones, key=lambda x: x['confianza'])
                    bbox = mejor['bbox']
                    entrenador.capturar_objeto(frame, objeto_actual_captura, bbox)
                    print(f"   ✅ Capturada imagen para {objeto_actual_captura}")
                else:
                    print("   ⚠️ No se detectó ningún objeto. Coloca el objeto frente a la cámara")
            elif key_cap == 27:  # ESC
                modo_captura = False
                print("📸 Modo captura desactivado")
                cv2.destroyWindow("TEA - Modo Captura")
            continue
        
        # Modo normal - detectar objetos
        objetos = detector.detectar(frame)
        
        if objetos:
            mejor = max(objetos, key=lambda x: x['confianza'])
            nombre = mejor['nombre']
            confianza = mejor['confianza']
            info = mejor['info']
            bbox = mejor['bbox']
            ahora = time.time()
            
            # Dibujar bounding box
            x1, y1, x2, y2 = map(int, bbox)
            color = info['color']
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)
            
            etiqueta = f"{nombre} → {info['emocion']} ({confianza:.0%})"
            cv2.putText(frame, etiqueta, (x1, y1-10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            
            # Reaccionar si es nuevo objeto o pasó el tiempo
            if (nombre != ultimo_objeto_procesado) or (ahora - ultimo_tiempo_procesado > 2.0):
                ultimo_objeto_procesado = nombre
                ultimo_tiempo_procesado = ahora
                robot.reaccionar(nombre, confianza, info)
        
        # Mostrar información en pantalla
        cv2.putText(frame, f"Cooldown: {robot.cooldown}s | Conf: {CONFIANZA_MINIMA*100:.0f}%", 
                   (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.putText(frame, "c:Capturar | t:Entrenar | q:Salir", 
                   (10, frame.shape[0]-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        
        cv2.imshow("TEA - Reconocimiento de Objetos y Emociones", frame)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('c'):
            modo_captura = True
            print("\n📸 MODO CAPTURA ACTIVADO")
            print("   Coloca el objeto (pila, vidrio roto) frente a la cámara")
            print("   Presiona ESPACIO para capturar, ESC para salir")
        elif key == ord('t'):
            print("\n🚀 Iniciando entrenamiento personalizado...")
            modelo = entrenador.entrenar(epochs=30)
            if modelo:
                print("\n✅ Entrenamiento completado!")
                print("   Reinicia el programa para usar el nuevo modelo")
                print("   Ahora las pilas y vidrio roto generarán la emoción de ENOJO")
            else:
                print("   ❌ No hay suficientes imágenes. Captura más con 'c'")
        elif key == ord('+') or key == ord('='):
            CONFIANZA_MINIMA = min(0.9, CONFIANZA_MINIMA + 0.05)
            print(f"🔧 Umbral de confianza: {CONFIANZA_MINIMA*100:.0f}%")
        elif key == ord('-'):
            CONFIANZA_MINIMA = max(0.1, CONFIANZA_MINIMA - 0.05)
            print(f"🔧 Umbral de confianza: {CONFIANZA_MINIMA*100:.0f}%")
    
    cap.release()
    cv2.destroyAllWindows()
    if robot.ser:
        robot.ser.close()
    print("\n👋 Programa terminado")

if __name__ == "__main__":
    main()