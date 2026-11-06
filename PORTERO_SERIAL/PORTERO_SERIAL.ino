/*
  PORTERO ROBOT con FreeRTOS — Sistemas Informaticos en Tiempo Real (UNIS)
  ---------------------------------------------------------------------------
  La laptop (vision_cancha.py) ve la bola con la camara, predice donde cruza la porteria y manda
  por serial (115200 baud):
    T<mm>\n     objetivo del carro en mm desde el tope izquierdo (0..RECORRIDO_MM)
    K\n         golpe del solenoide
    V<i>,<d>\n  marcador para la LCD (linea 1)     X<texto>\n  mensaje para la LCD (linea 2)
    P<ms>\n     duracion del golpe (20..600 ms)
  Teclas de prueba (Monitor Serie): a/d mover, x soltar, espacio freno, w/s velocidad, k golpe,
    j solenoide 1 s, c calibrar, p estado, v estado en vivo, m mediciones de tiempo real.

  ORGANIZACION EN FreeRTOS (Arduino_FreeRTOS 11.1; tick = 16 ms con el watchdog del ATmega328P)
    tControl     prio 3  periodo 1 tick, o al instante cuando la despierta un evento (ISR de un
                         final de carrera, objetivo nuevo u orden). UNICA duena del motor:
                         calibracion, posicion estimada, control y proteccion de topes.
    Temporizador prio 3  (tarea de temporizadores del kernel) apaga el solenoide al terminar el golpe:
                         el actuador nunca queda energizado aunque otra tarea se atrase.
    tSerial      prio 2  periodo 1 tick: decodifica los mensajes de la laptop y los reparte con
                         colas y notificaciones; ordena el golpe.
    Ociosa       prio 0  loop() corre como gancho de la tarea ociosa: supervision (watchdogs, fallo de
                         topes), pantalla LCD por I2C (lenta) y reportes. Solo usa llamadas que no
                         bloquean. Se hizo asi porque el Uno tiene 2 KB de RAM: cada tarea extra cuesta
                         ~200 bytes y la ociosa ya tiene su pila de 192 bytes reservada.
  COMUNICACION Y SINCRONIZACION
    colaObjetivo  buzon de 1 elemento (xQueueOverwrite): siempre el objetivo mas nuevo, nunca uno viejo.
    colaOrden     cola de 4 char con ordenes para tControl (a, d, x, espacio, w, s, c y S = freno de seguridad).
    colaLCD       cola de 2 mensajes hacia la pantalla.
    mtxSerial     mutex (con herencia de prioridad) para que dos tareas no mezclen texto en el puerto.
    Notificacion directa ISR -> tControl y tSerial -> tControl (despierta sin esperar el tick).
    Secciones criticas para copiar variables de varios bytes que comparten tareas e ISR.

  Conexiones:
    Motor:      L298N #1  IN -> 5 (PWM), IN -> 4
    Solenoide:  L298N #2  IN1 -> 9, IN2 -> 10, solenoide en OUT1/OUT2 (fuente propia de 12 V)
    Final izq:  NO -> 2 (INT0), C -> 12      Final der: NO -> 3 (INT1), C -> 11
    LCD 1602 I2C (opcional): SDA -> A4, SCL -> A5 (direccion 0x27 o 0x3F, se detecta sola)
  Version anterior sin RTOS (todo en loop): carpeta PORTERO_SERIAL_v1_loop.
*/
#include <Arduino_FreeRTOS.h>
#include <queue.h>
#include <semphr.h>
#include <timers.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// ===== AJUSTA ESTOS VALORES =====
const bool INVERTIR_MOTOR     = true;  // sentido inicial; si esta al reves, la calibracion lo corrige sola
const int  RECORRIDO_MM       = 210;   // distancia entre los dos finales (medida con la camara)
const int  PWM_CAL            = 190;   // PWM inicial de calibracion = velocidad en automatico
const int  VEL_MIN_MM_S       = 400;   // si el carro va mas lento, la calibracion sube el PWM (hasta 255)
const int  OBJ_MIN_MM         = 15;    // objetivos permitidos en automatico: sin tocar los topes (antes 25; con la ISR de topes el freno es inmediato)
const int  OBJ_MAX_MM         = 205;
const int  PWM_MIN            = 90;    // minimo para 'w'/'s' en modo manual
const int  ZONA_MUERTA_MM     = 8;     // error aceptable: aqui se frena

