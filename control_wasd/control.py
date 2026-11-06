"""
Control WASD para el portero — Porteros Robot
Mantén A o D para mover el carro; al soltar se detiene.
W / S = más o menos velocidad, K = golpe, Espacio = freno, Esc = salir.

El Arduino debe tener cargado el programa "Control WASD" y el
Monitor Serie del Arduino IDE debe estar CERRADO.
"""
import sys
import threading
import time

try:
    import serial
    from serial.tools import list_ports
    from pynput import keyboard
except ImportError:
    print("Faltan librerías. Ejecuta: python -m pip install pyserial pynput")
    input("Presiona Enter para salir...")
    sys.exit(1)

VELOCIDAD_BAUDIOS = 115200


def buscar_arduino():
    puertos = list(list_ports.comports())
    for p in puertos:
        texto = f"{p.description} {p.manufacturer or ''}".lower()
        if any(k in texto for k in ("arduino", "ch340", "ch341", "usb-serial", "usb serial", "ftdi", "cp210")):
            return p.device
    return puertos[0].device if len(puertos) == 1 else None


puerto = sys.argv[1] if len(sys.argv) > 1 else buscar_arduino()
if not puerto:
    print("No encontré el Arduino. Puertos disponibles:")
    for p in list_ports.comports():
        print(f"  {p.device}  ({p.description})")
    print("Conéctalo por USB o ejecuta:  python control.py COM6")
    input("Presiona Enter para salir...")
    sys.exit(1)

try:
    ser = serial.Serial(puerto, VELOCIDAD_BAUDIOS, timeout=0)
except serial.SerialException:
    print(f"No pude abrir {puerto}. Cierra el Monitor Serie del Arduino IDE y vuelve a intentar.")
    input("Presiona Enter para salir...")
    sys.exit(1)

print(f"Conectado a {puerto}. Esperando al Arduino...")
time.sleep(2)  # el Uno se reinicia al abrir el puerto
print("A / D = mover (mantener)   W / S = velocidad   K = golpe   Espacio = freno\n"
      "V = sensores en vivo   P = estado   C = calibrar   M = seguir la bola\n"
      "F = medir fondo   R = reiniciar sensor   I = buscar I2C   Esc = salir\n")

presionadas = set()
corriendo = True


def tecla(k):
    try:
        return k.char.lower() if k.char else None
    except AttributeError:
        return None


def al_presionar(k):
    if k == keyboard.Key.esc:
        return False
    if k == keyboard.Key.space:
        ser.write(b" ")
        return
    c = tecla(k)
    if c in ("w", "s", "k", "c", "m", "p", "v", "f", "r", "i"):
        ser.write(c.encode())
    elif c in ("a", "d"):
        presionadas.add(c)


def al_soltar(k):
    c = tecla(k)
    if c in ("a", "d"):
        presionadas.discard(c)
        if not presionadas:
            ser.write(b"x")


def latido():
    while corriendo:
        try:
            if presionadas == {"a"}:
                ser.write(b"a")
            elif presionadas == {"d"}:
                ser.write(b"d")
            datos = ser.read(256)
            if datos:
                print(datos.decode(errors="ignore"), end="", flush=True)
        except serial.SerialException:
            print("\nSe perdió la conexión con el Arduino.")
            break
        time.sleep(0.08)


threading.Thread(target=latido, daemon=True).start()
with keyboard.Listener(on_press=al_presionar, on_release=al_soltar) as escucha:
    escucha.join()

corriendo = False
try:
    ser.write(b"x")
    ser.close()
except serial.SerialException:
    pass
print("\nListo, puerto cerrado.")
