"""
Vision de la cancha - Porteros Robot
  1) Clic en los 4 extremos de las paredes RECTAS de arriba y de abajo del octagono
     (las esquinas de adentro, donde empiezan las paredes diagonales), en orden:
       arriba izquierda -> arriba derecha -> abajo derecha -> abajo izquierda
     La imagen se "endereza" de la cara de un portero a la del otro y cada pixel pasa a ser
     milimetros reales. Se guarda en calibracion.json (solo se hace una vez).
  2) Deteccion de la bola (tecla M cambia el modo):
     - color (por defecto): la bola se separa por color HSV. Hay dos colores (azul y naranja)
       y se buscan LOS DOS a la vez, asi sirve cualquiera de las dos pelotas sin cambiar nada.
       B elige cual color se ajusta; clic DERECHO sobre la bola toma su color para ese perfil;
       afina con los sliders de la ventana "Color" y guarda con G.
     - fondo: resta contra la cancha vacia (quita la bola y presiona F). Detecta TODO lo que se mueve.
  3) Un filtro de Kalman suaviza la posicion y estima la velocidad; con eso se predice donde
     cruza la linea de cada porteria y se manda al Arduino de ese portero:
     "T<mm>\n" (objetivo del carro) y "K\n" (golpe).

IMPORTANTE: en la app iVCam del iPhone fija la exposicion, el balance de blancos y el enfoque
(sin automaticos), o el color de la bola cambia con la luz. Usa "Single Camera" para 60 fps.

Teclas: K = recalibrar esquinas   M = modo color/fondo   G = guardar color   F = guardar fondo
        B = elegir color que se ajusta (azul / naranja)
        + / - = sensibilidad (modo fondo)   C = cambiar camara   R = grabar CSV + video
        A = porteros automaticos ON/OFF     L = calibrar carros (manda 'c')   Esc = salir
        N = marcador a 0 - 0 (tambien vuelve solo a 0 - 0 cuando alguien llega a GOLES_GANAR)
Goles: la camara cuenta gol cuando la bola pasa la cara del portero entre los postes. El gol lo
anota el jugador contrario, y el marcador se manda a la pantalla LCD ("V<izq>,<der>" y "X<mensaje>").
Clic izquierdo sobre la vista enderezada: imprime ese punto en mm (sirve para medir Y_CERO).
"""
import csv, json, os, threading, time
from collections import deque
import cv2
import numpy as np
from trayectoria import Kalman, cruce, a_carro

try:
    import serial
except ImportError:
    serial = None

# ---- camara ----
CAM_ANCHO, CAM_ALTO, CAM_FPS = 640, 480, 60   # menos resolucion y mas fps = mejor velocidad

# ---- medidas reales de la cancha (MEDIR CON REGLA) ----
# Sistema de coordenadas: x = 0 en la cara del portero izquierdo, x = ANCHO_MM en la del derecho;
# y = 0 en la pared recta de arriba, y = ALTO_MM en la pared recta de abajo (por dentro).
ANCHO_MM = 400        # de la cara de un portero a la cara del otro (medido: 40 cm)
PORTERIA_MM = 300     # ancho de cada porteria, de poste a poste (medido: 30 cm)
ALTO_MM = 430         # de la pared recta de arriba a la de abajo (medido: 43 cm)
PARED_SUP_MM = 240    # largo de la pared recta de arriba (medido: 24 cm)
PARED_INF_MM = 240    # largo de la pared recta de abajo (medido: 24 cm)
# Se supone que las paredes rectas estan centradas entre los dos porteros; si no, ajusta esto:
DESFASE_SUP_MM = 0    # cuanto esta corrida a la derecha la pared de arriba respecto al centro
DESFASE_INF_MM = 0
PX_POR_MM = 1.5       # resolucion de la imagen enderezada
MARGEN_MM = 40        # la vista se extiende esto fuera de la cancha: la bola pegada a la pared
                      # se ve completa (por su altura, en perspectiva "se sale" del piso)
AREA_MIN_MM2 = 150    # mancha minima para ser bola (~1.4 cm de diametro)
AREA_MAX_MM2 = 4000
# Hmin Hmax Smin Smax Vmin Vmax (H va de 0 a 179); se buscan todos a la vez
COLORES_INICIALES = {"azul": [95, 130, 100, 255, 50, 255], "naranja": [1, 25, 185, 255, 159, 255]}