// ===== Pines =====
const int M_IN3 = 5, M_IN4 = 4;
const int SOL_IN1 = 9, SOL_IN2 = 10;
const int FIN_IZQ = 2, FIN_DER = 3, GND_IZQ = 12, GND_DER = 11;

// ===== Tiempos =====
const unsigned long WATCHDOG_MANUAL_MS = 400, WATCHDOG_AUTO_MS = 500, ESPERA_GOLPE_MS = 500;
const unsigned long PERIODO_SUPERVISION_MS = 100;
#define TICKS(ms) ((TickType_t)(((ms) + portTICK_PERIOD_MS - 1) / portTICK_PERIOD_MS))   // redondea hacia arriba

// ===== Estado del portero =====
enum Estado : uint8_t { INICIALIZACION, ESPERA, AUTOMATICO, MANUAL, FALLO };
volatile Estado estado = INICIALIZACION;

// Variables de tControl (las otras tareas solo las leen, dentro de una seccion critica)
int dir = 0;                     // -1 izquierda, 0 parado, 1 derecha
bool invertido = INVERTIR_MOTOR;
int velocidad = PWM_CAL;
int pwmCal = PWM_CAL;
bool calibrado = false;
float posMM = 0, velMMms = 0;
int objetivo = RECORRIDO_MM / 2;
unsigned long tPrev = 0;
volatile unsigned long ultimoT = 0, ultimoManual = 0;

// Golpe (lo usan tSerial y el temporizador)
volatile unsigned int pulsoMs = 250;   // la laptop lo cambia con P<ms>
volatile bool golpeActivo = false;
unsigned long ultimoGolpe = 0;

// Mediciones de tiempo real (micros), se consultan con la tecla m
volatile unsigned long tIsrTope = 0;   // instante de la ultima interrupcion de un tope
volatile unsigned long tObjetivo = 0;  // instante en que tSerial termino de recibir un T
struct Medidas {
  unsigned long topeMax, objetivoMax, cicloMax, periodoMax, serialMax;
  unsigned int ciclos, golpes, golpesIgnorados;
} med = {0, 0, 0, 0, 0, 0, 0, 0};
volatile unsigned int lcdEnviados = 0, lcdPerdidos = 0, lcdEscritos = 0;   // diagnostico de la pantalla
volatile unsigned int pilaOciosa = 999;

// Pedidos de tSerial a la tarea ociosa (los reportes largos se imprimen ahi)
volatile bool pedirEstado = false, pedirMedidas = false, mostrar = false;

// ===== Objetos del RTOS =====
TaskHandle_t hControl, hSerial;
QueueHandle_t colaObjetivo, colaOrden, colaLCD;
SemaphoreHandle_t mtxSerial;
TimerHandle_t tmrGolpe;

struct MsgLCD { char tipo; char texto[17]; };   // tipo 'V' (marcador) o 'X' (mensaje)

// Impresion protegida: una sola tarea a la vez escribe en el puerto
#define CON_SERIAL(codigo) do { xSemaphoreTake(mtxSerial, portMAX_DELAY); codigo; xSemaphoreGive(mtxSerial); } while (0)
void decir(const __FlashStringHelper* s) { CON_SERIAL(Serial.println(s)); }

// Lectura atomica de 4 bytes que otra tarea o una ISR puede estar escribiendo (el AVR es de 8 bits)
unsigned long leer(volatile unsigned long& v) { taskENTER_CRITICAL(); unsigned long x = v; taskEXIT_CRITICAL(); return x; }
void maximo(unsigned long& m, unsigned long x) { if (x >= 1000000UL) return; taskENTER_CRITICAL(); if (x > m) m = x; taskEXIT_CRITICAL(); }

LiquidCrystal_I2C* lcd = nullptr;

