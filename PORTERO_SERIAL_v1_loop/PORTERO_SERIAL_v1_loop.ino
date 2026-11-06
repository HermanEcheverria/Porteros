/*
  PORTERO CON OBJETIVO POR SERIAL — Porteros Robot
  La laptop (vision_cancha.py) ve la bola, predice donde cruza la porteria y manda:
    T<mm>\n   objetivo del carro en mm desde el tope izquierdo (0..RECORRIDO_MM)
    K\n       golpe del solenoide
  Sin objetivos nuevos por WATCHDOG_AUTO_MS, el carro se frena.

  Conexiones:
    Motor:      L298N IN3 -> 5, IN4 -> 4        (jumper ENB puesto)
    Solenoide (segun MODO_SOLENOIDE):
      SOL_L298N:      L298N IN1 -> 9, IN2 -> 10 (jumper ENA), solenoide en OUT1/OUT2.
                      Golpe DEBIL: el L298N pierde 2-4 V y da max ~2 A.
      SOL_RELE_ALTO / SOL_RELE_BAJO: modulo de rele 12 V de 1 canal:
                      VCC -> +12V, GND -> GND (comun con el Arduino), IN -> 9;
                      COM -> +12V, NO -> solenoide, solenoide -> GND (12 V directos = golpe fuerte).
                      ALTO o BAJO: con que nivel en IN se activa (probar tocando IN con GND o con 5V).
    Final izq:  NO -> 2, C -> 12                Final der: NO -> 3, C -> 11
    IR de gol:  OUT -> A3

  Teclas manuales (control WASD o Monitor Serie a 115200):
    a / d  mover   x  soltar   espacio  freno   w / s  velocidad
    k / K  golpe   c  calibrar   p  estado   v  estado en vivo (on/off)

  Pantalla LCD 1602 con modulo I2C (opcional, solo en uno de los porteros): SDA -> A4, SCL -> A5, VCC -> 5V.
  Si esta conectada se detecta sola (direccion 0x27 o 0x3F). La laptop le manda:
    V<izq>,<der>\n   goles de cada jugador (linea 1)     X<texto>\n   mensaje (linea 2, max 16 letras)
  P<ms>\n   duracion del golpe en ms (20 a 600), para ajustarla sin volver a cargar el programa
*/
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// ===== AJUSTA ESTOS VALORES =====
const bool INVERTIR_MOTOR     = true;  // sentido inicial del motor; si esta al reves, la calibracion lo corrige sola
const bool CALIBRAR_AL_INICIO = true;  // al encender (o al abrir el puerto) calibra solo
const int  RECORRIDO_MM       = 210;   // distancia entre los dos finales (medida con la camara)
const int  PWM_CAL            = 190;   // PWM inicial de calibracion = velocidad en automatico
const int  VEL_MIN_MM_S       = 400;   // si el carro va mas lento, la calibracion sube el PWM (hasta 255)
                                       // (a 255 iba a ~1 m/s y se trababa contra los finales de carrera)
const int  OBJ_MIN_MM         = 25;    // objetivos permitidos en automatico: sin tocar los topes
const int  OBJ_MAX_MM         = 205;   // (medido: el tope izquierdo real queda en ~22 de la estimacion)
const int  PWM_MIN            = 90;    // minimo para 'w'/'s' en modo manual
const int  ZONA_MUERTA_MM     = 8;     // error aceptable: aqui se frena
const int  INERCIA_MM         = 0;     // lo que sigue avanzando el carro despues de frenar a toda velocidad
                                       // (se frena antes por esta distancia; medir con la camara)

// ===== Pines =====
const int M_IN3 = 5, M_IN4 = 4;
const int SOL_IN1 = 9, SOL_IN2 = 10;   // antes 8 y 7: el pin 8 no mandaba senal
const int FIN_IZQ = 2, FIN_DER = 3, GND_IZQ = 12, GND_DER = 11;
const int IR_GOL = A3;

const unsigned long WATCHDOG_MS = 400, WATCHDOG_AUTO_MS = 500, ESPERA_GOLPE_MS = 500;
unsigned long pulsoMs = 250;   // duracion del golpe: con el bloque de madera el embolo necesita ~250 ms
                               // para salir completo (con 80-120 ms solo hacia un movimiento pequeno)
