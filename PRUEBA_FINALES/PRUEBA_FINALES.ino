/*
  PRUEBA COMPLETA DEL PORTERO — Porteros Robot
  Necesita la libreria "VL53L0X" de Pololu (Herramientas > Administrar bibliotecas).

  Conexiones (pestana Conexiones):
    Motor:      L298N IN3 -> 5, IN4 -> 4        (jumper ENB puesto)
    Solenoide:  L298N IN1 -> 8, IN2 -> 7        (jumper ENA puesto)
    Final izq:  NO -> 2, C -> 12                Final der: NO -> 3, C -> 11
    VL53L0X:    VIN -> 3V3, GND -> GND, SDA -> A4, SCL -> A5
    IR de gol:  VCC -> 5V, GND -> GND de arriba (junto a AREF), OUT -> A3

  Teclas (control WASD o Monitor Serie a 115200 + Enter):
    a / d  mover a la izquierda / derecha     espacio  freno
    w / s  mas / menos velocidad              k        golpe del solenoide
    v      ver sensores en vivo (on/off)      p        estado una vez
    c      calibrar recorrido                 m        modo seguir la bola (on/off)
    i      buscar dispositivos I2C
*/
#include <Wire.h>
#include <VL53L0X.h>

// ===== AJUSTA ESTOS VALORES =====
const bool INVERTIR_MOTOR      = false; // true si 'a' mueve el carro a la DERECHA
const bool SENSOR_A_LA_DERECHA = true;  // true si el VL53L0X esta del lado del final derecho
const int  RECORRIDO_MM        = 280;   // distancia entre los dos finales (midela con regla)
const int  OFFSET_SENSOR_MM    = 0;     // distancia del VL53L0X al final mas cercano

// ===== Pines =====
const int M_IN3 = 5, M_IN4 = 4;
const int SOL_IN1 = 8, SOL_IN2 = 7;
const int FIN_IZQ = 2, FIN_DER = 3, GND_IZQ = 12, GND_DER = 11;
const int IR_GOL = A3;

const unsigned long WATCHDOG_MS = 400, PULSO_MS = 40, ESPERA_GOLPE_MS = 500;

VL53L0X sensor;
bool sensorOK = false;

volatile int dir = 0;        // -1 hacia izquierda, 0 parado, 1 hacia derecha
int velocidad = 160, velCal = 160;
unsigned long tVivo = 0;
unsigned long ultimo = 0, ultimoGolpe = 0, tPrev = 0, tMostrar = 0, ultimaBola = 0, ultimoGol = 0;
bool modoSeguir = false, calibrado = false, mostrar = false, golAntes = false;
float posMM = 0, velMMms = 0;
int goles = 0;

bool topeConfirmado(int pin);
bool izq() { return topeConfirmado(FIN_IZQ); }
bool der() { return topeConfirmado(FIN_DER); }
bool golDetectado() { return digitalRead(IR_GOL) == LOW; }

void salidaMotor(int d) {
  if (INVERTIR_MOTOR) d = -d;
  if (d > 0)      { digitalWrite(M_IN4, LOW);  analogWrite(M_IN3, velocidad); }
  else if (d < 0) { digitalWrite(M_IN4, HIGH); analogWrite(M_IN3, 255 - velocidad); }
  else            { digitalWrite(M_IN4, LOW);  analogWrite(M_IN3, 0); }
}
void motor(int d) {
  if (d < 0 && izq()) d = 0;           // nunca empujar contra un tope
  if (d > 0 && der()) d = 0;
  dir = d; salidaMotor(d);
}
void frenar() {
  dir = 0;
  digitalWrite(M_IN4, HIGH); analogWrite(M_IN3, 255);
  delay(40);
  salidaMotor(0);
}
// Lectura confirmada de un tope: debe leerse presionado 3 veces seguidas (filtra el ruido del motor)
bool topeConfirmado(int pin) {
  for (int i = 0; i < 3; i++) { if (digitalRead(pin) != LOW) return false; delayMicroseconds(300); }
  return true;
}
void revisarTopes() {
  if (dir < 0 && topeConfirmado(FIN_IZQ)) { frenar(); Serial.println(F("TOPE IZQUIERDO")); }
  if (dir > 0 && topeConfirmado(FIN_DER)) { frenar(); Serial.println(F("TOPE DERECHO")); }
}

void golpe() {
  if (millis() - ultimoGolpe < ESPERA_GOLPE_MS) return;
  ultimoGolpe = millis();
  digitalWrite(SOL_IN1, HIGH); delay(PULSO_MS); digitalWrite(SOL_IN1, LOW);
  Serial.println(F("GOLPE"));
}