// ============================================================================
//  Hardware de bajo nivel
// ============================================================================
bool topeConfirmado(int pin) {   // 3 lecturas seguidas en LOW (filtra el ruido del motor)
  for (int i = 0; i < 3; i++) { if (digitalRead(pin) != LOW) return false; delayMicroseconds(300); }
  return true;
}
bool izq() { return topeConfirmado(FIN_IZQ); }
bool der() { return topeConfirmado(FIN_DER); }

// ISR de los dos finales de carrera (INT0/INT1): solo marca el instante y despierta a tControl
void isrTope() {
  tIsrTope = micros();
  BaseType_t despertar = pdFALSE;
  vTaskNotifyGiveFromISR(hControl, &despertar);
  if (despertar == pdTRUE) portYIELD_FROM_ISR();
}

bool frenando = false;          // freno activo puesto; tControl lo suelta al cumplirse finFreno
unsigned long finFreno = 0;

void salidaMotor(int d) {
  frenando = false;             // cualquier orden nueva al motor reemplaza al freno
  if (invertido) d = -d;
  if (d > 0)      { digitalWrite(M_IN4, LOW);  analogWrite(M_IN3, velocidad); }
  else if (d < 0) { digitalWrite(M_IN4, HIGH); analogWrite(M_IN3, 255 - velocidad); }
  else            { digitalWrite(M_IN4, LOW);  analogWrite(M_IN3, 0); }
}

void solenoide(bool on) { digitalWrite(SOL_IN1, on ? HIGH : LOW); digitalWrite(SOL_IN2, LOW); }

// ============================================================================
//  Golpe: tSerial lo enciende, el temporizador del kernel lo apaga
// ============================================================================
void finGolpe(TimerHandle_t) { solenoide(false); golpeActivo = false; }

void golpe(unsigned int ms) {
  unsigned long ahora = millis();
  // Evita activaciones repetidas: ignora la orden mientras el embolo sale o regresa
  if (golpeActivo || ahora - ultimoGolpe < pulsoMs + ESPERA_GOLPE_MS) { med.golpesIgnorados++; return; }
  ultimoGolpe = ahora;
  golpeActivo = true;
  solenoide(true);
  xTimerChangePeriod(tmrGolpe, TICKS(ms), 0);   // tambien lo arranca; al vencer llama a finGolpe
  med.golpes++;
}

// ============================================================================
//  tControl: motor, posicion, calibracion
// ============================================================================
float velActual() {   // velocidad estimada para el PWM actual (lineal entre PWM_MIN y pwmCal)
  if (velocidad <= PWM_MIN) return 0;
  return velMMms * (velocidad - PWM_MIN) / (float)(pwmCal - PWM_MIN);
}

void actualizarPos() {   // posicion por tiempo (dead reckoning) corregida con los topes
  unsigned long now = millis();
  if (calibrado) posMM += dir * velActual() * (now - tPrev);
  tPrev = now;
  if (izq()) posMM = 0;
  if (der()) posMM = RECORRIDO_MM;
  posMM = constrain(posMM, 0, RECORRIDO_MM);
}

void motor(int d) {
  if (d < 0 && izq()) d = 0;      // nunca empujar contra un tope
  if (d > 0 && der()) d = 0;
  dir = d; salidaMotor(d);
}

void frenar() {
  actualizarPos();
  dir = 0;
  digitalWrite(M_IN4, HIGH); analogWrite(M_IN3, 255);   // freno activo: las dos salidas iguales
  // Sin esperar aqui: tControl suelta el freno en un ciclo posterior (>= 40 ms), asi un objetivo
  // nuevo se atiende enseguida en vez de quedar 48 ms bloqueado.
  frenando = true; finFreno = millis() + 40;
  tPrev = millis();
}