unsigned long finGolpe = 0;    // el golpe no detiene el programa: se apaga solo en loop()
bool golpeActivo = false;

const int SOL_L298N = 0, SOL_RELE_ALTO = 1, SOL_RELE_BAJO = 2;
const int MODO_SOLENOIDE = SOL_L298N;  // cambiar al conectar el modulo de rele

int dir = 0;                 // -1 hacia izquierda, 0 parado, 1 hacia derecha
bool invertido = INVERTIR_MOTOR;  // sentido real del motor (lo ajusta calibrar())
int velocidad = 160;         // PWM actual
unsigned long ultimo = 0, ultimoGolpe = 0, tPrev = 0, tMostrar = 0, tVivo = 0, ultimoGol = 0, ultimoT = 0;
bool modoAuto = false, calibrado = false, mostrar = false, golAntes = false;
float posMM = 0, velMMms = 0;  // velMMms = velocidad medida a pwmCal
int pwmCal = PWM_CAL;          // PWM de trabajo de este portero (lo ajusta calibrar())
int objetivo = RECORRIDO_MM / 2;
int goles = 0;

// Lector de "T<mm>\n" sin bloquear
bool leyendoT = false;
int numT = 0;

// Pantalla LCD (nullptr si no hay) y lector de las lineas "V..." y "X..."
LiquidCrystal_I2C* lcd = nullptr;
char tipoLinea = 0;          // 'V' o 'X' mientras se lee una linea; 0 si no
char linea[17];
int nLinea = 0;

void lcdIniciar() {
  Wire.begin();
  Wire.setWireTimeout(3000, true);   // nunca quedarse trabado si la pantalla falla
  const byte dirs[] = {0x27, 0x3F};
  for (byte a : dirs) {
    Wire.beginTransmission(a);
    if (Wire.endTransmission() == 0) {
      lcd = new LiquidCrystal_I2C(a, 16, 2);
      lcd->init(); lcd->backlight();
      Serial.print(F("LCD en 0x")); Serial.println(a, HEX);
      return;
    }
  }
  Serial.println(F("Sin pantalla LCD"));
}

void lcdLinea(byte fila, const char* t) {
  if (!lcd) return;
  char b[17];
  snprintf(b, sizeof(b), "%-16s", t);   // rellena con espacios para borrar lo anterior
  lcd->setCursor(0, fila); lcd->print(b);
}

void procesarLinea() {
  linea[nLinea] = 0;
  if (tipoLinea == 'V') {                // "V10,9": vidas izquierda, derecha
    char* coma = strchr(linea, ',');
    int vi = atoi(linea), vd = coma ? atoi(coma + 1) : 0;
    char b[17]; snprintf(b, sizeof(b), "IZQ:%2d  DER:%2d", vi, vd);
    lcdLinea(0, b);
  } else if (tipoLinea == 'X') {
    lcdLinea(1, linea);
  } else if (tipoLinea == 'P') {
    pulsoMs = constrain(atoi(linea), 20, 600);
    Serial.print(F("Pulso del golpe: ")); Serial.print(pulsoMs); Serial.println(F(" ms"));
  }
  tipoLinea = 0;
}

bool topeConfirmado(int pin);
bool izq() { return topeConfirmado(FIN_IZQ); }
bool der() { return topeConfirmado(FIN_DER); }
bool golDetectado() { return digitalRead(IR_GOL) == LOW; }

void salidaMotor(int d) {
  if (invertido) d = -d;
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
  actualizarPos();                     // cuenta lo recorrido antes de parar
  dir = 0;
  digitalWrite(M_IN4, HIGH); analogWrite(M_IN3, 255);
  delay(40);
  salidaMotor(0);
  tPrev = millis();
}
// Lectura confirmada de un tope: debe leerse presionado 3 veces seguidas (filtra el ruido del motor)
bool topeConfirmado(int pin) {
  for (int i = 0; i < 3; i++) { if (digitalRead(pin) != LOW) return false; delayMicroseconds(300); }
  return true;
}
void revisarTopes() {
  if (dir < 0 && izq()) { frenar(); posMM = 0;            if (!modoAuto) Serial.println(F("TOPE IZQUIERDO")); }
  if (dir > 0 && der()) { frenar(); posMM = RECORRIDO_MM; if (!modoAuto) Serial.println(F("TOPE DERECHO")); }
}

