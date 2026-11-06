/*
  Control WASD — Porteros Robot
  IN3 -> pin 5 (PWM), IN4 -> pin 4, jumper ENB puesto, motor en OUT3/OUT4
  Comandos: a = izquierda, d = derecha, x = soltar, espacio = freno,
            w = mas velocidad, s = menos velocidad
  Si deja de recibir 'a' o 'd' por 400 ms, se detiene solo.
*/
const int PIN_IN3 = 5;   // PWM
const int PIN_IN4 = 4;
const unsigned long WATCHDOG_MS = 400;

int velocidad = 160;     // 0-255
int direccion = 0;       // -1 izq, 0 parado, 1 der
unsigned long ultimo = 0;

void aplicar() {
  if (direccion > 0)      { digitalWrite(PIN_IN4, LOW);  analogWrite(PIN_IN3, velocidad); }
  else if (direccion < 0) { digitalWrite(PIN_IN4, HIGH); analogWrite(PIN_IN3, 255 - velocidad); }
  else                    { digitalWrite(PIN_IN4, LOW);  analogWrite(PIN_IN3, 0); }
}

void frenar() {
  direccion = 0;
  digitalWrite(PIN_IN4, HIGH); analogWrite(PIN_IN3, 255);
  delay(50);
  aplicar();
}

void setup() {
  pinMode(PIN_IN3, OUTPUT);
  pinMode(PIN_IN4, OUTPUT);
  aplicar();
  Serial.begin(115200);
  Serial.println(F("Listo"));
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    switch (c) {
      case 'a': ultimo = millis(); if (direccion != -1) { direccion = -1; aplicar(); Serial.println(F("<- izquierda")); } break;
      case 'd': ultimo = millis(); if (direccion !=  1) { direccion =  1; aplicar(); Serial.println(F("-> derecha")); } break;
      case 'x': if (direccion != 0) { direccion = 0; aplicar(); Serial.println(F("parado")); } break;
      case ' ': frenar(); Serial.println(F("freno")); break;
      case 'w': velocidad = min(255, velocidad + 15); aplicar(); Serial.print(F("velocidad ")); Serial.println(velocidad); break;
      case 's': velocidad = max(0,   velocidad - 15); aplicar(); Serial.print(F("velocidad ")); Serial.println(velocidad); break;
    }
  }
  if (direccion != 0 && millis() - ultimo > WATCHDOG_MS) {
    frenar(); Serial.println(F("parada automatica"));
  }
}