// Proteccion de topes: corta el motor si el carro llego al extremo hacia el que va.
void revisarTopes() {
  bool llego = (dir < 0 && izq()) || (dir > 0 && der());
  if (!llego) return;
  digitalWrite(M_IN4, HIGH); analogWrite(M_IN3, 255);   // primero cortar, luego medir e informar
  maximo(med.topeMax, micros() - leer(tIsrTope));       // latencia ISR -> freno
  int d = dir;
  frenar();
  posMM = d < 0 ? 0 : RECORRIDO_MM;
  if (estado == MANUAL) { if (d < 0) decir(F("TOPE IZQUIERDO")); else decir(F("TOPE DERECHO")); }
}

// Espera el tope buscado SIN espera activa: la tarea duerme hasta que la ISR de un final la despierta
// (o hasta el siguiente tick). TOPE_CONTRARIO = el carro llego al otro extremo (motor al reves).
const int TOPE_OK = 0, TOPE_TIEMPO = 1, TOPE_CONTRARIO = 2, TOPE_FALLA = 3;
int esperarTope(bool (*tope)(), bool (*contrario)(), unsigned long maxMs) {
  unsigned long t0 = millis();
  bool solto = !contrario();
  while (!tope()) {
    if (millis() - t0 > maxMs) { frenar(); return TOPE_TIEMPO; }
    if (!contrario()) solto = true;
    else if (solto) { frenar(); return TOPE_CONTRARIO; }
    ulTaskNotifyTake(pdTRUE, 1);
  }
  frenar();
  return TOPE_OK;
}

// Mensaje para la linea 2 de la LCD. El texto vive en la flash (PSTR): la RAM del Uno no alcanza para todo.
void mensajeLCD(const char* t_P) { MsgLCD m; m.tipo = 'X'; strncpy_P(m.texto, t_P, 16); m.texto[16] = 0; xQueueSend(colaLCD, &m, 0); }

int calibrarUnaVez() {
  velocidad = pwmCal;
  int r;
  if (izq() && der()) {
    decir(F("ERROR: los dos finales de carrera se leen presionados (cables en corto o mal conectados)"));
    return TOPE_FALLA;
  }
  decir(F("Calibrando: voy al final izquierdo..."));
  if (!izq()) {
    motor(-1);
    r = esperarTope(izq, der, 4000);
    if (r == TOPE_TIEMPO) decir(F("ERROR: no llegue al final izquierdo"));
    if (r != TOPE_OK) return r;
  }
  vTaskDelay(TICKS(300));
  decir(F("Midiendo hasta el final derecho..."));
  unsigned long t0 = millis();
  motor(1);
  r = esperarTope(der, izq, 4000);
  if (r == TOPE_TIEMPO) decir(F("ERROR: no llegue al final derecho"));
  if (r != TOPE_OK) return r;
  unsigned long T = millis() - t0;
  if (T < 150) {
    CON_SERIAL(Serial.print(F("ERROR: recorrido imposible (")); Serial.print(T);
               Serial.println(F(" ms). Revisa los cables de los finales de carrera")));
    return TOPE_FALLA;
  }
  velMMms = (float)RECORRIDO_MM / T;
  calibrado = true; posMM = RECORRIDO_MM;
  CON_SERIAL(Serial.print(F("Recorrido en ")); Serial.print(T); Serial.print(F(" ms = "));
             Serial.print((int)(velMMms * 1000)); Serial.println(F(" mm/s")));
  vTaskDelay(TICKS(300));
  // Al centro contando la posicion desde que suelta el final derecho (punto fijo)
  tPrev = millis();
  motor(-1);
  unsigned long t1 = millis();
  while (posMM > RECORRIDO_MM / 2 && millis() - t1 < 3000) { actualizarPos(); vTaskDelay(1); }
  frenar();
  return TOPE_OK;
}

