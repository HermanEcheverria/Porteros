"""
Prueba de vision — Porteros Robot
Usa la camara del iPhone (iVCam) para encontrar la bola por su color.

Como usarlo:
  1. Abre iVCam en el iPhone y en la PC (deben verse conectados).
  2. Ejecuta iniciar_vision.bat
  3. Haz CLIC sobre la bola en la ventana: el programa aprende su color.
  4. Mueve la bola: un circulo verde la sigue y se muestra su posicion y velocidad.

Teclas (con la ventana de video activa):
  Z = marcar la cancha: luego clic en la esquina superior izquierda y en la inferior derecha
  B = bola blanca y negra (busca las manchas negras en vez del color)
  C = cambiar de camara      R = olvidar el color / modo      Esc = salir
"""
import sys
import time

try:
    import cv2
    import numpy as np
except ImportError:
    print("Faltan librerias. Ejecuta: py -3 -m pip install opencv-python numpy")
    input("Presiona Enter para salir...")
    sys.exit(1)

VENTANA = "Vision - clic sobre la bola"
color_hsv = None        # color aprendido (H, S, V)
modo_negro = False      # True: bola blanca y negra (busca manchas oscuras)
UMBRAL_NEGRO = 70       # brillo maximo de las manchas negras (0-255)
zona = None             # (x1, y1, x2, y2) de la cancha
marcando = []           # clics mientras se marca la cancha
esperando_zona = False
TOL_H, TOL_S, TOL_V = 12, 70, 70


def abrir_camara(indice):
    cam = cv2.VideoCapture(indice, cv2.CAP_DSHOW)
    if not cam.isOpened():
        return None
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    ok, _ = cam.read()
    return cam if ok else None


def buscar_camaras():
    disponibles = []
    for i in range(5):
        c = abrir_camara(i)
        if c is not None:
            disponibles.append(i)
            c.release()
    return disponibles


ultimo_hsv_frame = None


def al_hacer_clic(evento, x, y, flags, param):
    global color_hsv, zona, esperando_zona, modo_negro
    if evento != cv2.EVENT_LBUTTONDOWN or ultimo_hsv_frame is None:
        return
    if esperando_zona:
        marcando.append((x, y))
        if len(marcando) == 2:
            (x1, y1), (x2, y2) = marcando
            zona = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
            esperando_zona = False
            marcando.clear()
            print(f"Cancha marcada: {zona}")
        return
    parche = ultimo_hsv_frame[max(0, y - 4):y + 5, max(0, x - 4):x + 5].reshape(-1, 3)
    color_hsv = np.median(parche, axis=0).astype(int)
    if color_hsv[1] < 60:   # casi sin color (blanco, negro o gris)
        modo_negro = True
        print("Esa bola no tiene color fuerte: uso el modo blanco y negro (manchas negras).")
    else:
        modo_negro = False
        print(f"Color aprendido (HSV): {tuple(color_hsv)}")


def mascara_negra(hsv):
    m = cv2.inRange(hsv, np.array([0, 0, 0]), np.array([179, 255, UMBRAL_NEGRO]))
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, None, iterations=1)
    m = cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (25, 25)), iterations=1)  # une las manchas de la bola
    return m


def recortar_a_zona(m):
    if zona is None:
        return m
    x1, y1, x2, y2 = zona
    fuera = np.zeros_like(m)
    fuera[y1:y2, x1:x2] = m[y1:y2, x1:x2]
    return fuera


def mascara(hsv):
    h, s, v = color_hsv
    bajo = np.array([max(0, h - TOL_H), max(40, s - TOL_S), max(40, v - TOL_V)])
    alto = np.array([min(179, h + TOL_H), 255, 255])
    m = cv2.inRange(hsv, bajo, alto)
    # el rojo da la vuelta en el circulo de color (H cerca de 0 y de 179)
    if h - TOL_H < 0:
        m |= cv2.inRange(hsv, np.array([180 + h - TOL_H, bajo[1], bajo[2]]), np.array([179, 255, 255]))
    if h + TOL_H > 179:
        m |= cv2.inRange(hsv, np.array([0, bajo[1], bajo[2]]), np.array([h + TOL_H - 180, 255, 255]))
    m = cv2.erode(m, None, iterations=2)
    m = cv2.dilate(m, None, iterations=2)
    return m