# ---- porteros (medir en la cancha real) ----
# x_linea: x (mm) del CENTRO de la bola cuando toca la punta de golpe del portero
#          (punta medida: izq ~27 mm, der ~387 mm; + o - el radio de la bola, ~30 mm).
# y_cero:  y (mm) del centro del portero cuando su carro esta en el tope izquierdo (posicion 0 del riel).
# sentido: +1 si al ir hacia el tope derecho la y aumenta (baja en la imagen), -1 si disminuye.
# escala:  mm reales por mm que estima el firmware (medir: mandar T y ver con la camara donde queda).
# puerto:  "COM5", etc.; None = ese portero no esta conectado.
RECORRIDO_MM = 210     # recorrido del carro entre finales de carrera (medido con la camara)
PORTEROS = [
    dict(nombre="izq", puerto="COM6", x_linea=60,            y_cero=96,  sentido=+1, escala=1.12),  # medido 2026-11-05 (estabilizador + rampas): y = 96 + 1.12*carro
    dict(nombre="der", puerto="COM7", x_linea=ANCHO_MM - 40, y_cero=319, sentido=-1, escala=0.94),  # medido 2026-11-05 (estabilizador + rampas): y = 319 - 0.94*carro
]
REBOTES = True        # predecir rebotes en las paredes de arriba y abajo
LATENCIA_S = 0.10     # retraso camara+iVCam+proceso (medirlo); la posicion se adelanta este tiempo
T_GOLPE_S = 0.08      # golpear cuando a la bola le falte menos que esto para llegar a la linea...
DIST_GOLPE_MM = 25    # ...y ademas ya este a menos de esto de la linea (sin esto, bolas que rebotaban o se
VEL_GOLPE_MIN = 80    # detenian lejos provocaban golpes 0.5-0.8 s antes), viniendo a mas de esto (mm/s)
PULSO_GOLPE_MS = 350  # duracion del golpe; se le manda al Arduino ("P350") cada vez que se conecta
ESPERA_GOLPE_S = 0.9  # el firmware ignora otro golpe hasta que regresa el embolo (350 + 500 ms)
ENVIO_S = 0.05        # cada cuanto se puede mandar un objetivo nuevo
VIVO_S = 0.2          # reenviar aunque no cambie (el Arduino se frena si pasa 500 ms sin objetivo)
SIN_BOLA_S = 1.0      # sin bola este tiempo: el carro vuelve al centro

# ---- partida ----
GOLES_GANAR = 10      # el primero en llegar gana; se anuncia y el marcador vuelve a 0 - 0
POSTES_MM = ((ALTO_MM - PORTERIA_MM) / 2, (ALTO_MM + PORTERIA_MM) / 2)   # y de los postes de cada porteria
GOL_X_MM = 0          # gol: el centro de la bola pasa la cara del portero (x < 0 o x > ANCHO) entre los postes
GOL_PERDIDA_X_MM = 15 # o se pierde de vista con el centro a menos de esto de la cara (entro bajo el chasis)
GOL_PERDIDA_S = 0.3
GOL_VEL_MIN = 150     # y ademas venia rodando hacia esa porteria a mas de esto (mm/s) en el ultimo GOL_VENTANA_S:
GOL_VENTANA_S = 0.5   # una bola quieta junto al portero o una que levanta la mano no cuenta
GOL_BLOQUEO_S = 2.0   # despues de un gol no se cuenta otro por este tiempo...
REARME_X_MM = (100, 300)   # ...ni hasta que la bola vuelva a la zona central

CARPETA = os.path.dirname(os.path.abspath(__file__))
ARCHIVO = os.path.join(CARPETA, "calibracion.json")
REGISTROS = os.path.join(CARPETA, "registros")
VENTANA, VENTANA_COLOR = "Cancha", "Color"
W, H = int((ANCHO_MM + 2 * MARGEN_MM) * PX_POR_MM), int((ALTO_MM + 2 * MARGEN_MM) * PX_POR_MM)