// Calibra y se ajusta solo: invierte el motor si va al reves, sube el PWM si el carro va lento.
void calibrar() {
  estado = INICIALIZACION;
  mensajeLCD(PSTR("Calibrando..."));
  pwmCal = PWM_CAL;
  bool yaInvertido = false, ok = false;
  for (int intento = 0; intento < 6; intento++) {
    int r = calibrarUnaVez();
    if (r == TOPE_FALLA) break;
    if (r == TOPE_CONTRARIO) {
      if (yaInvertido) { decir(F("ERROR: el carro va al lado contrario en ambos sentidos (revisar finales de carrera)")); break; }
      invertido = !invertido; yaInvertido = true;
      decir(F("Motor al reves: corrijo el sentido y repito"));
    } else {
      bool lento = (r == TOPE_TIEMPO) || velMMms * 1000 < VEL_MIN_MM_S;
      if (!lento || pwmCal >= 255) { ok = (r == TOPE_OK); break; }
      pwmCal = min(255, pwmCal + 30);
      CON_SERIAL(Serial.print(F("Carro lento: subo el PWM a ")); Serial.println(pwmCal));
    }
    vTaskDelay(TICKS(300));
  }
  xQueueReset(colaObjetivo); xQueueReset(colaOrden);   // lo que llego mientras calibraba ya es viejo
  if (ok) {
    estado = ESPERA;
    CON_SERIAL(Serial.print(F("PWM de trabajo: ")); Serial.println(pwmCal); Serial.println(F("LISTO")));
    mensajeLCD(PSTR("Listo"));
  } else {
    estado = FALLO;                         // no acepta objetivos hasta calibrar bien (tecla c)
    decir(F("FALLO: sin calibrar. Revisa el carro y presiona c"));
    mensajeLCD(PSTR("FALLO: calibrar"));
  }
}

// Control todo-o-nada a pwmCal (la unica velocidad calibrada) y freno al llegar
void controlar() {
  float err = objetivo - posMM;
  if (fabs(err) <= ZONA_MUERTA_MM) { if (dir != 0) frenar(); return; }
  int d = err > 0 ? 1 : -1;
  if (dir != d || velocidad != pwmCal) { actualizarPos(); velocidad = pwmCal; motor(d); }
}

void ordenManual(char c) {
  switch (c) {
    case 'a': case 'd': {
      if (estado != FALLO) estado = MANUAL;     // en FALLO se puede mover a mano, pero no jugar
      ultimoManual = millis();
      int d = (c == 'a') ? -1 : 1;
      if (dir != d) { motor(d); if (dir == 0) decir(F("Bloqueado por el tope")); else if (d < 0) decir(F("<- izquierda")); else decir(F("-> derecha")); }
      break;
    }
    case 'x': if (estado != AUTOMATICO && dir != 0) { actualizarPos(); dir = 0; salidaMotor(0); } break;
    case ' ': if (estado == AUTOMATICO || estado == MANUAL) estado = ESPERA; frenar(); decir(F("freno")); break;
    case 'S': if (dir != 0) frenar(); if (estado == AUTOMATICO || estado == MANUAL) estado = ESPERA; break;   // de la supervision
    case 'w': velocidad = min(255, velocidad + 15); CON_SERIAL(Serial.print(F("velocidad ")); Serial.println(velocidad)); break;
    case 's': velocidad = max(PWM_MIN, velocidad - 15); CON_SERIAL(Serial.print(F("velocidad ")); Serial.println(velocidad)); break;
    case 'c': if (dir != 0) frenar(); calibrar(); break;
  }
}

void tareaControl(void*) {
  calibrar();                                     // INICIALIZACION -> ESPERA (o FALLO)
  tPrev = millis();
  unsigned long anterior = micros();
  for (;;) {
    ulTaskNotifyTake(pdTRUE, 1);                  // periodo: 1 tick, o antes si hay un evento
    unsigned long inicio = micros();
    maximo(med.periodoMax, inicio - anterior); anterior = inicio;
    if (frenando && (long)(millis() - finFreno) >= 0) salidaMotor(0);   // termina el freno activo

    char c;
    while (xQueueReceive(colaOrden, &c, 0) == pdTRUE) ordenManual(c);

    int nuevo;
    if (xQueueReceive(colaObjetivo, &nuevo, 0) == pdTRUE && calibrado && estado != FALLO && estado != INICIALIZACION) {
      objetivo = constrain(nuevo, OBJ_MIN_MM, OBJ_MAX_MM);
      ultimoT = millis();
      if (estado != AUTOMATICO) { estado = AUTOMATICO; velocidad = pwmCal; }
      maximo(med.objetivoMax, micros() - leer(tObjetivo));   // latencia T recibido -> control
    }

    revisarTopes();
    actualizarPos();
    if (estado == AUTOMATICO) controlar();
    revisarTopes();

    maximo(med.cicloMax, micros() - inicio);
    taskENTER_CRITICAL(); med.ciclos++; taskEXIT_CRITICAL();
  }
}