// Enciende o apaga el solenoide segun como este conectado
void solenoide(bool on) {
  if (MODO_SOLENOIDE == SOL_RELE_BAJO) {
    // Modulo que se activa con LOW: nunca se manda HIGH (su IN puede estar a 12 V);
    // apagado = pin en alta impedancia, encendido = pin en LOW
    if (on) { pinMode(SOL_IN1, OUTPUT); digitalWrite(SOL_IN1, LOW); }
    else    { pinMode(SOL_IN1, INPUT); }
  } else {
    pinMode(SOL_IN1, OUTPUT); digitalWrite(SOL_IN1, on ? HIGH : LOW);
  }
}

void golpe() {
  if (golpeActivo || millis() - ultimoGolpe < pulsoMs + ESPERA_GOLPE_MS) return;   // dejar que regrese el embolo
  ultimoGolpe = millis();
  solenoide(true); finGolpe = millis() + pulsoMs; golpeActivo = true;
  if (!modoAuto) Serial.println(F("GOLPE"));
}

// Velocidad estimada para el PWM actual: lineal entre PWM_MIN (0 mm/ms) y pwmCal (velMMms)
float velActual() {
  if (velocidad <= PWM_MIN) return 0;
  return velMMms * (velocidad - PWM_MIN) / (float)(pwmCal - PWM_MIN);
}

// Posicion por tiempo (calibracion) corregida con los topes
void actualizarPos() {
  unsigned long now = millis();
  if (calibrado) posMM += dir * velActual() * (now - tPrev);
  tPrev = now;
  if (izq()) posMM = 0;
  if (der()) posMM = RECORRIDO_MM;
  posMM = constrain(posMM, 0, RECORRIDO_MM);
}

void estado() {
  Serial.print(F("Fin izq: ")); Serial.print(izq() ? F("SI") : F("no"));
  Serial.print(F(" | Fin der: ")); Serial.print(der() ? F("SI") : F("no"));
  Serial.print(F(" | IR gol: ")); Serial.print(golDetectado() ? F("BOLA") : F("libre"));
  Serial.print(F(" | Portero: "));
  if (calibrado) { Serial.print((int)posMM); Serial.print(F(" mm")); } else Serial.print(F("sin calibrar"));
  Serial.print(F(" | Objetivo: ")); Serial.print(modoAuto ? objetivo : -1);
  Serial.print(F(" | Goles: ")); Serial.println(goles);
}

// Espera a llegar al tope buscado: TOPE_OK, TOPE_TIEMPO (no llego) o TOPE_CONTRARIO (el carro termino
// en el tope contrario: motor con los cables invertidos). En ese caso frena enseguida en vez de
// empujar contra el tope hasta que se acabe el tiempo.
const int TOPE_OK = 0, TOPE_TIEMPO = 1, TOPE_CONTRARIO = 2, TOPE_FALLA = 3;
int esperarTope(bool (*tope)(), bool (*contrario)(), unsigned long maxMs) {
  unsigned long t0 = millis();
  bool solto = !contrario();             // el tope contrario cuenta solo si antes se solto
  while (!tope()) {
    if (millis() - t0 > maxMs) { frenar(); return TOPE_TIEMPO; }   // no salio o no llego: carro lento
    if (!contrario()) solto = true;
    else if (solto) { frenar(); return TOPE_CONTRARIO; }
  }
  frenar();
  return TOPE_OK;
}

// Calibra y ajusta este portero solo, para que el mismo firmware sirva en los dos:
//  - si el carro va al lado contrario, invierte el sentido del motor (cables al reves) y repite;
//  - si no llega al tope o va mas lento que VEL_MIN_MM_S, sube el PWM de 30 en 30 (hasta 255) y repite.
void calibrar() {
  pwmCal = PWM_CAL;
  bool yaInvertido = false;
  for (int intento = 0; intento < 6; intento++) {
    int r = calibrarUnaVez();
    if (r == TOPE_FALLA) return;
    if (r == TOPE_CONTRARIO) {
      if (yaInvertido) { Serial.println(F("ERROR: el carro va al lado contrario en ambos sentidos (revisar finales de carrera)")); return; }
      invertido = !invertido; yaInvertido = true;
      Serial.println(F("Motor al reves: corrijo el sentido y repito"));
    } else {
      bool lento = (r == TOPE_TIEMPO) || velMMms * 1000 < VEL_MIN_MM_S;
      if (!lento || pwmCal >= 255) {
        if (r == TOPE_OK) { Serial.print(F("PWM de trabajo: ")); Serial.println(pwmCal); Serial.println(F("LISTO")); }
        return;
      }
      pwmCal = min(255, pwmCal + 30);
      Serial.print(F("Carro lento: subo el PWM a ")); Serial.println(pwmCal);
    }
    delay(300);
  }
}