def px(mm):
    """mm de la cancha -> pixel de la vista enderezada"""
    return int(round((mm + MARGEN_MM) * PX_POR_MM))


def mm_de_px(p):
    """pixel de la vista enderezada -> mm de la cancha"""
    return p / PX_POR_MM - MARGEN_MM
NOMBRES = ["IZQUIERDO de la pared de ARRIBA", "DERECHO de la pared de ARRIBA",
           "DERECHO de la pared de ABAJO", "IZQUIERDO de la pared de ABAJO"]


def puntos_destino():
    """Donde caen en la vista enderezada (px) los 4 extremos de las paredes rectas."""
    c = ANCHO_MM / 2
    mm = [(c + DESFASE_SUP_MM - PARED_SUP_MM / 2, 0), (c + DESFASE_SUP_MM + PARED_SUP_MM / 2, 0),
          (c + DESFASE_INF_MM + PARED_INF_MM / 2, ALTO_MM), (c + DESFASE_INF_MM - PARED_INF_MM / 2, ALTO_MM)]
    return (np.float32(mm) + MARGEN_MM) * PX_POR_MM
SLIDERS = ["H min", "H max", "S min", "S max", "V min", "V max"]
TOPES = [179, 179, 255, 255, 255, 255]

esquinas = []
resolucion = None          # resolucion de la camara con la que se marcaron las esquinas
colores = {n: list(r) for n, r in COLORES_INICIALES.items()}
activo = "azul"            # color que editan los sliders y el clic derecho
hsv = colores[activo]
umbral = 35
plano_actual = None        # ultima vista enderezada (para tomar el color con clic derecho)


def al_clic(ev, x, y, flags, p):
    if ev == cv2.EVENT_LBUTTONDOWN:
        if len(esquinas) < 4:
            esquinas.append((x, y))
            print(f"Esquina {NOMBRES[len(esquinas)-1]}: ({x}, {y})")
        else:
            print(f"Punto: x={mm_de_px(x):.0f} mm  y={mm_de_px(y):.0f} mm")
    elif ev == cv2.EVENT_RBUTTONDOWN and len(esquinas) == 4 and plano_actual is not None:
        tomar_color(x, y)


def tomar_color(x, y):
    """Rango HSV alrededor del color de un parche de 7x7 px de la bola."""
    parche = cv2.cvtColor(plano_actual[max(0, y-3):y+4, max(0, x-3):x+4], cv2.COLOR_BGR2HSV).reshape(-1, 3)
    h, s, v = np.median(parche, axis=0).astype(int)
    hsv[:] = [max(0, h - 12), min(179, h + 12), max(0, s - 70), 255, max(0, v - 80), 255]
    for nombre, valor in zip(SLIDERS, hsv):
        cv2.setTrackbarPos(nombre, VENTANA_COLOR, valor)
    print(f"Color {activo} tomado: H={h} S={s} V={v} -> rango {hsv} (G para guardar)")


def cambiar_color():
    """B: pasa los sliders y el clic derecho al otro color."""
    global activo, hsv
    nombres = list(colores)
    activo = nombres[(nombres.index(activo) + 1) % len(nombres)]
    hsv = colores[activo]
    for nombre, valor in zip(SLIDERS, hsv):
        cv2.setTrackbarPos(nombre, VENTANA_COLOR, valor)
    print(f"Ajustando el color {activo}: {hsv}")


def cargar():
    global resolucion
    if os.path.exists(ARCHIVO):
        with open(ARCHIVO) as f:
            d = json.load(f)
        esquinas.extend([tuple(p) for p in d["esquinas"]])
        r = d.get("resolucion", (1280, 720))                  # las calibraciones viejas eran a 1280x720
        resolucion = tuple(r) if r else None
        if "colores" in d:
            for n, r in d["colores"].items():
                colores.setdefault(n, list(r))[:] = r
        elif "hsv" in d:                                       # formato viejo: un solo color
            h0 = d["hsv"][0]
            colores["naranja" if h0 < 40 else "azul"][:] = d["hsv"]
        print("Calibracion cargada de", ARCHIVO)


def guardar():
    with open(ARCHIVO, "w") as f:
        json.dump({"esquinas": esquinas, "resolucion": resolucion, "colores": colores,
                   "ancho_mm": ANCHO_MM, "alto_mm": ALTO_MM}, f)
    print("Calibracion guardada en", ARCHIVO)