// ============================================================================
//  tSerial: decodifica los mensajes de la laptop
// ============================================================================
void mandarOrden(char c) {
  xQueueSend(colaOrden, &c, 0);
  xTaskNotifyGive(hControl);              // que la atienda ya, sin esperar el tick
}

void tareaSerial(void*) {
  bool leyendoT = false; int numT = 0;
  char tipoLinea = 0; MsgLCD msg; int nLinea = 0;
  for (;;) {
    unsigned long inicio = micros();
    while (Serial.available()) {
      char c = Serial.read();
      if (tipoLinea) {                                    // V..., X..., P... hasta el fin de linea
        if (c == '\n' || c == '\r') {
          msg.texto[nLinea] = 0;
          if (tipoLinea == 'P') {
            pulsoMs = constrain(atoi(msg.texto), 20, 600);
            CON_SERIAL(Serial.print(F("Pulso del golpe: ")); Serial.print(pulsoMs); Serial.println(F(" ms")));
          } else {
            msg.tipo = tipoLinea;
            if (xQueueSend(colaLCD, &msg, 0) == pdTRUE) lcdEnviados++; else lcdPerdidos++;
          }
          tipoLinea = 0;
        } else if (nLinea < 16) msg.texto[nLinea++] = c;
        continue;
      }
      if (leyendoT) {                                     // T<mm>
        if (c >= '0' && c <= '9') { numT = numT * 10 + (c - '0'); if (numT > 9999) leyendoT = false; continue; }
        leyendoT = false;
        if (c == '\n' || c == '\r') {
          tObjetivo = micros();
          xQueueOverwrite(colaObjetivo, &numT);           // buzon: solo importa el mas nuevo
          xTaskNotifyGive(hControl);
          continue;
        }
      }
      switch (c) {
        case 'T': leyendoT = true; numT = 0; break;
        case 'V': case 'X': case 'P': tipoLinea = c; nLinea = 0; break;
        case 'K': case 'k': golpe(pulsoMs); break;
        case 'j': mandarOrden(' '); decir(F("SOLENOIDE 1 s")); golpe(1000); break;
        case 'a': case 'd': case 'x': case ' ': case 'w': case 's': case 'c': mandarOrden(c); break;
        case 'p': pedirEstado = true; break;
        case 'v': mostrar = !mostrar; break;
        case 'm': pedirMedidas = true; break;
      }
    }
    maximo(med.serialMax, micros() - inicio);
    vTaskDelay(1);                                        // el UART guarda 64 bytes entre ticks
  }
}

// ============================================================================
//  Tarea ociosa (loop): supervision, LCD y reportes. NUNCA bloquea.
// ============================================================================
// La tarea ociosa tiene solo 192 B de pila (y ahi caen tambien las interrupciones): se evita
// snprintf (vfprintf usa mucha pila) y Serial.print(numero) (buffer de 33 B).
void num(long v) {
  char b[12]; byte i = sizeof(b) - 1; b[i] = 0;
  bool neg = v < 0; unsigned long u = neg ? -v : v;
  do { b[--i] = '0' + u % 10; u /= 10; } while (u);
  if (neg) b[--i] = '-';
  Serial.print(b + i);
}

bool tomarSerial() { return xSemaphoreTake(mtxSerial, 0) == pdTRUE; }   // si esta ocupado, otra vuelta

const __FlashStringHelper* nombreEstado(Estado e) {
  switch (e) { case INICIALIZACION: return F("INICIALIZACION"); case ESPERA: return F("ESPERA");
               case AUTOMATICO: return F("AUTOMATICO"); case MANUAL: return F("MANUAL"); default: return F("FALLO"); }
}

