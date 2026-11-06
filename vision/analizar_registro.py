"""
Analiza las grabaciones de vision_cancha.py (tecla R) - Porteros Robot
Uso:  py -3 analizar_registro.py                -> analiza la grabacion mas reciente
      py -3 analizar_registro.py archivo.csv    -> una en particular
      py -3 analizar_registro.py --todas        -> todas las de la carpeta registros/
      py -3 analizar_registro.py archivo.csv 215 215   -> ademas compara contra la posicion real (mm)
"""
import csv, glob, os, sys
import numpy as np

CARPETA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "registros")


def cargar(ruta):
    with open(ruta) as f:
        filas = list(csv.DictReader(f))
    num = lambda c: np.array([float(r[c]) if r[c] != "" else np.nan for r in filas])
    return {c: num(c) for c in ("t", "detectada", "x_med", "y_med", "x_kal", "y_kal", "vx", "vy")}


def analizar(ruta, real=None):
    d = cargar(ruta)
    t, det = d["t"], d["detectada"] == 1
    n = len(t)
    print(f"\n=== {os.path.basename(ruta)} ===")
    if n < 2:
        print("Grabacion vacia"); return
    dur = t[-1] - t[0]
    print(f"Duracion {dur:.1f} s, {n} fotos -> {(n - 1) / dur:.1f} fps")
    print(f"Bola detectada en {det.mean() * 100:.1f} % de las fotos")
    # huecos: fotos seguidas sin detectar
    huecos, actual = [], 0
    for v in det:
        if v:
            if actual: huecos.append(actual)
            actual = 0
        else:
            actual += 1
    if actual: huecos.append(actual)
    if huecos:
        print(f"Perdidas: {len(huecos)} veces, la mas larga {max(huecos)} fotos seguidas")
    if not det.any():
        return
    x, y = d["x_med"][det], d["y_med"][det]
    v = np.hypot(d["vx"], d["vy"])
    v = v[~np.isnan(v)]
    quieta = len(v) and np.median(v) < 30
    if quieta:
        sx, sy = x.std(), y.std()
        print(f"BOLA QUIETA en x={x.mean():.1f} y={y.mean():.1f} mm")
        print(f"  Temblor (desv. estandar): x={sx:.2f} mm  y={sy:.2f} mm  | maximo salto {np.max(np.hypot(x - x.mean(), y - y.mean())):.1f} mm")
        print(f"  Temblor filtrado (Kalman): x={np.nanstd(d['x_kal']):.2f} mm  y={np.nanstd(d['y_kal']):.2f} mm")
        if real:
            ex, ey = x.mean() - real[0], y.mean() - real[1]
            print(f"  Error contra la posicion real ({real[0]:.0f}, {real[1]:.0f}): {np.hypot(ex, ey):.1f} mm (x {ex:+.1f}, y {ey:+.1f})")
    else:
        print(f"BOLA EN MOVIMIENTO: velocidad media {v.mean():.0f} mm/s, maxima {v.max():.0f} mm/s")
        print(f"  Recorrio x de {x.min():.0f} a {x.max():.0f} mm, y de {y.min():.0f} a {y.max():.0f} mm")
        # saltos imposibles = detecciones falsas
        tt = t[det]
        paso = np.hypot(np.diff(x), np.diff(y)) / np.maximum(np.diff(tt), 1e-3)
        print(f"  Saltos sospechosos (> 3000 mm/s entre fotos): {(paso > 3000).sum()}")


def main():
    args = sys.argv[1:]
    if args and args[0] == "--todas":
        rutas = sorted(glob.glob(os.path.join(CARPETA, "*.csv")))
    elif args:
        rutas = [args[0] if os.path.exists(args[0]) else os.path.join(CARPETA, args[0])]
    else:
        rutas = sorted(glob.glob(os.path.join(CARPETA, "*.csv")))[-1:]
    if not rutas:
        print("No hay grabaciones en", CARPETA); return
    real = (float(args[1]), float(args[2])) if len(args) >= 3 else None
    for r in rutas:
        analizar(r, real)


if __name__ == "__main__":
    main()