int distanciaMM() {                     // -1 si no hay lectura valida
  if (!sensorOK) return -1;
  uint16_t d = sensor.readRangeContinuousMillimeters();
  if (sensor.timeoutOccurred() || d >= 8000) return -1;
  return d;
}
int posicionBola(int d) {               // posicion de la bola desde el final izquierdo
  if (d < 0) return -1;
  int a = d - OFFSET_SENSOR_MM;
  if (a < 0 || a > RECORRIDO_MM + 20) return -1;   // fuera de la porteria
  int p = SENSOR_A_LA_DERECHA ? RECORRIDO_MM - a : a;
  return constrain(p, 0, RECORRIDO_MM);
}

void actualizarPos() {
  unsigned long now = millis();
  if (calibrado && velocidad == velCal) posMM += dir * velMMms * (now - tPrev);
  tPrev = now;
  if (izq()) posMM = 0;
  if (der()) posMM = RECORRIDO_MM;
  posMM = constrain(posMM, 0, RECORRIDO_MM);
}

void estado() {
  int d = distanciaMM();
  Serial.print(F("Fin izq: ")); Serial.print(izq() ? F("SI") : F("no"));
  Serial.print(F(" | Fin der: ")); Serial.print(der() ? F("SI") : F("no"));
  Serial.print(F(" | IR gol: ")); Serial.print(golDetectado() ? F("BOLA") : F("libre"));
  Serial.print(F(" | VL53: "));
  if (!sensorOK) Serial.print(F("sin sensor"));
  else if (d < 0) {
    uint16_t raw = sensor.readRangeContinuousMillimeters();
    if (sensor.timeoutOccurred()) Serial.print(F("sin respuesta (timeout)"));
    else { Serial.print(F("nada a la vista (crudo ")); Serial.print(raw); Serial.print(F(")")); }
  }
  else { Serial.print(d); Serial.print(F(" mm (bola en ")); Serial.print(posicionBola(d)); Serial.print(F(" mm)")); }
  Serial.print(F(" | Portero: "));
  if (calibrado) { Serial.print((int)posMM); Serial.print(F(" mm")); } else Serial.print(F("sin calibrar"));
  Serial.print(F(" | Goles: ")); Serial.println(goles);
}

bool esperarTope(bool (*tope)(), unsigned long maxMs) {
  unsigned long t0 = millis();
  while (!tope()) {
    if (millis() - t0 > maxMs) { frenar(); return false; }
  }
  frenar();
  return true;
}

void calibrar() {
  modoSeguir = false;
  Serial.println(F("Calibrando: voy al final izquierdo..."));
  if (!izq()) { motor(-1); if (!esperarTope(izq, 8000)) { Serial.println(F("ERROR: no llegue al final izquierdo")); return; } }
  delay(300);
  Serial.println(F("Midiendo hasta el final derecho..."));
  velCal = velocidad;
  unsigned long t0 = millis();
  motor(1);
  if (!esperarTope(der, 8000)) { Serial.println(F("ERROR: no llegue al final derecho")); return; }
  unsigned long T = millis() - t0;
  velMMms = (float)RECORRIDO_MM / T;
  calibrado = true; posMM = RECORRIDO_MM;
  Serial.print(F("Recorrido en ")); Serial.print(T); Serial.print(F(" ms = "));
  Serial.print(velMMms * 1000, 0); Serial.println(F(" mm/s"));
  delay(300);
  motor(-1); delay((unsigned long)((RECORRIDO_MM / 2) / velMMms)); frenar();   // al centro
  posMM = RECORRIDO_MM / 2; tPrev = millis();
  Serial.println(F("Listo, portero en el centro. Presiona m para seguir la bola."));
}

void seguir() {
  int b = posicionBola(distanciaMM());
  int objetivo;
  if (b >= 0) { ultimaBola = millis(); objetivo = b; }
  else if (millis() - ultimaBola > 1500) objetivo = RECORRIDO_MM / 2;  // sin bola: al centro
  else return;
  float err = objetivo - posMM;
  if (err > 12)       { if (dir != 1)  motor(1); }
  else if (err < -12) { if (dir != -1) motor(-1); }
  else if (dir != 0)  frenar();
  if (b >= 0 && fabs(err) < 25) golpe();   // alineado con la bola: golpear
}