def main():
    global ultimo_hsv_frame, color_hsv, modo_negro, zona, esperando_zona
    camaras = buscar_camaras()
    if not camaras:
        print("No encontre ninguna camara. Revisa que iVCam este abierto en la PC y en el iPhone.")
        input("Presiona Enter para salir...")
        return
    print(f"Camaras encontradas: {camaras}. Presiona C para cambiar si no ves el iPhone.")
    k = len(camaras) - 1          # iVCam suele ser la ultima
    cam = abrir_camara(camaras[k])

    cv2.namedWindow(VENTANA, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(VENTANA, al_hacer_clic)

    anterior = None   # (x, y, t)
    t_fps, cuadros, fps = time.time(), 0, 0.0
    while True:
        ok, frame = cam.read()
        if not ok:
            print("Se perdio la imagen de la camara.")
            break
        hsv = cv2.cvtColor(cv2.GaussianBlur(frame, (7, 7), 0), cv2.COLOR_BGR2HSV)
        ultimo_hsv_frame = hsv
        alto_img, ancho_img = frame.shape[:2]

        texto = "Z = marcar cancha, luego clic sobre la bola (B si es blanca y negra)"
        if esperando_zona:
            texto = f"Marcando cancha: clic en la esquina {'superior izquierda' if not marcando else 'inferior derecha'}"
        if zona is not None:
            cv2.rectangle(frame, zona[:2], zona[2:], (255, 200, 0), 2)
        if (color_hsv is not None or modo_negro) and not esperando_zona:
            m = mascara_negra(hsv) if modo_negro else mascara(hsv)
            m = recortar_a_zona(m)
            contornos, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contornos:
                c = max(contornos, key=cv2.contourArea)
                (x, y), r = cv2.minEnclosingCircle(c)
                if r > 5:
                    cv2.circle(frame, (int(x), int(y)), int(r), (0, 255, 0), 3)
                    cv2.circle(frame, (int(x), int(y)), 4, (0, 0, 255), -1)
                    ahora = time.time()
                    vx = vy = 0.0
                    if anterior:
                        dt = ahora - anterior[2]
                        if dt > 0:
                            vx, vy = (x - anterior[0]) / dt, (y - anterior[1]) / dt
                    anterior = (x, y, ahora)
                    texto = f"Bola: x={x/ancho_img*100:5.1f}%  y={y/alto_img*100:5.1f}%   vel=({vx:6.0f}, {vy:6.0f}) px/s"
                    if abs(vx) + abs(vy) > 30:
                        cv2.arrowedLine(frame, (int(x), int(y)), (int(x + vx * 0.3), int(y + vy * 0.3)), (255, 0, 255), 3)
                else:
                    texto, anterior = "Bola no encontrada", None
            else:
                texto, anterior = "Bola no encontrada", None
            pequena = cv2.resize(m, (ancho_img // 4, alto_img // 4))
            frame[0:alto_img // 4, ancho_img - ancho_img // 4:ancho_img] = cv2.cvtColor(pequena, cv2.COLOR_GRAY2BGR)

        cuadros += 1
        if time.time() - t_fps >= 1:
            fps, cuadros, t_fps = cuadros / (time.time() - t_fps), 0, time.time()
        cv2.rectangle(frame, (0, alto_img - 40), (ancho_img, alto_img), (0, 0, 0), -1)
        cv2.putText(frame, f"{texto}   |  {fps:4.1f} fps  |  camara {camaras[k]}", (10, alto_img - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.imshow(VENTANA, frame)

        tecla = cv2.waitKey(1) & 0xFF
        if tecla == 27:
            break
        if tecla in (ord('r'), ord('R')):
            color_hsv, modo_negro = None, False
        if tecla in (ord('b'), ord('B')):
            modo_negro = True
            print("Modo bola blanca y negra activado.")
        if tecla in (ord('z'), ord('Z')):
            esperando_zona, zona = True, None
            marcando.clear()
        if tecla in (ord('c'), ord('C')):
            cam.release()
            k = (k + 1) % len(camaras)
            cam = abrir_camara(camaras[k])
            print(f"Usando camara {camaras[k]}")
        if cv2.getWindowProperty(VENTANA, cv2.WND_PROP_VISIBLE) < 1:
            break

    cam.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