bool imprimirEstado() {
  if (!tomarSerial()) return false;
  taskENTER_CRITICAL();
  Estado e = estado; int p = (int)posMM, o = objetivo; bool cal = calibrado;
  taskEXIT_CRITICAL();
  Serial.print(F("Estado: ")); Serial.print(nombreEstado(e));
  Serial.print(F(" | Fin izq: ")); Serial.print(izq() ? F("SI") : F("no"));
  Serial.print(F(" | Fin der: ")); Serial.print(der() ? F("SI") : F("no"));
  Serial.print(F(" | Portero: "));
  if (cal) { num(p); Serial.print(F(" mm")); } else Serial.print(F("sin calibrar"));
  Serial.print(F(" | Objetivo: ")); num(e == AUTOMATICO ? o : -1); Serial.println();
  xSemaphoreGive(mtxSerial);
  return true;
}

bool imprimirMedidas() {
  if (!tomarSerial()) return false;
  taskENTER_CRITICAL();
  Medidas m = med;
  med = {0, 0, 0, 0, 0, 0, 0, 0};
  taskEXIT_CRITICAL();
  Serial.println(F("--- Tiempo real: maximos desde la ultima m (us) ---"));
  Serial.print(F("Periodo de tControl: ")); num(m.periodoMax); Serial.println();
  Serial.print(F("Ejecucion de tControl: ")); num(m.cicloMax); Serial.println();
  Serial.print(F("Ejecucion de tSerial: ")); num(m.serialMax); Serial.println();
  Serial.print(F("Final de carrera (ISR) -> freno: ")); num(m.topeMax); Serial.println();
  Serial.print(F("T recibido -> control: ")); num(m.objetivoMax); Serial.println();
  Serial.print(F("Ciclos de control: ")); num(m.ciclos);
  Serial.print(F(" | golpes: ")); num(m.golpes); Serial.print(F(" (ignorados ")); num(m.golpesIgnorados); Serial.println(')');
  Serial.print(F("LCD: recibidos ")); num(lcdEnviados); Serial.print(F(" perdidos ")); num(lcdPerdidos);
  Serial.print(F(" escritos ")); num(lcdEscritos); Serial.print(F(" | pila libre ociosa ")); num(pilaOciosa); Serial.println();
  Serial.print(F("Pila libre (bytes) control/serial: "));
  num(uxTaskGetStackHighWaterMark(hControl)); Serial.print('/'); num(uxTaskGetStackHighWaterMark(hSerial)); Serial.println();
  xSemaphoreGive(mtxSerial);
  return true;
}

void lcdLinea(byte fila, const char* t) {
  if (!lcd) return;
  lcd->setCursor(0, fila);
  byte n = 0;
  while (n < 16 && t[n]) lcd->write(t[n++]);
  while (n++ < 16) lcd->write(' ');           // rellena con espacios para borrar lo anterior
}

void supervisar() {
  taskENTER_CRITICAL();
  Estado e = estado; int d = dir; unsigned long uT = ultimoT, uM = ultimoManual;
  taskEXIT_CRITICAL();
  unsigned long ahora = millis();
  if (e == AUTOMATICO && ahora - uT > WATCHDOG_AUTO_MS) {          // la laptop dejo de mandar objetivos
    mandarOrden('S');
    if (tomarSerial()) { Serial.println(F("SIN OBJETIVO: freno")); xSemaphoreGive(mtxSerial); }
  }
  if ((e == MANUAL || e == FALLO) && d != 0 && ahora - uM > WATCHDOG_MANUAL_MS) mandarOrden('S');   // soltaron la tecla
  if (e != FALLO && e != INICIALIZACION && izq() && der()) {         // imposible: cables en corto
    mandarOrden('S'); estado = FALLO;
    if (tomarSerial()) { Serial.println(F("FALLO: los dos finales presionados. Presiona c al corregir")); xSemaphoreGive(mtxSerial); }
  }
}