class Camara:
    """Lee la camara en un hilo aparte y guarda SOLO la foto mas nueva:
    asi nunca se procesan fotos atrasadas del buffer del driver."""

    def __init__(self, i):
        self.cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAM_ANCHO); self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_ALTO)
        self.cap.set(cv2.CAP_PROP_FPS, CAM_FPS)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)            # no todos los drivers lo respetan; el hilo lo garantiza
        self.frame, self.t, self.n = None, 0.0, 0
        self.cond = threading.Condition()
        self.vivo = True
        self.hilo = threading.Thread(target=self._bucle, daemon=True)
        self.hilo.start()

    def _bucle(self):
        while self.vivo:
            ok, f = self.cap.read()
            t = time.time()
            if not ok:
                time.sleep(0.05); continue
            with self.cond:
                self.frame, self.t, self.n = f, t, self.n + 1
                self.cond.notify_all()

    def leer(self, n_visto, espera=1.0):
        """Espera una foto mas nueva que n_visto. Devuelve (foto, instante, numero) o (None, 0, n_visto)."""
        with self.cond:
            self.cond.wait_for(lambda: self.n != n_visto or not self.vivo, espera)
            if self.n == n_visto:
                return None, 0.0, n_visto
            return self.frame, self.t, self.n

    def cerrar(self):
        self.vivo = False
        self.hilo.join(timeout=1.0)                         # que el hilo suelte la camara antes de cerrarla
        self.cap.release()


def gris(img):
    return cv2.GaussianBlur(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (7, 7), 0)


def mejor_mancha(m):
    """La mancha mas grande con tamano y redondez de bola: (x, y, r, area) en px de la vista."""
    cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    a_min, a_max = AREA_MIN_MM2 * PX_POR_MM ** 2, AREA_MAX_MM2 * PX_POR_MM ** 2
    mejor = None
    for c in cs:
        a = cv2.contourArea(c)
        if not (a_min <= a <= a_max):
            continue
        (x, y), r = cv2.minEnclosingCircle(c)
        redondez = a / (np.pi * r * r + 1e-6)       # 1 = circulo perfecto
        if redondez < 0.4:
            continue
        if mejor is None or a > mejor[3]:
            mo = cv2.moments(c)                     # centro de masa: mas estable que el del circulo
            mejor = (mo["m10"] / mo["m00"], mo["m01"] / mo["m00"], r, a)
    return mejor


def buscar_color(plano):
    img = cv2.cvtColor(cv2.GaussianBlur(plano, (5, 5), 0), cv2.COLOR_BGR2HSV)
    m = None
    for r in colores.values():
        mi = cv2.inRange(img, np.array(r[0::2]), np.array(r[1::2]))
        m = mi if m is None else cv2.bitwise_or(m, mi)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, k)      # quita puntitos sueltos
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, k)     # rellena huecos (brillos, pentagonos)
    return mejor_mancha(m), m


def buscar_fondo(plano, fondo):
    dif = cv2.absdiff(gris(plano), fondo.astype(np.uint8))
    _, m = cv2.threshold(dif, umbral, 255, cv2.THRESH_BINARY)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
    m = cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
    return mejor_mancha(m), m


def crear_sliders():
    cv2.namedWindow(VENTANA_COLOR, cv2.WINDOW_NORMAL)
    for nombre, valor, tope in zip(SLIDERS, hsv, TOPES):
        cv2.createTrackbar(nombre, VENTANA_COLOR, valor, tope, lambda v: None)


def leer_sliders():
    try:
        hsv[:] = [cv2.getTrackbarPos(n, VENTANA_COLOR) for n in SLIDERS]   # edita el color activo
    except cv2.error:            # la ventana de sliders se cerro: se vuelve a abrir
        crear_sliders()