void escanearI2C() {
  Serial.println(F("Buscando dispositivos I2C (SDA=A4, SCL=A5)..."));
  int n = 0;
  for (byte addr = 1; addr < 127; addr++) {
    Wire.beginTransmission(addr);
    if (Wire.endTransmission() == 0) {
      Serial.print(F("  Encontrado en 0x")); if (addr < 16) Serial.print('0'); Serial.print(addr, HEX);
      if (addr == 0x29) Serial.print(F("  <- VL53L0X"));
      if (addr == 0x27 || addr == 0x3F) Serial.print(F("  <- pantalla LCD"));
      Serial.println(); n++;
    }
  }
  if (n == 0) Serial.println(F("  Ninguno. El sensor no esta conectado bien (cables, alimentacion o pines sin soldar)."));
}

void setup() {
  pinMode(M_IN3, OUTPUT); pinMode(M_IN4, OUTPUT); salidaMotor(0);
  pinMode(SOL_IN1, OUTPUT); pinMode(SOL_IN2, OUTPUT); digitalWrite(SOL_IN1, LOW); digitalWrite(SOL_IN2, LOW);
  pinMode(GND_IZQ, OUTPUT); digitalWrite(GND_IZQ, LOW);
  pinMode(GND_DER, OUTPUT); digitalWrite(GND_DER, LOW);
  pinMode(FIN_IZQ, INPUT_PULLUP); pinMode(FIN_DER, INPUT_PULLUP);
  pinMode(IR_GOL, INPUT);
  Serial.begin(115200);
  delay(2000);   // da tiempo a que el Monitor Serie se conecte
  Serial.println();
  Wire.begin();
  Wire.setWireTimeout(3000, true);   // nunca quedarse trabado esperando al sensor
  sensor.setTimeout(100);
  sensorOK = sensor.init();
  if (sensorOK) { sensor.setMeasurementTimingBudget(33000); sensor.startContinuous(); }
  Serial.println(F("=== PRUEBA DEL PORTERO ==="));
  Serial.println(sensorOK ? F("VL53L0X: OK") : F("VL53L0X: NO RESPONDE (revisa SDA/SCL/3V3/GND)"));
  golAntes = golDetectado();
  estado();
  Serial.println(F("Teclas: a/d mover, k golpe, v sensores, c calibrar, m seguir, i buscar I2C"));
  tPrev = millis();
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    switch (c) {
      case 'a': case 'd':
        if (modoSeguir) { Serial.println(F("Modo seguir activo: presiona m para salir")); break; }
        ultimo = millis();
        { int d = (c == 'a') ? -1 : 1; if (dir != d) { motor(d); if (dir == 0) Serial.println(F("Bloqueado por el tope")); else Serial.println(d < 0 ? F("<- izquierda") : F("-> derecha")); } }
        break;
      case 'x': if (!modoSeguir && dir != 0) { dir = 0; salidaMotor(0); } break;
      case ' ': modoSeguir = false; frenar(); Serial.println(F("freno")); break;
      case 'w': velocidad = min(255, velocidad + 15); Serial.print(F("velocidad ")); Serial.println(velocidad); break;
      case 's': velocidad = max(60,  velocidad - 15); Serial.print(F("velocidad ")); Serial.println(velocidad); break;
      case 'k': golpe(); break;
      case 'p': estado(); break;
      case 'v': mostrar = !mostrar; Serial.println(mostrar ? F("Sensores en vivo: ON") : F("Sensores en vivo: OFF")); break;
      case 'c': calibrar(); break;
      case 'i': escanearI2C(); break;
      case 'm':
        if (!calibrado) { Serial.println(F("Primero calibra con c")); break; }
        modoSeguir = !modoSeguir; velocidad = velCal;
        if (!modoSeguir) frenar();
        Serial.println(modoSeguir ? F("MODO SEGUIR: ON") : F("MODO SEGUIR: OFF"));
        break;
    }
  }

  revisarTopes();
  actualizarPos();
  if (modoSeguir) seguir();
  revisarTopes();

  // Gol: el IR ve la bola (se cuenta una sola vez por ingreso)
  bool g = golDetectado();
  if (g && !golAntes && millis() - ultimoGol > 1500) { goles++; ultimoGol = millis(); Serial.print(F("GOL! Total: ")); Serial.println(goles); }
  golAntes = g;

  // Seguridad en modo manual: sin teclas, se detiene
  if (!modoSeguir && dir != 0 && millis() - ultimo > WATCHDOG_MS) frenar();

  if (mostrar && millis() - tMostrar > 300) { tMostrar = millis(); estado(); }

  // Senal de vida: un punto cada 2 s cuando no se muestran los sensores
  if (!mostrar && millis() - tVivo > 2000) { tVivo = millis(); Serial.print('.'); }
}