void loop() {   // gancho de la tarea ociosa: corre solo cuando ninguna otra tarea tiene trabajo
  static unsigned long tSup = 0, tMostrar = 0, tVivo = 0;
  unsigned long ahora = millis();
  if (ahora - tSup >= PERIODO_SUPERVISION_MS) { tSup = ahora; supervisar(); }

  MsgLCD m;
  if (xQueueReceive(colaLCD, &m, 0) == pdTRUE) {      // 0 = no esperar
    lcdEscritos++;
    if (m.tipo == 'V') {                              // "V3,7": goles izquierda, derecha
      char* coma = strchr(m.texto, ',');
      int gi = constrain(atoi(m.texto), 0, 99), gd = coma ? constrain(atoi(coma + 1), 0, 99) : 0;
      char b[17] = "IZQ:    DER:   ";                // "IZQ:%2d  DER:%2d" armado a mano
      b[4] = gi >= 10 ? '0' + gi / 10 : ' '; b[5] = '0' + gi % 10;
      b[12] = gd >= 10 ? '0' + gd / 10 : ' '; b[13] = '0' + gd % 10;
      lcdLinea(0, b);
    } else lcdLinea(1, m.texto);
    UBaseType_t libre = uxTaskGetStackHighWaterMark(NULL);   // NULL = esta tarea (la ociosa)
    if (libre < pilaOciosa) pilaOciosa = libre;
  }

  if (pedirEstado && imprimirEstado()) pedirEstado = false;
  if (pedirMedidas && imprimirMedidas()) pedirMedidas = false;
  if (mostrar && ahora - tMostrar > 300 && imprimirEstado()) tMostrar = ahora;
  if (!mostrar && estado != AUTOMATICO && ahora - tVivo > 2000 && tomarSerial()) {
    tVivo = ahora; Serial.print('.'); xSemaphoreGive(mtxSerial);
  }
}

// ============================================================================
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
      lcdLinea(0, "PORTEROS ROBOT");
      return;
    }
  }
  Serial.println(F("Sin pantalla LCD"));
}

void setup() {
  pinMode(M_IN3, OUTPUT); pinMode(M_IN4, OUTPUT); salidaMotor(0);
  pinMode(SOL_IN1, OUTPUT); pinMode(SOL_IN2, OUTPUT); solenoide(false);
  pinMode(GND_IZQ, OUTPUT); digitalWrite(GND_IZQ, LOW);
  pinMode(GND_DER, OUTPUT); digitalWrite(GND_DER, LOW);
  pinMode(FIN_IZQ, INPUT_PULLUP); pinMode(FIN_DER, INPUT_PULLUP);
  Serial.begin(115200);
  // OJO: con FreeRTOS delay() es vTaskDelay y antes de arrancar el planificador cuelga el programa:
  { unsigned long t0 = millis(); while (millis() - t0 < 1500) {} }   // espera activa SOLO aqui, antes del RTOS
  Serial.println(F("=== PORTERO ROBOT (FreeRTOS) ==="));
  lcdIniciar();

  colaObjetivo = xQueueCreate(1, sizeof(int));
  colaOrden    = xQueueCreate(4, sizeof(char));
  colaLCD      = xQueueCreate(2, sizeof(MsgLCD));
  mtxSerial    = xSemaphoreCreateMutex();
  tmrGolpe     = xTimerCreate("Golpe", 1, pdFALSE, NULL, finGolpe);   // de un disparo

  //          funcion        nombre  pila(bytes) param prio handle
  xTaskCreate(tareaControl,  "Ctrl", 180,        NULL, 3,   &hControl);
  xTaskCreate(tareaSerial,   "Ser",  150,        NULL, 2,   &hSerial);
  if (!colaObjetivo || !colaOrden || !colaLCD || !mtxSerial || !tmrGolpe || !hControl || !hSerial) {
    Serial.println(F("ERROR: sin memoria para el RTOS"));
    for (;;) {}
  }
  attachInterrupt(digitalPinToInterrupt(FIN_IZQ), isrTope, CHANGE);
  attachInterrupt(digitalPinToInterrupt(FIN_DER), isrTope, CHANGE);
  // Al terminar setup() la libreria arranca el planificador (vTaskStartScheduler)
}