class Registro:
    """Graba CSV (una fila por foto) y el video de la vista, para medir y depurar."""

    def __init__(self):
        os.makedirs(REGISTROS, exist_ok=True)
        base = os.path.join(REGISTROS, time.strftime("%Y%m%d_%H%M%S"))
        self.f = open(base + ".csv", "w", newline="")
        self.csv = csv.writer(self.f)
        self.csv.writerow(["t", "detectada", "x_med", "y_med", "x_kal", "y_kal", "vx", "vy"]
                          + [f"T_{p['nombre']}" for p in PORTEROS] + [f"golpe_{p['nombre']}" for p in PORTEROS])
        self.video = cv2.VideoWriter(base + ".mp4", cv2.VideoWriter_fourcc(*"mp4v"), CAM_FPS, (W, H))
        self.t0 = time.time()
        print("Grabando en", base + ".csv / .mp4")

    def fila(self, t, med, est, objetivos, golpes, vista):
        m = [f"{v:.1f}" for v in med] if med else ["", ""]
        k = [f"{v:.1f}" for v in est] if est else ["", "", "", ""]
        self.csv.writerow([f"{t - self.t0:.4f}", int(med is not None)] + m + k
                          + ["" if o is None else o for o in objetivos] + [int(g) for g in golpes])
        self.video.write(vista)

    def cerrar(self):
        self.f.close(); self.video.release(); print("Grabacion cerrada")


class Portero:
    """Un portero = un Arduino en su propio puerto COM."""

    def __init__(self, cfg):
        self.__dict__.update(cfg)
        self.ser, self.objetivo, self.t_envio, self.t_golpe, self.buf = None, None, 0.0, 0.0, b""
        if self.puerto and serial:
            try:
                self.ser = serial.Serial(self.puerto, 115200, timeout=0, write_timeout=0)
                print(f"Portero {self.nombre}: conectado a {self.puerto} (el Arduino se reinicia y calibra)")
            except serial.SerialException as e:
                print(f"Portero {self.nombre}: no pude abrir {self.puerto} ({e})")
        elif self.puerto:
            print("Falta pyserial: py -3 -m pip install pyserial")

    def mandar(self, texto):
        if self.ser:
            try:
                self.ser.write(texto.encode())
            except serial.SerialException:
                pass

    def objetivo_mm(self, mm, ahora):
        cambio = self.objetivo is None or abs(mm - self.objetivo) >= 2
        if (cambio and ahora - self.t_envio >= ENVIO_S) or ahora - self.t_envio >= VIVO_S:
            self.mandar(f"T{mm}\n"); self.objetivo, self.t_envio = mm, ahora

    def golpe(self, ahora):
        if ahora - self.t_golpe >= ESPERA_GOLPE_S:
            self.mandar("K\n"); self.t_golpe = ahora

    def leer(self):
        """Imprime y devuelve lo que manda el Arduino (LISTO, TOPE, errores...)."""
        lineas = []
        if not self.ser:
            return lineas
        try:
            self.buf += self.ser.read(self.ser.in_waiting or 1)
        except serial.SerialException:
            return lineas
        while b"\n" in self.buf:
            linea, self.buf = self.buf.split(b"\n", 1)
            linea = linea.decode(errors="ignore").strip(" .\r")
            if linea:
                print(f"[{self.nombre}] {linea}")
                lineas.append(linea)
        return lineas

    def cerrar(self):
        if self.ser:
            self.ser.close()