int calibrarUnaVez() {
  modoAuto = false;
  velocidad = pwmCal;
  int r;
  if (izq() && der()) {                 // el carro no puede estar en los dos extremos
    Serial.println(F("ERROR: los dos finales de carrera se leen presionados (cables en corto o mal conectados)"));
    return TOPE_FALLA;
  }
  Serial.println(F("Calibrando: voy al final izquierdo..."));
  if (!izq()) {
    motor(-1);
    r = esperarTope(izq, der, 4000);
    if (r == TOPE_TIEMPO) Serial.println(F("ERROR: no llegue al final izquierdo"));
    if (r != TOPE_OK) return r;
  }
  delay(300);
  Serial.println(F("Midiendo hasta el final derecho..."));
  unsigned long t0 = millis();
  motor(1);
  r = esperarTope(der, izq, 4000);
  if (r == TOPE_TIEMPO) Serial.println(F("ERROR: no llegue al final derecho"));
  if (r != TOPE_OK) return r;
  unsigned long T = millis() - t0;
  if (T < 150) {                        // ningun carro cruza el riel tan rapido: lectura falsa de un tope
    Serial.print(F("ERROR: recorrido imposible (")); Serial.print(T);
    Serial.println(F(" ms). Revisa los cables de los finales de carrera"));
    return TOPE_FALLA;
  }
  velMMms = (float)RECORRIDO_MM / T;
  calibrado = true; posMM = RECORRIDO_MM;
  Serial.print(F("Recorrido en ")); Serial.print(T); Serial.print(F(" ms = "));
  Serial.print(velMMms * 1000, 0); Serial.println(F(" mm/s"));
  delay(300);
  // Al centro contando la posicion igual que en automatico: mientras el final derecho siga
  // presionado la posicion queda en RECORRIDO_MM, y se empieza a contar desde donde lo suelta
  // (un punto fijo). Con una espera por tiempo el error cambiaba en cada calibracion.
  tPrev = millis();
  motor(-1);
  unsigned long t1 = millis();
  while (posMM > RECORRIDO_MM / 2 && millis() - t1 < 3000) actualizarPos();
  frenar();
  while (Serial.available()) Serial.read();   // descarta lo que llego mientras calibraba
  leyendoT = false; tipoLinea = 0;
  return TOPE_OK;
}

// Control todo-o-nada: siempre a pwmCal (la unica velocidad calibrada, la posicion por tiempo
// solo es confiable ahi) y freno al llegar. Con PWM bajo el motor casi no avanza y la estimacion falla.
void controlar() {
  float err = objetivo - posMM;
  float margen = ZONA_MUERTA_MM + (dir != 0 ? INERCIA_MM : 0);   // en marcha: frenar antes por la inercia
  if (fabs(err) <= margen) {
    if (dir != 0) {
      int d = dir;
      frenar();
      posMM = constrain(posMM + d * INERCIA_MM, 0, RECORRIDO_MM);  // lo que avanza mientras frena
    }
    return;
  }
  int d = err > 0 ? 1 : -1;
  if (dir != d || velocidad != pwmCal) {
    actualizarPos();                      // cerrar el tramo anterior antes de cambiar
    velocidad = pwmCal;
    motor(d);
  }
}

void recibirObjetivo(int mm) {
  if (!calibrado) return;
  objetivo = constrain(mm, OBJ_MIN_MM, OBJ_MAX_MM);   // sin chocar con los topes
  ultimoT = millis();
  modoAuto = true;
}

