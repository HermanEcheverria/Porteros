"""
Deteccion de la bola con un modelo ya entrenado (YOLO11 de Ultralytics, dataset COCO).
COCO ya trae la clase 32 = "sports ball", asi que no hay que entrenar nada.

Teclas (ventana de video activa):
  Z = detectar la cancha blanca sola     M = marcarla a mano con 2 clics
  C = cambiar de camara    + / - = confianza minima    Esc = salir
"""
import time
import cv2
from ultralytics import YOLO

MODELO = "yolo11n.pt"     # se descarga solo la primera vez (~5 MB)
CLASE_BOLA = 32           # "sports ball" en COCO
TAM = 960                 # tamano de entrada del modelo
conf_min = 0.15

zona, marcando, esperando_zona = None, [], False


def al_clic(ev, x, y, flags, p):
    global zona, esperando_zona
    if ev == cv2.EVENT_LBUTTONDOWN and esperando_zona:
        marcando.append((x, y))
        if len(marcando) == 2:
            (x1, y1), (x2, y2) = marcando
            zona = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
            marcando.clear(); esperando_zona = False
            print("Cancha marcada:", zona)


def cancha_automatica(frame):
    """Busca la zona blanca mas grande (la cancha) y devuelve su rectangulo."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    blanco = cv2.inRange(hsv, (0, 0, 170), (179, 65, 255))
    k = (frame.shape[1] // 23) | 1      # borra lo blanco delgado (rieles, cables, mesa)
    blanco = cv2.morphologyEx(blanco, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    cs, _ = cv2.findContours(blanco, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cs:
        return None
    x, y, w, h = cv2.boundingRect(max(cs, key=cv2.contourArea))
    return (x, y, x + w, y + h)


def abrir(i):
    cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280); cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    return cap


def main():
    global conf_min, esperando_zona, zona
    print("Cargando modelo...")
    modelo = YOLO(MODELO)
    cam = 0; cap = abrir(cam)
    cv2.namedWindow("Bola YOLO", cv2.WINDOW_NORMAL)
    cv2.setMouseCallback("Bola YOLO", al_clic)
    previo, t_prev, fps = None, time.time(), 0.0

    while True:
        ok, frame = cap.read()
        if not ok:
            print("No llega imagen de la camara", cam); time.sleep(0.5); continue
        h, w = frame.shape[:2]

        ox, oy = (zona[0], zona[1]) if zona else (0, 0)
        recorte = frame[zona[1]:zona[3], zona[0]:zona[2]] if zona else frame   # solo la cancha: la bola se ve mas grande
        r = modelo.predict(recorte, classes=[CLASE_BOLA], conf=conf_min, imgsz=TAM, verbose=False)[0]
        mejor = None
        for b in r.boxes:
            x1, y1, x2, y2 = map(int, b.xyxy[0]); c = float(b.conf[0])
            x1, x2, y1, y2 = x1 + ox, x2 + ox, y1 + oy, y2 + oy
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            if zona and not (zona[0] <= cx <= zona[2] and zona[1] <= cy <= zona[3]):
                continue
            if mejor is None or c > mejor[4]:
                mejor = (x1, y1, x2, y2, c, cx, cy)

        ahora = time.time(); dt = ahora - t_prev; t_prev = ahora
        fps = 0.9 * fps + 0.1 * (1 / dt if dt > 0 else 0)

        texto = "Z = detectar cancha | buscando bola..."
        if esperando_zona:
            texto = "Clic en esquina " + ("superior izquierda" if not marcando else "inferior derecha")
        if zona:
            cv2.rectangle(frame, zona[:2], zona[2:], (255, 200, 0), 2)
        if mejor:
            x1, y1, x2, y2, c, cx, cy = mejor
            vx = vy = 0
            if previo and dt > 0:
                vx, vy = (cx - previo[0]) / dt, (cy - previo[1]) / dt
            previo = (cx, cy)
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 3)
            cv2.circle(frame, (cx, cy), 4, (0, 0, 255), -1)
            cv2.arrowedLine(frame, (cx, cy), (int(cx + vx * 0.3), int(cy + vy * 0.3)), (0, 0, 255), 2)
            texto = f"Bola x={100*cx/w:5.1f}%  y={100*cy/h:5.1f}%  conf={c:.2f}  vel=({vx:5.0f},{vy:5.0f}) px/s"
        else:
            previo = None

        cv2.rectangle(frame, (0, h - 40), (w, h), (0, 0, 0), -1)
        cv2.putText(frame, f"{texto} | {fps:4.1f} fps | conf min {conf_min:.2f}", (10, h - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.imshow("Bola YOLO", frame)

        k = cv2.waitKey(1) & 0xFF
        if k == 27: break
        if k in (ord('z'), ord('Z')):
            zona = cancha_automatica(frame); print("Cancha detectada sola:", zona)
        if k in (ord('m'), ord('M')): esperando_zona, zona = True, None; marcando.clear()
        if k in (ord('c'), ord('C')):
            cap.release(); cam = (cam + 1) % 5; cap = abrir(cam); print("Camara", cam)
        if k == ord('+'): conf_min = min(0.9, conf_min + 0.05)
        if k == ord('-'): conf_min = max(0.05, conf_min - 0.05)

    cap.release(); cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