class Partida:
    """Contador de goles de cada jugador y deteccion de gol con la camara."""

    def __init__(self, porteros):
        self.porteros = porteros
        self.nueva()

    def nueva(self):
        self.goles = {"izq": 0, "der": 0}   # goles ANOTADOS por cada jugador
        self.ganador = ""                     # ultimo ganador, para mostrarlo en la ventana
        self.armado, self.t_gol, self.ultima, self.t_ultima = True, -1e9, None, 0.0
        self.hist = deque()                  # (t, x) de las ultimas posiciones, para ver si venia rodando
        self.mensaje("Jugando")
        print("Marcador a 0 - 0")

    def pantalla(self):
        for p in self.porteros:              # el que no tiene LCD lo ignora
            p.mandar(f"V{self.goles['izq']},{self.goles['der']}\n")
            p.mandar(f"X{self.msg}\n")

    def mensaje(self, texto):
        self.msg = texto[:16]
        self.pantalla()

    def lado_gol(self, x, y, margen=GOL_X_MM):
        if not (POSTES_MM[0] - 10 <= y <= POSTES_MM[1] + 10):
            return None
        if x < margen: return "izq"
        if x > ANCHO_MM - margen: return "der"
        return None

    def venia_rodando(self, lado, ahora):
        """True si en el ultimo GOL_VENTANA_S la bola se acerco a esa porteria a mas de GOL_VEL_MIN."""
        pts = [(t, x) for t, x in self.hist if ahora - t <= GOL_VENTANA_S]
        if len(pts) < 3:
            return False
        (t0, x0), (t1, x1) = pts[0], pts[-1]
        if t1 - t0 < 0.05:
            return False
        v = (x1 - x0) / (t1 - t0)
        return v < -GOL_VEL_MIN if lado == "izq" else v > GOL_VEL_MIN

    def ver(self, med, ahora):
        """Llamar en cada foto con la posicion medida (o None). Devuelve el lado del gol o None."""
        lado = None
        if med:
            x, y = med
            self.hist.append((ahora, x))
            while self.hist and ahora - self.hist[0][0] > GOL_VENTANA_S + 0.2:
                self.hist.popleft()
            if not self.armado and REARME_X_MM[0] < x < REARME_X_MM[1]:
                self.armado = True
            if self.armado and ahora - self.t_gol > GOL_BLOQUEO_S:
                lado = self.lado_gol(x, y)
                t_ref = ahora
            self.ultima, self.t_ultima = med, ahora
        elif self.ultima and self.armado and ahora - self.t_gol > GOL_BLOQUEO_S and ahora - self.t_ultima > GOL_PERDIDA_S:
            x, y = self.ultima                # se perdio de vista pegada a la cara del portero: entro
            lado = self.lado_gol(x, y, GOL_PERDIDA_X_MM)
            t_ref = self.t_ultima
            self.ultima = None
        if not lado or not self.venia_rodando(lado, t_ref):
            return None
        anota = "der" if lado == "izq" else "izq"   # entra en la porteria izquierda: punto del derecho
        self.goles[anota] += 1
        self.armado, self.t_gol, self.ultima = False, ahora, None
        self.hist.clear()
        print(f"GOL de {anota} -> marcador IZQ {self.goles['izq']} - {self.goles['der']} DER")
        if self.goles[anota] >= GOLES_GANAR:
            final = f"{self.goles['izq']}-{self.goles['der']}"
            print(f"*** GANA {anota.upper()} {final} *** marcador a 0 - 0")
            self.ganador = f"GANA {anota.upper()} {final}"
            self.goles = {"izq": 0, "der": 0}
            self.mensaje(self.ganador)
        else:
            self.mensaje(f"GOL de {anota.upper()}!")
        return lado


