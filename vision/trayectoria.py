"""
Prediccion de trayectoria - Porteros Robot
Coordenadas de la vista enderezada, en mm:
  x = de izquierda a derecha (portero izquierdo en x pequeno, derecho en x grande)
  y = de arriba a abajo (eje del riel de cada portero)
"""
from collections import deque
import cv2
import numpy as np


class Kalman:
    """Filtro de Kalman de velocidad constante: estado [x, y, vx, vy], medicion [x, y].
    Suaviza la posicion, estima la velocidad y sigue prediciendo si se pierde la bola unas fotos."""

    def __init__(self, ruido_med_mm=3.0, acel_mm_s2=2000.0, perdida_max_s=0.15):
        self.r, self.q, self.perdida_max = ruido_med_mm ** 2, acel_mm_s2 ** 2, perdida_max_s
        self.kf = cv2.KalmanFilter(4, 2)
        self.kf.measurementMatrix = np.array([[1, 0, 0, 0], [0, 1, 0, 0]], np.float32)
        self.kf.measurementNoiseCov = np.eye(2, dtype=np.float32) * self.r
        self.reiniciar()

    def reiniciar(self):
        self.t = None          # instante del estado actual
        self.t_med = None      # instante de la ultima medicion

    def _avanzar(self, t):
        dt = t - self.t
        if dt <= 0:
            return
        self.kf.transitionMatrix = np.array([[1, 0, dt, 0], [0, 1, 0, dt], [0, 0, 1, 0], [0, 0, 0, 1]], np.float32)
        # ruido de aceleracion aleatoria (modelo discreto de aceleracion blanca)
        a, b, c = dt ** 4 / 4, dt ** 3 / 2, dt ** 2
        self.kf.processNoiseCov = np.array([[a, 0, b, 0], [0, a, 0, b], [b, 0, c, 0], [0, b, 0, c]], np.float32) * self.q
        self.kf.predict()
        self.t = t

    def agregar(self, t, x, y):
        if self.t is None:
            self.kf.statePost = np.array([[x], [y], [0], [0]], np.float32)
            self.kf.errorCovPost = np.diag([self.r, self.r, 1e6, 1e6]).astype(np.float32)
            self.t = self.t_med = t
            self.n = 1
            return
        self._avanzar(t)
        self.kf.correct(np.array([[x], [y]], np.float32))
        self.t_med = t
        self.n += 1

    def sin_medicion(self, t):
        """Foto sin bola: predecir un rato; si se pierde demasiado, olvidar."""
        if self.t is None:
            return
        if t - self.t_med > self.perdida_max:
            self.reiniciar()
            return
        self._avanzar(t)
        self.kf.statePost = self.kf.statePre.copy()
        self.kf.errorCovPost = self.kf.errorCovPre.copy()

    def estado(self):
        """(x, y, vx, vy) en mm y mm/s; None hasta tener 3 mediciones (la velocidad aun no es confiable)."""
        if self.t is None or self.n < 3:
            return None
        return tuple(float(v) for v in self.kf.statePost.ravel())


class Rastreador:
    """Guarda las ultimas posiciones y estima la velocidad con minimos cuadrados
    (mas estable que restar solo dos fotos)."""

    def __init__(self, n=6, salto_max_mm=150):
        self.hist = deque(maxlen=n)
        self.salto_max = salto_max_mm

    def reiniciar(self):
        self.hist.clear()

    def agregar(self, t, x, y):
        if self.hist:
            _, x0, y0 = self.hist[-1]
            if np.hypot(x - x0, y - y0) > self.salto_max:   # salto imposible: deteccion falsa o bola nueva
                self.hist.clear()
        self.hist.append((t, x, y))

    def estado(self):
        """(x, y, vx, vy) en mm y mm/s en el instante de la ultima foto; None si hay pocos datos."""
        if len(self.hist) < 3:
            return None
        h = np.array(self.hist)
        t = h[:, 0] - h[-1, 0]
        if t[0] == 0:
            return None
        vx, x = np.polyfit(t, h[:, 1], 1)    # recta x(t): pendiente = velocidad, ordenada = posicion ahora
        vy, y = np.polyfit(t, h[:, 2], 1)
        return x, y, vx, vy


def reflejar(y, alto):
    """Rebotes en las paredes y=0 y y=alto (espejo)."""
    periodo = 2 * alto
    y = y % periodo
    return y if y <= alto else periodo - y


def cruce(x, y, vx, vy, x_linea, alto, rebotes=True, v_min=50):
    """Punto y donde la bola cruza la linea x = x_linea y el tiempo que falta (s).
    None si la bola no va hacia esa linea o va demasiado lenta."""
    dx = x_linea - x
    if abs(vx) < v_min or dx * vx <= 0:   # parada o alejandose
        return None
    t = dx / vx
    y_c = y + vy * t
    y_c = reflejar(y_c, alto) if rebotes else min(max(y_c, 0), alto)
    return y_c, t


def a_carro(y_mm, y_cero, sentido, recorrido=280, escala=1.0):
    """Convierte la y de la camara a la posicion del carro en el riel (0 = tope izquierdo).
    escala = mm reales que avanza el carro por cada mm que cree avanzar el firmware."""
    return int(round(min(max(sentido * (y_mm - y_cero) / escala, 0), recorrido)))


if __name__ == "__main__":
    # Pruebas rapidas: py -3 trayectoria.py
    assert reflejar(50, 430) == 50
    assert reflejar(-30, 430) == 30            # rebote en la pared de arriba
    assert reflejar(460, 430) == 400           # rebote en la pared de abajo
    # bola en el centro yendo recto a la izquierda a 500 mm/s: cruza x=40 en y=215 dentro de 0.35 s
    yc, t = cruce(215, 215, -500, 0, 40, 430)
    assert abs(yc - 215) < 1e-6 and abs(t - 0.35) < 1e-6
    assert cruce(215, 215, 500, 0, 40, 430) is None          # se aleja
    # en diagonal con rebote: y = 215 - 1000*0.35 = -135 -> 135
    yc, _ = cruce(215, 215, -500, -1000, 40, 430)
    assert abs(yc - 135) < 1e-6
    assert a_carro(75, 75, 1) == 0 and a_carro(400, 75, 1) == 280 and a_carro(215, 355, -1) == 140
    assert a_carro(93 + 1.1 * 100, 93, 1, 210, 1.1) == 100
    r = Rastreador()
    for i in range(6):
        r.agregar(i * 0.033, 300 - 0.033 * i * 600, 100 + 0.033 * i * 200)
    x, y, vx, vy = r.estado()
    assert abs(vx + 600) < 1 and abs(vy - 200) < 1
    # Kalman: bola a (-600, 200) mm/s con ruido de 3 mm, 60 fps
    rng = np.random.default_rng(0)
    k = Kalman()
    for i in range(30):
        t = i / 60
        k.agregar(t, 300 - 600 * t + rng.normal(0, 3), 100 + 200 * t + rng.normal(0, 3))
    x, y, vx, vy = k.estado()
    assert abs(vx + 600) < 100 and abs(vy - 200) < 100, (vx, vy)
    k.sin_medicion(31 / 60)                      # se pierde una foto: sigue prediciendo
    assert k.estado() is not None and k.estado()[0] < x
    k.sin_medicion(1.0)                          # perdida larga: se olvida
    assert k.estado() is None
    print("trayectoria.py: todas las pruebas pasaron")