void comando(char c) {
  // Lectura de V... y X...: se guarda la linea hasta el fin de linea
  if (tipoLinea) {
    if (c == '\n' || c == '\r') procesarLinea();
    else if (nLinea < 16) linea[nLinea++] = c;
    return;
  }
  // Lectura de T<mm>: los digitos se acumulan hasta el fin de linea
  if (leyendoT) {
    if (c >= '0' && c <= '9') { numT = numT * 10 + (c - '0'); if (numT > 9999) leyendoT = false; return; }
    leyendoT = false;
    if (c == '\n' || c == '\r') { recibirObjetivo(numT); return; }
    // otro caracter: la linea venia cortada, se descarta y se procesa el caracter
  }
  switch (c) {
    case 'T': leyendoT = true; numT = 0; break;
    case 'V': case 'X': case 'P': tipoLinea = c; nLinea = 0; break;
    case 'K': case 'k': golpe(); break;
    case 'j':                                // diagnostico: solenoide encendido 1 s (para medir con multimetro)
      modoAuto = false; frenar();
      Serial.println(F("SOLENOIDE ON 1 s"));
      solenoide(true); delay(1000); solenoide(false);
      Serial.println(F("SOLENOIDE OFF"));
      break;
    case 'a': case 'd':
      modoAuto = false;
      ultimo = millis();
      { int d = (c == 'a') ? -1 : 1; if (dir != d) { motor(d); if (dir == 0) Serial.println(F("Bloqueado por el tope")); else Serial.println(d < 0 ? F("<- izquierda") : F("-> derecha")); } }
      break;
    case 'x': if (!modoAuto && dir != 0) { actualizarPos(); dir = 0; salidaMotor(0); } break;
    case ' ': modoAuto = false; frenar(); Serial.println(F("freno")); break;
    case 'w': if (!modoAuto) { velocidad = min(255, velocidad + 15); Serial.print(F("velocidad ")); Serial.println(velocidad); } break;
    case 's': if (!modoAuto) { velocidad = max(PWM_MIN, velocidad - 15); Serial.print(F("velocidad ")); Serial.println(velocidad); } break;
    case 'p': estado(); break;
    case 'v': mostrar = !mostrar; Serial.println(mostrar ? F("Estado en vivo: ON") : F("Estado en vivo: OFF")); break;
    case 'c': calibrar(); break;
  }
}

void setup() {
  pinMode(M_IN3, OUTPUT); pinMode(M_IN4, OUTPUT); salidaMotor(0);
  solenoide(false); pinMode(SOL_IN2, OUTPUT); digitalWrite(SOL_IN2, LOW);
  pinMode(GND_IZQ, OUTPUT); digitalWrite(GND_IZQ, LOW);
  pinMode(GND_DER, OUTPUT); digitalWrite(GND_DER, LOW);
  pinMode(FIN_IZQ, INPUT_PULLUP); pinMode(FIN_DER, INPUT_PULLUP);
  pinMode(IR_GOL, INPUT);
  Serial.begin(115200);
  delay(1500);
  Serial.println(F("=== PORTERO SERIAL ==="));
  lcdIniciar();
  lcdLinea(0, "PORTEROS ROBOT");
  lcdLinea(1, "Calibrando...");
  if (CALIBRAR_AL_INICIO) calibrar();
  else Serial.println(F("Presiona c para calibrar"));
  lcdLinea(1, calibrado ? "Listo" : "Sin calibrar");
  golAntes = golDetectado();
  tPrev = millis();
}

void loop() {
  while (Serial.available()) comando(Serial.read());
  if (golpeActivo && (long)(millis() - finGolpe) >= 0) { solenoide(false); golpeActivo = false; }

  revisarTopes();
  actualizarPos();
  if (modoAuto) {
    if (millis() - ultimoT > WATCHDOG_AUTO_MS) { modoAuto = false; frenar(); Serial.println(F("SIN OBJETIVO: freno")); }
    else controlar();
  }
  revisarTopes();

  // El gol lo cuenta la camara (vision_cancha.py): el sensor IR daba lecturas falsas.

  // Seguridad en modo manual: sin teclas, se detiene
  if (!modoAuto && dir != 0 && millis() - ultimo > WATCHDOG_MS) frenar();

  if (mostrar && millis() - tMostrar > 300) { tMostrar = millis(); estado(); }
  if (!mostrar && !modoAuto && millis() - tVivo > 2000) { tVivo = millis(); Serial.print('.'); }
}
