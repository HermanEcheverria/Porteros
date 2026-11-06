"""Genera los diagramas del documento tecnico (PNG en ./figuras). Uso: py -3 diagramas.py"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figuras")
os.makedirs(OUT, exist_ok=True)

AZUL, VERDE, NARANJA, GRIS, ROJO, MORADO = "#dbe8f6", "#dff0dc", "#fde9d4", "#eeeeee", "#f8d9d9", "#e9e0f3"
BORDE = "#33475b"


def caja(ax, x, y, w, h, texto, color=AZUL, fs=9, negrita=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                                fc=color, ec=BORDE, lw=1.2))
    ax.text(x + w / 2, y + h / 2, texto, ha="center", va="center", fontsize=fs,
            fontweight="bold" if negrita else "normal")


def flecha(ax, x1, y1, x2, y2, rad=0.0, ls="-", doble=False):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="<|-|>" if doble else "-|>", mutation_scale=12,
                                 color=BORDE, lw=1.2, linestyle=ls, connectionstyle=f"arc3,rad={rad}"))


def texto(ax, x, y, t, fs=7.5, ha="center", fondo=True, **kw):
    ax.text(x, y, t, ha=ha, va="center", fontsize=fs,
            bbox=dict(fc="white", ec="none", pad=0.5) if fondo else None, **kw)


def nota(ax, x, y, t, fs=7.5, ha="left"):
    ax.text(x, y, t, ha=ha, va="center", fontsize=fs, bbox=dict(fc="#fff8e1", ec="#c9a227"))


def lienzo(w, h):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, w); ax.set_ylim(0, h); ax.axis("off")
    return fig, ax


def guardar(fig, nombre):
    fig.savefig(os.path.join(OUT, nombre), dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)


# ---------------------------------------------------------------- 1. arquitectura
fig, ax = lienzo(11, 7.4)
ax.add_patch(FancyBboxPatch((0.2, 5.0), 10.6, 2.2, boxstyle="round,pad=0.02", fc="#f7fbff", ec="#7a9cc0", ls="--"))
ax.text(0.4, 6.95, "LAPTOP  (Python 3 + OpenCV)", fontsize=10, fontweight="bold", color="#2a5b8c")
caja(ax, 0.4, 5.2, 1.8, 1.45, "Cámara cenital\n(iPhone + iVCam)\n640x480 a 60 fps", GRIS, 8.5)
caja(ax, 2.55, 5.2, 1.85, 1.45, "Percepción\nhomografía + HSV\n→ bola (x, y) en mm", AZUL, 8.5)
caja(ax, 4.75, 5.2, 1.85, 1.45, "Estimación\nKalman (x, y, vx, vy)\n+ latencia 0,10 s", AZUL, 8.5)
caja(ax, 6.95, 5.2, 1.85, 1.45, "Intercepción\ncruce con rebotes\n→ objetivo y golpe", AZUL, 8.5)
caja(ax, 9.15, 5.2, 1.5, 1.45, "Partida\ngoles, ganador,\nregistro CSV/MP4", NARANJA, 8.5)
for x in (2.2, 4.4, 6.6, 8.8):
    flecha(ax, x, 5.92, x + 0.35, 5.92)
flecha(ax, 1.5, 5.0, 1.5, 3.75, doble=True)
texto(ax, 1.7, 4.38, "USB serie a 115200 baud      laptop → Arduino:  T<mm>, K, V<i>,<d>, X<texto>, P<ms>"
      "      Arduino → laptop:  LISTO, estado, mediciones", 8.3, ha="left", fondo=False)
ax.add_patch(FancyBboxPatch((0.2, 1.75), 10.6, 2.0, boxstyle="round,pad=0.02", fc="#fbfff7", ec="#7fae73", ls="--"))
ax.text(0.4, 3.5, "ARDUINO UNO con FreeRTOS  (uno por portero, mismo firmware)", fontsize=10, fontweight="bold", color="#3f7a33")
caja(ax, 0.4, 1.9, 2.2, 1.35, "tSerial  (prioridad 2)\ndecodifica mensajes", VERDE, 8.5)
caja(ax, 3.0, 1.9, 2.4, 1.35, "tControl  (prioridad 3)\ncalibración, posición\ny control del carro", VERDE, 8.5)
caja(ax, 5.8, 1.9, 2.2, 1.35, "Temporizador (prio 3)\napaga el solenoide", VERDE, 8.5)
caja(ax, 8.4, 1.9, 2.3, 1.35, "Tarea ociosa (prio 0)\nsupervisión, LCD\ny reportes", VERDE, 8.5)
flecha(ax, 2.6, 2.55, 3.0, 2.55)
caja(ax, 3.0, 0.1, 1.1, 1.0, "Finales de\ncarrera", MORADO, 8)
caja(ax, 4.3, 0.1, 1.1, 1.0, "Motor DC\n(L298N #1)", ROJO, 8)
caja(ax, 6.35, 0.1, 1.1, 1.0, "Solenoide\n(L298N #2)", ROJO, 8)
caja(ax, 8.95, 0.1, 1.2, 1.0, "LCD 16x2\nI2C", MORADO, 8)
flecha(ax, 3.55, 1.1, 3.55, 1.9); texto(ax, 3.62, 1.45, "INT0/1", 7, ha="left", fondo=False)
flecha(ax, 4.85, 1.9, 4.85, 1.1); texto(ax, 4.92, 1.45, "PWM", 7, ha="left", fondo=False)
flecha(ax, 6.9, 1.9, 6.9, 1.1)
flecha(ax, 9.55, 1.9, 9.55, 1.1)
guardar(fig, "arquitectura.png")

# ---------------------------------------------------------------- 2. eléctrico
fig, ax = lienzo(11, 7.2)
caja(ax, 4.0, 2.4, 2.4, 2.8, "ARDUINO UNO\n(uno por portero)\n\nD5 (PWM), D4 → motor\nD9, D10 → solenoide\nD2, D3 ← finales\nD12, D11 = GND finales\nA4 SDA, A5 SCL → LCD\nUSB ↔ laptop", AZUL, 8.5)
caja(ax, 0.3, 4.4, 2.7, 1.9, "L298N #1 (motor)\nIN ← D5 (PWM), IN ← D4\nENB con jumper\nOUT → motor DC del carro\n+12 V de la fuente 1", VERDE, 8.5)
caja(ax, 0.3, 1.2, 2.7, 1.9, "L298N #2 (solenoides)\nIN1/IN3 ← D9\nIN2/IN4 ← D10\nOUT → solenoide push 12 V\n+12 V de la fuente 2", VERDE, 8.5)
caja(ax, 7.5, 4.6, 3.1, 1.6, "Finales de carrera (NO)\nizq: NO → D2, C → D12\nder: NO → D3, C → D11\npull-up interno, activos en LOW", MORADO, 8.5)
caja(ax, 7.5, 2.5, 3.1, 1.6, "LCD 1602 + módulo I2C\n(solo en el Uno izquierdo)\nVCC 5 V, GND, SDA A4, SCL A5\ndirección 0x27 / 0x3F", MORADO, 8.5)
caja(ax, 7.5, 0.5, 3.1, 1.5, "Laptop\nUSB: alimenta el Uno (5 V)\ny comunicación serie\n(COM6 izq, COM7 der)", GRIS, 8.5)
caja(ax, 0.3, 6.5, 2.7, 0.42, "Fuente 12 V #1", ROJO, 8)
caja(ax, 0.3, 0.6, 2.7, 0.42, "Fuente 12 V #2", ROJO, 8)
flecha(ax, 1.65, 6.5, 1.65, 6.3); flecha(ax, 1.65, 1.02, 1.65, 1.2)
flecha(ax, 4.0, 4.6, 3.0, 5.3); texto(ax, 3.5, 5.15, "D5, D4")
flecha(ax, 4.0, 3.0, 3.0, 2.2); texto(ax, 3.5, 2.35, "D9, D10")
flecha(ax, 7.5, 5.3, 6.4, 4.7); texto(ax, 6.95, 5.2, "D2, D3")
flecha(ax, 6.4, 3.4, 7.5, 3.3); texto(ax, 6.95, 3.55, "I2C")
flecha(ax, 6.4, 2.7, 7.5, 1.3, doble=True); texto(ax, 7.0, 1.9, "USB")
ax.text(5.45, 0.0, "GND común: Arduino, L298N #1, L298N #2 y las dos fuentes. El Arduino solo maneja entradas lógicas\n"
        "de los L298N (la potencia queda aislada); los diodos de rueda libre del módulo protegen contra las cargas inductivas.",
        ha="center", va="center", fontsize=8, bbox=dict(fc="#fff8e1", ec="#c9a227"))
guardar(fig, "electrico.png")

# ---------------------------------------------------------------- 3. tareas FreeRTOS
fig, ax = lienzo(11, 6.6)
caja(ax, 0.2, 4.9, 2.2, 1.0, "ISR finales de carrera\n(INT0 e INT1, ambos flancos)", ROJO, 8)
caja(ax, 0.2, 2.9, 2.2, 1.2, "UART RX\n(buffer de 64 B)", GRIS, 8.5)
caja(ax, 3.2, 2.6, 2.4, 1.8, "tSerial\nprioridad 2\nperiodo 1 tick (16 ms)\npila 150 B", VERDE, 8.5)
caja(ax, 7.4, 3.0, 3.1, 2.9, "tControl\nprioridad 3\nperiodo 1 tick o evento\npila 180 B\núnica dueña del motor:\ncalibración, posición,\ncontrol y protección de topes", VERDE, 8.5)
caja(ax, 7.4, 1.4, 3.1, 1.1, "Temporizador del kernel (prio 3)\nde un disparo: apaga el solenoide", VERDE, 8)
caja(ax, 3.2, 0.0, 2.4, 1.7, "Tarea ociosa (loop)\nprioridad 0, nunca bloquea\nsupervisión cada 100 ms\nLCD y reportes\nwatchdog → orden S", NARANJA, 8)
caja(ax, 7.4, 0.0, 3.1, 0.9, "Pantalla LCD (I2C)", MORADO, 8.5)
flecha(ax, 2.4, 5.4, 7.4, 5.4); texto(ax, 4.9, 5.62, "vTaskNotifyGiveFromISR: despierta a tControl sin esperar el tick", 7.5, fondo=False)
flecha(ax, 2.4, 3.5, 3.2, 3.5)
flecha(ax, 5.6, 4.1, 7.4, 4.1); texto(ax, 6.5, 4.38, "colaObjetivo (buzón, xQueueOverwrite)\n+ xTaskNotifyGive", 7, fondo=False)
flecha(ax, 5.6, 3.3, 7.4, 3.3); texto(ax, 6.5, 3.5, "colaOrden (4 órdenes)", 7, fondo=False)
flecha(ax, 5.6, 2.8, 7.4, 1.95); texto(ax, 6.25, 2.05, "golpe(): solenoide ON\n+ xTimerChangePeriod", 7, fondo=False)
flecha(ax, 3.8, 2.6, 3.8, 1.7); texto(ax, 3.72, 2.15, "colaLCD (2)", 7, ha="right", fondo=False)
flecha(ax, 5.0, 1.7, 5.0, 2.6, ls="--"); texto(ax, 4.92, 2.15, "banderas\np, m", 7, ha="right", fondo=False)
flecha(ax, 5.6, 0.45, 7.4, 0.45); texto(ax, 6.5, 0.62, "I2C", 7, fondo=False)
nota(ax, 0.2, 1.6, "mtxSerial: mutex con herencia de\nprioridad; protege Serial.print\nentre tSerial, tControl y la ociosa")
nota(ax, 0.2, 0.45, "Secciones críticas al copiar\nvariables de 4 bytes que\ncomparten tareas e ISR")
guardar(fig, "tareas_freertos.png")

# ---------------------------------------------------------------- 4. estados del firmware
fig, ax = lienzo(11, 5.8)
B = {"FALLO": (0.3, 4.0), "INICIALIZACIÓN": (0.3, 1.8), "ESPERA": (4.2, 1.8), "AUTOMÁTICO": (8.3, 3.6), "MANUAL": (8.3, 0.2)}
C = [ROJO, GRIS, AZUL, VERDE, NARANJA]
for (k, (x, y)), c in zip(B.items(), C):
    caja(ax, x, y, 2.2, 0.9, k, c, 9.5, True)
flecha(ax, 2.5, 2.25, 4.2, 2.25); texto(ax, 3.35, 2.6, "calibración OK\n(imprime LISTO)")
flecha(ax, 1.4, 2.7, 1.4, 4.0); texto(ax, 1.5, 3.35, "calibración fallida", ha="left")
flecha(ax, 6.4, 2.6, 8.3, 3.95, rad=-0.15); texto(ax, 6.85, 3.45, "llega T<mm>")
flecha(ax, 8.3, 3.7, 6.4, 2.45, rad=-0.15); texto(ax, 8.0, 2.85, "500 ms sin T (watchdog)\no espacio")
flecha(ax, 6.4, 1.95, 8.3, 0.75, rad=0.15); texto(ax, 6.9, 1.05, "tecla a / d")
flecha(ax, 8.3, 0.5, 6.4, 1.85, rad=0.15); texto(ax, 8.0, 1.6, "400 ms sin tecla\no espacio")
flecha(ax, 4.8, 2.7, 2.5, 4.4, rad=0.1); texto(ax, 4.6, 3.85, "ambos finales presionados\n(desde ESPERA, AUTOMÁTICO o MANUAL)")
ax.text(5.5, 5.5, "Tecla c (recalibrar): desde cualquier estado → INICIALIZACIÓN.   En FALLO el carro solo se mueve en manual.",
        fontsize=8, ha="center", bbox=dict(fc="white", ec="#999"))
guardar(fig, "estados_firmware.png")

# ---------------------------------------------------------------- 5. estados de la partida
fig, ax = lienzo(11, 4.6)
est = [("INICIALIZACIÓN", 0.2, 2.6, GRIS, "abre la cámara, conecta\ny calibra los porteros"),
       ("ESPERA", 2.4, 2.6, AZUL, "los dos responden LISTO;\nmarcador 0 - 0"),
       ("INICIO DE\nPARTIDA", 4.6, 2.6, AZUL, "tecla A (automático),\nbola al centro"),
       ("JUEGO", 6.8, 2.6, VERDE, "percepción, predicción,\nmovimiento y golpe"),
       ("ANOTACIÓN", 6.8, 0.0, NARANJA, "gol válido: venía rodando\nentre postes; +1 gol"),
       ("FIN", 4.6, 0.0, ROJO, "10 goles: GANA X a-b;\nel marcador vuelve a 0 - 0"),
       ("FALLO /\nSEGURIDAD", 9.0, 2.6, ROJO, "")]
for n, x, y, c, d in est:
    caja(ax, x, y + 0.85, 1.9, 0.8, n, c, 8.5, True)
    if d:
        ax.text(x + 0.95, y + 0.4, d, ha="center", va="center", fontsize=7)
for x in (2.1, 4.3, 6.5, 8.7):
    flecha(ax, x, 3.85, x + 0.3, 3.85)
flecha(ax, 7.95, 2.75, 7.95, 1.65); texto(ax, 8.02, 2.2, "gol", ha="left", fondo=False)
flecha(ax, 7.4, 1.65, 7.4, 2.75); texto(ax, 7.33, 2.2, "< 10 goles", ha="right", fondo=False)
flecha(ax, 6.8, 1.25, 6.5, 1.25); texto(ax, 6.65, 1.8, "10\ngoles", fondo=False)
flecha(ax, 4.6, 1.25, 3.35, 3.45, rad=-0.25); texto(ax, 3.1, 1.6, "nueva partida\n(o tecla N)", fondo=False)
ax.text(9.95, 2.95, "sin bola, sin objetivo\no calibración fallida:\nel carro se frena o\nvuelve al centro;\nla tecla L recalibra", ha="center", va="top", fontsize=7)
guardar(fig, "estados_partida.png")

# ---------------------------------------------------------------- 6. flujo percepción -> golpe
fig, ax = lienzo(11, 4.6)
pasos = ["1. Foto 640x480\n(hilo de captura: solo\nse usa la más nueva)", "2. Homografía con las\n4 esquinas → vista\nenderezada en mm",
         "3. Máscara HSV + apertura\ny cierre → mancha válida\nmás circular", "4. Kalman de velocidad\nconstante (predice hasta\n0,15 s sin medición)",
         "5. Compensa la latencia:\nposición + v · 0,10 s", "6. Cruce con la línea\ndel portero, con\nrebotes en espejo",
         "7. Objetivo del carro\nmm = (y − y0) / (s · esc)\n→ T<mm>", "8. Golpe K si faltan\n< 0,08 s, |x − xl| < 25 mm\ny |vx| > 80 mm/s"]
col = [GRIS, AZUL, AZUL, AZUL, AZUL, VERDE, VERDE, NARANJA]
for i, p in enumerate(pasos):
    fila, c = divmod(i, 4)
    x, y = 0.2 + c * 2.72, 2.6 - fila * 2.0
    caja(ax, x, y, 2.3, 1.45, p, col[i], 8)
    if c:
        flecha(ax, x - 0.42, y + 0.72, x, y + 0.72)
flecha(ax, 9.35, 2.6, 1.35, 2.05)
ax.text(5.5, 0.2, "Medición inválida (área fuera de 150–4000 mm² o salto imposible): se usa la predicción;  "
        "sin bola más de 1 s: el carro vuelve al centro.", ha="center", fontsize=8, style="italic")
guardar(fig, "flujo_percepcion.png")
print("diagramas en", OUT)
