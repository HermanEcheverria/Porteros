"""
Medidor de latencia de la camara - Porteros Robot
Apunta la camara (iPhone con iVCam) a la ventana "Destello", que cambia de negro a blanco.
Se mide cuanto tarda la camara en ver el cambio = latencia (incluye ~10-20 ms del monitor).
Pon ese numero en LATENCIA_S de vision_cancha.py.  Esc = salir.
"""
import time
import cv2
import numpy as np
from vision_cancha import Camara

CAMBIO_S = 0.8        # cada cuanto cambia de color la pantalla
MEDICIONES = 20


def main():
    camara = Camara(0)
    cv2.namedWindow("Destello", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Destello", 700, 500)
    blanco, t_cambio, esperando = False, time.time(), False
    claro_neg, claro_bla = None, None     # brillo que ve la camara con la pantalla negra / blanca
    resultados, n = [], 0
    cv2.imshow("Destello", np.zeros((500, 700), np.uint8))
    print("Apunta la camara a la ventana 'Destello' para que la llene casi toda...")
    while len(resultados) < MEDICIONES:
        if time.time() - t_cambio > CAMBIO_S:
            blanco = not blanco
            cv2.imshow("Destello", np.full((500, 700), 255 if blanco else 0, np.uint8))
            cv2.waitKey(1)                     # aqui se pinta de verdad
            t_cambio = time.time()
            esperando = claro_neg is not None and claro_bla is not None
        if (cv2.waitKey(1) & 0xFF) == 27: break
        ahora = time.time()

        f, t_foto, n = camara.leer(n, espera=0.005)
        if f is None:
            continue
        brillo = float(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).mean())
        # aprender los niveles al final de cada fase (cuando la camara ya se estabilizo)
        if ahora - t_cambio > CAMBIO_S * 0.8:
            if blanco: claro_bla = brillo
            else: claro_neg = brillo
        if esperando and claro_bla - claro_neg > 20:
            medio = (claro_bla + claro_neg) / 2
            if (brillo > medio) == blanco:
                lat = (t_foto - t_cambio) * 1000
                resultados.append(lat); esperando = False
                print(f"  {len(resultados):2d}: {lat:5.0f} ms")
    camara.cerrar(); cv2.destroyAllWindows()
    if resultados:
        r = np.array(resultados)
        print(f"\nLatencia: mediana {np.median(r):.0f} ms  (min {r.min():.0f}, max {r.max():.0f})")
        print(f"-> LATENCIA_S = {np.median(r) / 1000:.2f}")
    else:
        print("No se pudo medir: la camara no ve la diferencia entre negro y blanco.")


if __name__ == "__main__":
    main()