def main():
    global umbral, resolucion, plano_actual
    print("=" * 60)
    print("Carpeta del programa:", CARPETA)
    print("=" * 60)
    cargar()
    guardadas = len(esquinas) == 4 and resolucion is not None   # calibracion completa ya en el archivo
    porteros = [Portero(c) for c in PORTEROS]
    partida = Partida(porteros)
    kalman = Kalman()
    auto, t_bola, modo, registro = False, 0.0, "color", None
    cam = 0; camara = Camara(cam)
    cv2.namedWindow(VENTANA, cv2.WINDOW_AUTOSIZE)   # sin escalar: los clics caen donde apuntas
    cv2.setMouseCallback(VENTANA, al_clic)
    crear_sliders()
    fondo, t_prev, fps, n_foto = None, time.time(), 0.0, 0
    destino = puntos_destino()

    while True:
        frame, ahora, n_foto = camara.leer(n_foto)
        if frame is None:
            if (cv2.waitKey(1) & 0xFF) == 27: break
            continue
        dt = ahora - t_prev; t_prev = ahora
        fps = 0.9 * fps + 0.1 * (1 / dt if dt > 0 else 0)
        for p in porteros:
            if "LISTO" in p.leer():
                partida.pantalla()                 # el Arduino se reinicio: volver a mostrar el marcador
                p.mandar(f"P{PULSO_GOLPE_MS}\n")   # y la duracion del golpe

        # la calibracion se hizo con otra resolucion: escalar las esquinas, o recalibrar si
        # cambio la proporcion (de 16:9 a 4:3 la imagen se recorta y escalar no sirve)
        tam = (frame.shape[1], frame.shape[0])
        if len(esquinas) == 4 and resolucion and tuple(resolucion) != tam:
            sx, sy = tam[0] / resolucion[0], tam[1] / resolucion[1]
            if abs(sx - sy) < 0.01:
                esquinas[:] = [(int(round(x * sx)), int(round(y * sy))) for x, y in esquinas]
                print(f"Esquinas escaladas de {tuple(resolucion)} a {tam}")
                resolucion = tam; guardar()
            else:
                print(f"La camara cambio de {tuple(resolucion)} a {tam}: marca otra vez las 4 esquinas")
                esquinas.clear(); resolucion = tam; guardadas = False

        # el cuarto clic llega durante waitKey: se guarda aqui, en la vuelta siguiente
        if len(esquinas) == 4 and not guardadas:
            resolucion = tam; guardar(); fondo = None; guardadas = True

        # ---- paso 1: calibrar esquinas ----
        if len(esquinas) < 4:
            for i, p in enumerate(esquinas):
                cv2.circle(frame, p, 7, (0, 0, 255), -1)
                if i: cv2.line(frame, esquinas[i-1], p, (0, 255, 255), 2)
            cv2.rectangle(frame, (0, 0), (frame.shape[1], 40), (0, 0, 0), -1)
            cv2.putText(frame, f"Clic en el extremo {NOMBRES[len(esquinas)]}",
                        (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)
            cv2.imshow(VENTANA, frame)
            if (cv2.waitKey(1) & 0xFF) == 27: break
            continue

        M = cv2.getPerspectiveTransform(np.float32(esquinas), destino)
        plano = cv2.warpPerspective(frame, M, (W, H))
        plano_actual = plano
        vista = plano.copy()
        cv2.rectangle(vista, (px(0), px(0)), (px(ANCHO_MM), px(ALTO_MM)), (160, 160, 160), 1)   # limites
        for p in porteros:                           # lineas de porteria
            cv2.line(vista, (px(p.x_linea), 0), (px(p.x_linea), H), (255, 0, 255), 1)
        for xg in (GOL_X_MM, ANCHO_MM - GOL_X_MM):   # lineas de gol entre los postes
            cv2.line(vista, (px(xg), px(POSTES_MM[0])), (px(xg), px(POSTES_MM[1])), (0, 200, 255), 2)

        # ---- paso 2: buscar la bola ----
        bola, mascara = None, None
        if modo == "color":
            leer_sliders()
            bola, mascara = buscar_color(plano)
            texto = "Sin bola (clic derecho sobre la bola para tomar su color)"
        elif fondo is not None:
            bola, mascara = buscar_fondo(plano, fondo)
            texto = "Sin bola"
            if not bola:                             # sin bola: el fondo se adapta despacio a la luz
                cv2.accumulateWeighted(gris(plano).astype(np.float32), fondo, 0.02)
        else:
            texto = "Modo fondo: quita la bola y presiona F"

        med = None
        if bola:
            x, y, r, _ = bola
            med = (mm_de_px(x), mm_de_px(y))
            kalman.agregar(ahora, *med)
            t_bola = ahora
            cv2.circle(vista, (int(x), int(y)), int(r), (0, 255, 0), 2)
        else:
            kalman.sin_medicion(ahora)
        est = kalman.estado()
        partida.ver(med, ahora)
        if mascara is not None:
            mini = cv2.resize(mascara, (W // 4, H // 4))
            vista[0:H // 4, W - W // 4:W] = cv2.cvtColor(mini, cv2.COLOR_GRAY2BGR)

        # ---- paso 3: prediccion y ordenes a cada portero ----
        if est:
            bx, by, vx, vy = est
            bx, by = bx + vx * LATENCIA_S, by + vy * LATENCIA_S    # donde esta la bola "ahora" de verdad
            texto = f"Bola x={bx:4.0f} y={by:4.0f} mm  vel=({vx:5.0f},{vy:5.0f}) mm/s" + ("" if med else " (prediccion)")
            cv2.arrowedLine(vista, (px(bx), px(by)), (px(bx + vx * 0.3), px(by + vy * 0.3)), (0, 0, 255), 2)
        elif med:
            texto = f"Bola x={med[0]:4.0f} y={med[1]:4.0f} mm"
        for p in porteros:
            if est:
                c = cruce(bx, by, vx, vy, p.x_linea, ALTO_MM, REBOTES)
                if c:                                # viene hacia este portero
                    yc, t = c
                    mm = a_carro(yc, p.y_cero, p.sentido, RECORRIDO_MM, p.escala)
                    cv2.circle(vista, (px(p.x_linea), px(yc)), 8, (0, 0, 255), -1)
                    texto += f" | {p.nombre}: T{mm} en {t:.2f}s"
                    if auto:
                        p.objetivo_mm(mm, ahora)
                        cerca = abs(bx - p.x_linea) < DIST_GOLPE_MM          # bx ya incluye el retraso de la camara
                        if med and cerca and abs(vx) > VEL_GOLPE_MIN and t < T_GOLPE_S:
                            p.golpe(ahora)
                    continue
                mm = a_carro(by, p.y_cero, p.sentido, RECORRIDO_MM, p.escala)   # se aleja: seguir su altura
            elif ahora - t_bola > SIN_BOLA_S:
                mm = RECORRIDO_MM // 2                                # sin bola: al centro
            else:
                mm = p.objetivo if p.objetivo is not None else RECORRIDO_MM // 2
            if auto:
                p.objetivo_mm(mm, ahora)

        marcador = f"IZQ {partida.goles['izq']:2d} - {partida.goles['der']:2d} DER" + (f"   ({partida.ganador})" if partida.ganador else "")
        cv2.rectangle(vista, (0, 0), (W // 2 + 120 if partida.ganador else W // 2 - 60, 26), (0, 0, 0), -1)
        cv2.putText(vista, marcador, (8, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2)
        cv2.rectangle(vista, (0, H - 34), (W, H), (0, 0, 0), -1)
        estado = f"{'AUTO' if auto else 'manual'} | {modo} (ajusta {activo}) | {fps:4.1f} fps" + (" | REC" if registro else "")
        cv2.putText(vista, estado, (8, H - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)
        cv2.putText(vista, texto, (8, H - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        cv2.imshow(VENTANA, vista)
        if registro:
            registro.fila(ahora, med, est, [p.objetivo for p in porteros], [p.t_golpe == ahora for p in porteros], vista)

        k = cv2.waitKey(1) & 0xFF
        if k == 27: break
        if k in (ord('k'), ord('K')): esquinas.clear(); fondo = None; guardadas = False
        if k in (ord('m'), ord('M')):
            modo = "fondo" if modo == "color" else "color"; kalman.reiniciar(); print("Modo:", modo)
        if k in (ord('g'), ord('G')): guardar()
        if k in (ord('b'), ord('B')): cambiar_color()
        if k in (ord('f'), ord('F')):
            acum, n = np.zeros((H, W), np.float32), 0
            while n < 15:                            # promedio de 15 fotos: menos ruido
                fr, _, n_foto = camara.leer(n_foto)
                if fr is None: break
                acum += gris(cv2.warpPerspective(fr, M, (W, H))).astype(np.float32); n += 1
            if n: fondo = acum / n; print("Fondo guardado.")
        if k == ord('+'): umbral = max(10, umbral - 5)     # mas sensible
        if k == ord('-'): umbral = min(100, umbral + 5)    # menos sensible
        if k in (ord('c'), ord('C')):
            camara.cerrar(); cam = (cam + 1) % 5; camara = Camara(cam); n_foto = 0; print("Camara", cam)
        if k in (ord('r'), ord('R')):
            if registro: registro.cerrar(); registro = None
            else: registro = Registro()
        if k in (ord('a'), ord('A')):
            auto = not auto; print("Porteros automaticos:", "ON" if auto else "OFF")
            if not auto:
                for p in porteros: p.mandar(" ")       # freno
        if k in (ord('n'), ord('N')):
            partida.nueva()
        if k in (ord('l'), ord('L')):
            auto = False
            for p in porteros: p.mandar("c")
            print("Calibrando carros...")

    if registro: registro.cerrar()
    for p in porteros:
        p.mandar(" "); p.cerrar()
    camara.cerrar(); cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
