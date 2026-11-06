// Genera Documento_Tecnico_Porteros_Robot.docx. Uso: node generar_doc.js
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, Table, TableRow, TableCell,
  WidthType, ShadingType, ImageRun, PageBreak, LevelFormat, TableOfContents, Footer, Header,
  PageNumber, BorderStyle,
} = require("docx");

const FIG = path.join(__dirname, "figuras");
const ANCHO = 9360; // carta con margenes de 1"
const FUENTE = "Calibri";
const AZUL = "1F4E79";

// ---------- ayudantes ----------
function runs(texto, base = {}) {
  // **negrita** y `codigo` dentro del texto
  const partes = texto.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).filter(Boolean);
  return partes.map((p) => {
    if (p.startsWith("**")) return new TextRun({ text: p.slice(2, -2), bold: true, ...base });
    if (p.startsWith("`")) return new TextRun({ text: p.slice(1, -1), font: "Consolas", size: 19, ...base });
    return new TextRun({ text: p, ...base });
  });
}
const P = (t, o = {}) => new Paragraph({ children: runs(t), spacing: { after: 120, line: 276 }, alignment: AlignmentType.JUSTIFIED, ...o });
const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(t)], pageBreakBefore: true });
const H1c = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(t)] });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(t)] });
const H3 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun(t)] });
const B = (t, nivel = 0) => new Paragraph({ numbering: { reference: "vinetas", level: nivel }, children: runs(t), spacing: { after: 60 } });
const N = (t) => new Paragraph({ numbering: { reference: "numeros", level: 0 }, children: runs(t), spacing: { after: 60 } });
const CODIGO = (lineas) => lineas.map((l) => new Paragraph({
  children: [new TextRun({ text: l || " ", font: "Consolas", size: 17 })],
  shading: { type: ShadingType.CLEAR, fill: "F3F3F3", color: "auto" }, spacing: { after: 0 },
}));

let nFig = 0, nTab = 0;
function FIGURA(archivo, anchoPx, titulo, dims) {
  const buf = fs.readFileSync(path.join(FIG, archivo));
  const [w, h] = dims || [buf.readUInt32BE(16), buf.readUInt32BE(20)]; // PNG (o medidas dadas para JPG)
  const ancho = anchoPx, alto = Math.round((anchoPx * h) / w);
  nFig++;
  return [
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120, after: 40 }, keepNext: true,
      children: [new ImageRun({ type: archivo.endsWith(".jpg") ? "jpg" : "png", data: buf, transformation: { width: ancho, height: alto },
        altText: { title: titulo, description: titulo, name: archivo } })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 },
      children: [new TextRun({ text: `Figura ${nFig}. `, bold: true, size: 19, color: "444444" }), new TextRun({ text: titulo, italics: true, size: 19, color: "444444" })] }),
  ];
}

const borde = { style: BorderStyle.SINGLE, size: 4, color: "A6A6A6" };
const bordes = { top: borde, bottom: borde, left: borde, right: borde };
function TABLA(titulo, encabezado, filas, anchos) {
  const total = anchos.reduce((a, b) => a + b, 0);
  const esc = anchos.map((a) => Math.round((a * ANCHO) / total));
  esc[esc.length - 1] += ANCHO - esc.reduce((a, b) => a + b, 0);
  const celda = (t, i, cab) => new TableCell({
    width: { size: esc[i], type: WidthType.DXA }, borders: bordes,
    margins: { top: 50, bottom: 50, left: 90, right: 90 },
    shading: cab ? { type: ShadingType.CLEAR, fill: "DCE6F2", color: "auto" } : undefined,
    children: String(t).split("\n").map((l) => new Paragraph({ children: runs(l, { size: 18, bold: cab ? true : undefined }), spacing: { after: 0 } })),
  });
  nTab++;
  return [
    new Paragraph({ keepNext: true, spacing: { before: 160, after: 60 },
      children: [new TextRun({ text: `Tabla ${nTab}. `, bold: true, size: 19, color: "444444" }), new TextRun({ text: titulo, italics: true, size: 19, color: "444444" })] }),
    new Table({ width: { size: ANCHO, type: WidthType.DXA }, columnWidths: esc,
      rows: [new TableRow({ tableHeader: true, children: encabezado.map((t, i) => celda(t, i, true)) }),
        ...filas.map((f) => new TableRow({ children: f.map((t, i) => celda(t, i, false)) }))] }),
    new Paragraph({ spacing: { after: 120 }, children: [] }),
  ];
}

// ---------- portada ----------
const portada = [
  new Paragraph({ spacing: { before: 1200 }, alignment: AlignmentType.CENTER, children: [new TextRun({ text: "UNIVERSIDAD DEL ISTMO", bold: true, size: 28, color: AZUL })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Facultad de Ingeniería", size: 24 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 900 }, children: [new TextRun({ text: "Sistemas Informáticos en Tiempo Real", size: 24 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "PORTEROS ROBOT", bold: true, size: 56, color: AZUL })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [new TextRun({ text: "Juego de mesa autónomo inspirado en Hyperlaps Initial", size: 30 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 900 }, children: [new TextRun({ text: "Documento técnico del proyecto integrador", italics: true, size: 24 })] }),
  ...FIGURA("camara_cenital.png", 380, "Vista cenital de la cancha con los dos porteros, tomada por la cámara del sistema."),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 400 }, children: [new TextRun({ text: "Catedrático: Ing. Mario Porras", size: 24 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Integrantes: ______________________________________________", size: 24 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Guatemala, noviembre de 2026", size: 24 })] }),
];

// ---------- contenido ----------
const c = [];
const add = (...xs) => xs.forEach((x) => (Array.isArray(x) ? c.push(...x) : c.push(x)));

add(
  new Paragraph({ children: [new TextRun({ text: "Contenido", bold: true, size: 32, color: AZUL })], spacing: { after: 200 } }),
  new TableOfContents("Contenido", { hyperlink: true, headingStyleRange: "1-2" }),
  P("(Si el índice aparece vacío, en Word: clic derecho sobre él → Actualizar campos.)", { alignment: AlignmentType.LEFT }));

// 1
add(H1("1. Resumen del proyecto"),
  P("Se diseñó, construyó y programó una arena de juego para dos jugadores en la que dos **porteros robot** (las «naves» del enunciado) defienden su portería de forma completamente autónoma. Una cámara cenital observa la cancha; un programa en Python con OpenCV localiza la bola, estima su velocidad con un filtro de Kalman, predice dónde cruzará la línea de cada portero (incluidos los rebotes en las paredes) y envía por puerto serie el objetivo de posición y la orden de golpe a dos Arduino Uno. Cada Arduino ejecuta **FreeRTOS** y controla su carro (motor DC sobre el riel de una impresora Epson L120), protege los extremos con finales de carrera atendidos por interrupción y acciona un solenoide de empuje de 12 V que devuelve la bola."),
  P("La partida se gestiona en la laptop: detecta los goles con la misma cámara, lleva el marcador, lo muestra en una pantalla LCD de 16x2 y declara al ganador cuando un jugador llega a 10 goles; luego el marcador vuelve a 0-0 para una nueva partida sin reprogramar nada."),
  ...TABLA("Resumen del cumplimiento del alcance mínimo (sección 3 del enunciado).",
    ["Requisito mínimo", "Cómo se cumple", "Estado"],
    [["Arena física construida y operativa", "Octágono de 400 x 430 mm con dos porterías de 300 mm", "Cumplido"],
     ["Dos porterías y dos naves motorizadas", "Carros de impresora Epson L120 con motor DC, banda y finales de carrera", "Cumplido"],
     ["Mecanismo de golpe por jugador", "Solenoide push 12 V con bloque de madera, manejado por L298N", "Cumplido"],
     ["Detección automática de la bola", "Cámara cenital a 60 fps + visión por color (HSV) + Kalman", "Cumplido"],
     ["Detección automática de anotaciones", "Con la cámara: la bola cruza la línea entre postes, rodando hacia la portería", "Cumplido"],
     ["Indicador de 10 puntos por jugador", "Marcador en LCD 16x2 y en pantalla; gana el primero en 10 goles (ver 11.3)", "Cumplido con variante"],
     ["Control autónomo de las dos naves", "Modo automático: sin intervención humana", "Cumplido"],
     ["Software en Arduino con FreeRTOS", "Tareas, colas, mutex, notificaciones, temporizador e ISR (sección 8)", "Cumplido (probado en los dos Uno)"],
     ["Gestión completa de la partida", "Inicio, juego, anotación, ganador y reinicio sin reprogramar", "Cumplido"],
     ["Documentación, diagramas, código y videos", "Este documento, carpeta del proyecto y registros CSV/MP4", "En entrega"]],
    [30, 52, 18]));

// 2
add(H1("2. Requerimientos"),
  P("Los requerimientos se priorizaron con la escala **Alta** (sin ella no hay partida autónoma), **Media** (mejora el desempeño o la seguridad) y **Baja** (extensión)."),
  ...TABLA("Requerimientos funcionales.",
    ["ID", "Requerimiento", "Prioridad", "Implementación"],
    [["RF-01", "Localizar la bola en coordenadas de la cancha (mm) en tiempo real", "Alta", "vision_cancha.py: homografía + HSV"],
     ["RF-02", "Estimar velocidad y dirección de la bola", "Alta", "Filtro de Kalman (trayectoria.py)"],
     ["RF-03", "Predecir el punto de intercepción con rebotes", "Alta", "cruce() con reflexión en espejo"],
     ["RF-04", "Mover cada nave al punto calculado", "Alta", "tControl en el Arduino (T<mm>)"],
     ["RF-05", "Golpear la bola en el momento oportuno", "Alta", "Criterio de tiempo, distancia y velocidad + K"],
     ["RF-06", "Establecer la posición de referencia de la nave", "Alta", "Calibración con los dos finales de carrera"],
     ["RF-07", "Impedir choques contra los extremos", "Alta", "ISR de finales + límites de objetivo 15–205 mm"],
     ["RF-08", "Detectar goles sin contarlos dos veces", "Alta", "Regla de cruce + velocidad + bloqueo de 2 s y rearme"],
     ["RF-09", "Llevar el marcador, declarar ganador y reiniciar", "Alta", "Clase Partida + LCD"],
     ["RF-10", "Manejar pérdida de bola y datos inválidos", "Alta", "Kalman predice 0,15 s; centro tras 1 s; filtros de área y salto"],
     ["RF-11", "Modo manual de prueba", "Baja", "Teclas a/d/k por el monitor serie"],
     ["RF-12", "Registrar evidencias de cada partida", "Media", "CSV por foto + video MP4 anotado (tecla R)"]],
    [9, 47, 12, 32]),
  ...TABLA("Requerimientos no funcionales.",
    ["ID", "Requerimiento", "Prioridad", "Valor objetivo / medido"],
    [["RNF-01", "Frecuencia de percepción suficiente", "Alta", "≥ 30 Hz; medido 64 fps (intervalo p95 = 30 ms)"],
     ["RNF-02", "Latencia total cámara → decisión acotada y compensada", "Alta", "Medida ≈ 100 ms; se compensa adelantando la posición"],
     ["RNF-03", "Respuesta del control del carro", "Alta", "Periodo ≤ 16 ms (1 tick); eventos atendidos al instante"],
     ["RNF-04", "Precisión de posicionamiento", "Alta", "Error típico ±8 mm frente a una paleta de ~100 mm"],
     ["RNF-05", "Seguridad: el solenoide no queda energizado", "Alta", "Apagado por temporizador del kernel (pulso 350 ms)"],
     ["RNF-06", "Seguridad: frenar si se pierde la comunicación", "Alta", "Watchdog: 500 ms sin objetivo → freno"],
     ["RNF-07", "Mantenibilidad: mismo firmware en los dos porteros", "Media", "Autocalibración de sentido del motor y PWM"],
     ["RNF-08", "Recalibración rápida cuando se mueve la cámara", "Media", "Tecla K (4 clics) + medición de carros"],
     ["RNF-09", "Uso de memoria del Arduino Uno", "Alta", "Flash 77 %, RAM estática 35 %; pila libre medida ≥ 54 B por tarea"]],
    [9, 45, 12, 34]));

// 3
add(H1("3. Análisis del problema y planteamiento de la solución"),
  H2("3.1 Problema"),
  P("Una bola rueda por una cancha cerrada a velocidades de 0,3 a 1,5 m/s y rebota en paredes diagonales y rectas. Cada portero recorre 210 mm de riel y tarda entre 0,4 y 0,6 s en cruzarlo, por lo que no basta con seguir la posición actual de la bola: hay que **anticipar** dónde va a cruzar la línea del portero y empezar a moverse antes. Además el golpe debe ocurrir en una ventana corta (decenas de milisegundos) para que el émbolo encuentre a la bola."),
  H2("3.2 Alternativas evaluadas"),
  ...TABLA("Decisiones técnicas principales.",
    ["Decisión", "Alternativas", "Elegida y justificación"],
    [["Sensado de la bola", "Sensor de distancia VL53L0X en cada portero; matriz de sensores; cámara", "Cámara cenital: entrega x, y y velocidad de toda la cancha (el VL53L0X solo mide una distancia y no ve los rebotes)"],
     ["Procesamiento de visión", "En el Arduino; en la laptop", "Laptop con Python/OpenCV: el Uno no tiene memoria ni CPU para imágenes"],
     ["Detección de la bola", "Resta de fondo; red neuronal YOLO; color HSV", "Color HSV: rápido (64 fps), robusto con bola azul sobre fondo blanco; YOLO se probó y era más lento"],
     ["Mecánica de las naves", "Perfil 2020 + GT2 (referencia); riel de impresora", "Riel, banda y motor de impresora Epson L120 reutilizados: guiado ya alineado y bajo costo (solución equivalente permitida en 5.1)"],
     ["Posición del carro", "Encoder; posición por tiempo", "Dead reckoning por tiempo calibrado contra los dos finales de carrera (no hay encoder disponible)"],
     ["Golpe", "Relé; MOSFET IRFZ44N; puente H L298N", "L298N dedicado a los solenoides: el relé disponible estaba dañado; el L298N aísla al Arduino y trae diodos de protección"],
     ["Detección de goles", "Láser/IR en la portería; cámara", "Cámara: el sensor IR daba falsos positivos; la cámara ya ve la línea de gol"],
     ["Sistema operativo", "Lazo único (versión 1); FreeRTOS", "FreeRTOS: prioridades, eventos por interrupción y comunicación entre tareas (requisito del curso)"]],
    [20, 33, 47]),
  H2("3.3 Solución propuesta"),
  P("El sistema se divide en dos niveles que se comunican por USB serie (Figura 2):"),
  B("**Nivel de percepción y decisión (laptop):** cámara, visión, estimación, predicción, decisión de golpe, reglas de la partida y registro de evidencias."),
  B("**Nivel de control en tiempo real (Arduino + FreeRTOS):** posición del carro, control del motor, protección de topes, pulso del solenoide, pantalla y supervisión."),
  P("Así la tarea pesada (procesar 64 imágenes por segundo) no compite con el control del motor, y cada Arduino puede reaccionar en microsegundos a un final de carrera aunque la laptop se atrase."));

// 4
add(H1("4. Arquitectura general hardware–software"),
  ...FIGURA("arquitectura.png", 600, "Arquitectura general: la laptop percibe y decide; cada Arduino controla su portero con FreeRTOS."),
  ...TABLA("Protocolo serie laptop ↔ Arduino (115200 baud, texto terminado en salto de línea).",
    ["Mensaje", "Sentido", "Significado"],
    [["T<mm>", "laptop → Arduino", "Objetivo del carro en mm desde el tope izquierdo (se limita a 15–205)"],
     ["K", "laptop → Arduino", "Golpe del solenoide"],
     ["P<ms>", "laptop → Arduino", "Duración del golpe (20–600 ms); se envía 350 al conectar"],
     ["V<i>,<d>", "laptop → Arduino", "Marcador para la línea 1 de la LCD"],
     ["X<texto>", "laptop → Arduino", "Mensaje para la línea 2 de la LCD (máx. 16 caracteres)"],
     ["c, p, m, a, d, k…", "laptop → Arduino", "Recalibrar, estado, mediciones de tiempo real y teclas manuales"],
     ["LISTO", "Arduino → laptop", "Calibración terminada: el portero puede jugar"],
     ["Estado / mediciones", "Arduino → laptop", "Respuestas a p y m, avisos de fallo"]],
    [18, 20, 62]));

// 5
add(H1("5. Diseño y construcción mecánica"),
  H2("5.1 Arena"),
  P("La arena es un octágono simétrico. Las dimensiones se redujeron respecto a la referencia de 700 x 700 mm porque el recorrido útil de los rieles de impresora disponibles es de 210 mm; con una portería de 300 mm, una cancha más grande dejaría zonas imposibles de defender. Todas las medidas se tomaron con regla y se usan directamente en el software. La arena se trazó y cortó en cartón (Figura 3); después se agregaron rampas blancas inclinadas al pie de las paredes para que la bola no se quede atorada en las esquinas."),
  ...FIGURA("fotos_arena.jpg", 600, "Construcción de la arena: trazado del octágono, corte del cartón, armado de las paredes y arena terminada.", [1620, 570]),
  ...TABLA("Dimensiones de la arena construida frente a la referencia.",
    ["Elemento", "Referencia del enunciado", "Construido", "Justificación"],
    [["Área de juego", "700 x 700 mm", "400 mm entre caras de los porteros x 430 mm entre paredes rectas", "Escalada al recorrido del riel (210 mm)"],
     ["Geometría", "Octágono simétrico", "Octágono: paredes rectas de 240 mm arriba y abajo + 4 diagonales", "Igual a la referencia"],
     ["Paredes", "379 x 55 x 4 mm, transparentes", "Cartón rígido, 75 mm de alto", "Material disponible; altura suficiente para la bola"],
     ["Porterías", "Una por lado", "Dos, de 300 mm de poste a poste", "Mínimo obligatorio de dos jugadores"],
     ["Bola", "Acero pulido", "Bola azul", "Color con alto contraste para la visión por cámara"],
     ["Naves", "Dos como mínimo", "Dos carros de impresora Epson L120", "Desplazamiento horizontal sobre riel"]],
    [16, 22, 34, 28]),
  ...FIGURA("vista_enderezada.png", 330, "Vista enderezada por homografía: cada píxel equivale a 1/1,5 mm; las paredes rectas quedan en y = 0 y y = 430 mm."),
  H2("5.2 Naves (porteros)"),
  P("Cada portero reutiliza el mecanismo de carro de una impresora Epson L120: riel guía, banda, poleas y motor DC. Sobre el carro se montó la paleta defensora (palitos de madera) y el solenoide. Dos finales de carrera normalmente abiertos marcan los extremos y sirven de referencia de posición. El recorrido medido con la cámara es de **210 mm**; el software limita los objetivos a 15–205 mm para no golpear los topes (era 25 mm; se redujo a 15 al tener el freno por interrupción, para cubrir más las esquinas de la portería)."),
  B("Desplazamiento en ambos sentidos con un puente H L298N."),
  B("Velocidad de trabajo definida por calibración: portero izquierdo ≈ 490 mm/s con PWM 190; el derecho necesita PWM 255 por mayor fricción mecánica."),
  B("A PWM 255 el carro izquierdo alcanzaba ~1 m/s y se trababa contra el final de carrera, por eso su velocidad se limitó."),
  P("Antes de llegar a esta solución se probó un chasis con piezas LEGO movido por un motor DC y una paleta articulada (Figura 5). Se cambió al riel de impresora porque ya trae guía, banda y motor alineados, y es más rígido y repetible. La paleta y el solenoide se montaron primero sobre el carro con piezas LEGO para las pruebas de movimiento (Figura 6)."),
  ...FIGURA("fotos_prototipos.jpg", 600, "Primeros prototipos: chasis LEGO, motor DC, paleta articulada y el riel de la impresora Epson que se reutilizó.", [2154, 570]),
  ...FIGURA("fotos_integracion.jpg", 600, "Integración: riel con Arduino y L298N, solenoide montado en el carro, pruebas de movimiento y medición de voltajes.", [1533, 570]),
  H2("5.3 Mecanismo de golpe"),
  P("Un solenoide de empuje (push) de 12 V con un bloque de madera en el émbolo empuja la bola. Con pulsos de 80–120 ms el émbolo apenas se movía por la masa del bloque; con **350 ms** sale completo. El firmware impide activaciones repetidas: ignora una orden nueva hasta que pasaron el pulso más 500 ms de regreso del émbolo."));

// 6
add(H1("6. Diseño eléctrico y electrónico"),
  ...FIGURA("electrico.png", 600, "Diagrama eléctrico de un portero (el segundo es idéntico, salvo la LCD)."),
  ...TABLA("Asignación de pines del Arduino Uno.",
    ["Pin", "Función", "Conectado a"],
    [["D5 (PWM)", "Velocidad y sentido del motor", "L298N #1, entrada IN"],
     ["D4", "Sentido del motor", "L298N #1, entrada IN"],
     ["D9", "Solenoide", "L298N #2, IN1 e IN3"],
     ["D10", "Solenoide (nivel bajo)", "L298N #2, IN2 e IN4"],
     ["D2 (INT0)", "Final de carrera izquierdo (NO)", "Interruptor; su común va a D12"],
     ["D3 (INT1)", "Final de carrera derecho (NO)", "Interruptor; su común va a D11"],
     ["D12, D11", "Salidas en LOW (tierra de los finales)", "Común de cada final de carrera"],
     ["A4, A5", "I2C SDA, SCL", "LCD 1602 con módulo I2C (solo Uno izquierdo)"],
     ["USB", "Alimentación 5 V y comunicación", "Laptop (COM6 izquierdo, COM7 derecho)"]],
    [16, 38, 46]),
  H2("6.1 Alimentación y protección"),
  B("Dos fuentes de 12 V independientes: una para los motores y otra para los solenoides, para que el pico de corriente del golpe no haga caer el voltaje del motor ni reinicie la lógica."),
  B("Tierra común entre los Arduino, los dos L298N y las fuentes, necesaria para que las señales lógicas tengan la misma referencia."),
  B("Aislamiento: el Arduino solo entrega señales lógicas a las entradas de los L298N; la corriente de potencia nunca pasa por el microcontrolador."),
  B("Cargas inductivas: el módulo L298N incluye diodos de rueda libre que absorben el pico de voltaje al apagar el motor o el solenoide."),
  B("Desconexión de potencia: apagando las fuentes de 12 V se detienen motores y solenoides sin afectar la comunicación del Arduino."),
  B("Finales de carrera con pull-up interno y lectura confirmada (3 lecturas en LOW con 300 µs de separación) para filtrar el ruido del motor."),
  P("Se descartaron un módulo de relé (no conmutaba: estaba dañado) y el primer montaje de un solo L298N compartido entre motor y solenoide (el solenoide quedaba débil). Dos MOSFET IRFZ44N quedan como repuesto."));

// 7
add(H1("7. Arquitectura de software"),
  H2("7.1 Programas y archivos"),
  ...TABLA("Organización del código fuente.",
    ["Archivo", "Lenguaje", "Responsabilidad"],
    [["PORTERO_SERIAL/PORTERO_SERIAL.ino", "C++ (Arduino + FreeRTOS)", "Firmware de cada portero (mismo archivo en los dos Uno)"],
     ["PORTERO_SERIAL_v1_loop/", "C++ (Arduino)", "Versión anterior sin RTOS, conservada como referencia"],
     ["vision/vision_cancha.py", "Python 3 + OpenCV", "Programa principal: cámara, visión, decisiones, partida, registro"],
     ["vision/trayectoria.py", "Python 3", "Filtro de Kalman, reflexión de rebotes, cruce, conversión a mm del carro"],
     ["vision/calibracion.json", "JSON", "Esquinas de la homografía, resolución y color HSV"],
     ["vision/analizar_registro.py", "Python 3", "Análisis de los CSV de cada partida"],
     ["vision/medir_latencia.py", "Python 3", "Medición de la latencia de la cámara"],
     ["vision/iniciar_cancha.bat", "Batch", "Instala dependencias y arranca el sistema con doble clic"],
     ["vision/registros/", "CSV + MP4", "Evidencia de cada sesión: una fila y un cuadro de video por foto"]],
    [34, 22, 44]),
  P("Bibliotecas de terceros (sección 21 del enunciado): **FreeRTOS 11.1 para Arduino** (Phillip Stevens), **LiquidCrystal_I2C** y **Wire** en el firmware; **OpenCV**, **NumPy** y **pySerial** en la laptop. El código de control, percepción, predicción y reglas del juego es propio del equipo."),
  H2("7.2 Ciclo principal de la laptop"),
  P("Un hilo dedicado lee la cámara y conserva solo la foto más nueva, para no procesar imágenes atrasadas del búfer del controlador. El hilo principal, por cada foto: endereza la imagen, detecta la bola, actualiza el Kalman, calcula objetivos y golpes, envía los mensajes a los dos Arduino (como máximo cada 50 ms, y al menos cada 200 ms aunque no cambien, para alimentar el watchdog), aplica las reglas de gol y escribe el registro."));

// 8
add(H1("8. Implementación de tiempo real con FreeRTOS"),
  P("El firmware usa la biblioteca FreeRTOS 11.1 para AVR. El tick del kernel lo genera el watchdog del ATmega328P cada **16 ms** (62,5 Hz); el planificador es expropiativo con prioridades fijas (0 a 3). Para no depender solo del tick, los eventos urgentes despiertan a la tarea de control con notificaciones directas."),
  ...FIGURA("tareas_freertos.png", 600, "Tareas, prioridades y mecanismos de comunicación del firmware."),
  ...TABLA("Tareas y componentes concurrentes (sección 9.1 del enunciado).",
    ["Componente", "Prioridad", "Activación / periodo", "Pila", "Funciones del enunciado que cubre"],
    [["ISR de finales (INT0, INT1)", "Hardware", "Cada flanco de un final de carrera", "—", "Adquisición de sensores (topes)"],
     ["tControl", "3 (máxima)", "Cada tick (16 ms) o al instante con una notificación", "180 B", "Control de movimiento, protección de topes, calibración"],
     ["Temporizador del kernel", "3", "Un disparo, al terminar el pulso", "92 B (kernel)", "Control del mecanismo de golpe (apagado seguro)"],
     ["tSerial", "2", "Cada tick (16 ms)", "150 B", "Adquisición de datos de la visión, orden de golpe, puntos para la LCD"],
     ["Tarea ociosa (loop)", "0", "Cuando no hay otra lista; supervisión cada 100 ms", "192 B (kernel)", "Supervisión y diagnóstico, pantalla, reportes"],
     ["Laptop (Python)", "—", "Cada foto (≈ 15,6 ms)", "—", "Estimación de posición y trayectoria, máquina de estados del juego, goles"]],
    [22, 11, 27, 11, 29]),
  H2("8.1 Justificación de prioridades"),
  B("**tControl tiene la prioridad más alta** porque es la única que puede dañar el hardware: si el carro llega a un extremo, cada milisegundo de retraso es empuje contra el tope. Además su trabajo es corto (decenas a cientos de microsegundos)."),
  B("**El temporizador del golpe también tiene prioridad 3** para que el solenoide se apague exactamente al terminar el pulso aunque otra tarea esté ocupada: el actuador nunca queda energizado de más."),
  B("**tSerial tiene prioridad 2:** sus datos alimentan al control, pero un retraso de un tick (16 ms) es pequeño frente a la latencia de la cámara (≈ 100 ms)."),
  B("**La supervisión y la LCD corren en la tarea ociosa (prioridad 0):** la escritura I2C de la pantalla tarda varios milisegundos y nunca debe retrasar al control. Se ubicaron en el gancho de la tarea ociosa en lugar de una tarea propia porque el Uno tiene 2 KB de RAM: cada tarea adicional cuesta ≈ 200 B (pila + TCB de 48 B), y la tarea ociosa ya tiene su pila reservada. El código ahí nunca bloquea (colas y mutex con tiempo de espera 0)."),
  H2("8.2 Sincronización y comunicación"),
  ...TABLA("Mecanismos de sincronización usados.",
    ["Mecanismo", "Entre", "Para qué"],
    [["Notificación directa desde ISR (vTaskNotifyGiveFromISR)", "ISR de finales → tControl", "Despertar al control en cuanto cambia un final, sin esperar el tick; la ISR solo anota el instante"],
     ["Buzón (cola de 1, xQueueOverwrite)", "tSerial → tControl", "Entregar siempre el objetivo más nuevo; uno viejo no sirve en tiempo real"],
     ["Cola de órdenes (4 caracteres)", "tSerial y supervisión → tControl", "Órdenes manuales, recalibración y freno de seguridad S; tControl es la única que toca el motor"],
     ["Cola de la LCD (2 mensajes)", "tSerial y tControl → tarea ociosa", "Desacoplar la escritura lenta por I2C"],
     ["Mutex mtxSerial (con herencia de prioridad)", "tSerial, tControl y tarea ociosa", "Que dos tareas no mezclen texto en el puerto serie"],
     ["Temporizador de un disparo (xTimerChangePeriod)", "tSerial → servicio de temporizadores", "Apagar el solenoide al cumplirse el pulso sin bloquear a nadie"],
     ["Secciones críticas (taskENTER_CRITICAL)", "Tareas e ISR", "Copiar variables de 4 bytes de forma atómica en un procesador de 8 bits"]],
    [32, 26, 42]),
  H2("8.3 Condiciones de carrera, bloqueos e inversión de prioridades"),
  B("**Un solo dueño del motor:** solo tControl escribe los pines del motor; las demás tareas le piden cosas por colas. Así no hay carreras sobre la dirección ni el PWM."),
  B("**Variables de varios bytes:** `posMM`, `ultimoT` o los instantes de las mediciones ocupan 4 bytes y el AVR los escribe en varias instrucciones; se leen dentro de secciones críticas para no obtener valores a medias."),
  B("**Inversión de prioridades:** si la tarea ociosa (prioridad 0) tiene el mutex del puerto serie y tControl (prioridad 3) lo necesita, el mutex de FreeRTOS hereda la prioridad y la ociosa termina rápido. Además, en modo automático tControl casi no imprime."),
  B("**Bloqueos (deadlock):** solo existe un mutex y nunca se toma otro recurso mientras se tiene, por lo que no puede haber espera circular. La tarea ociosa nunca espera el mutex: si está ocupado lo intenta en la siguiente vuelta."),
  B("**Pérdida de eventos:** el buzón de objetivos descarta a propósito los viejos; las órdenes manuales tienen cola de 4; las notificaciones de la ISR se acumulan como contador; el UART guarda 64 bytes, suficiente para 16 ms de mensajes (≈ 6 bytes por objetivo)."),
  B("**Sin esperas activas:** la calibración espera los finales de carrera durmiendo hasta la notificación de la ISR, las pausas usan vTaskDelay y el freno activo no espera: se pone y tControl lo suelta 40 ms después en un ciclo posterior, para que un objetivo nuevo no quede bloqueado."),
  H2("8.4 Medición de tiempos de respuesta"),
  P("El firmware mide sus propios tiempos con micros() y los informa con la tecla **m** (máximos desde la consulta anterior): periodo y tiempo de ejecución de tControl, tiempo de ejecución de tSerial, latencia final de carrera (ISR) → freno, latencia objetivo recibido → control, cantidad de golpes ejecutados e ignorados y la pila libre de cada tarea. La tabla siguiente compara la cota de diseño con lo medido en los dos Arduino el 5 de noviembre de 2026 (calibración + objetivos 40, 170 y 105 mm)."),
  ...TABLA("Tiempos de respuesta de los eventos críticos.",
    ["Evento crítico", "Cota por diseño", "Medido (tecla m)"],
    [["Final de carrera → motor cortado", "< 1 ms (ISR + cambio de contexto + 3 lecturas de 300 µs)", "0,76 ms (portero derecho)"],
     ["Objetivo T recibido → control lo aplica", "≤ 16 ms (lectura de tSerial) + < 1 ms (notificación)", "84 µs desde que tSerial lo decodifica"],
     ["Orden K → solenoide encendido", "≤ 16 ms (lectura de tSerial)", "≤ 16 ms; tSerial se ejecuta en ≤ 0,44 ms"],
     ["Duración del pulso del golpe", "350 ms ± 16 ms (resolución del tick)", "22 ticks = 352 ms (configurado)"],
     ["Periodo de tControl", "1 tick = 16 ms", "16,8 ms máx.; ejecución 0,15–0,30 ms"],
     ["Pérdida de comunicación → freno", "500 ms + ≤ 100 ms de supervisión", "Comprobado (aviso SIN OBJETIVO y freno)"],
     ["Cámara → decisión en la laptop", "—", "≈ 100 ms (medido, 2026-10-30)"]],
    [36, 40, 24]),
  H2("8.5 Uso de memoria"),
  P("Compilado para el Arduino Uno: 25 100 bytes de programa (77 %) y 730 bytes de variables globales (35 %), dejando 1 318 bytes para el montículo de FreeRTOS. Las pilas de las tareas, la tarea ociosa (192 B), el servicio de temporizadores (92 B + cola), las colas y el mutex ocupan ≈ 1 100 bytes. Para que alcanzara se pasaron los textos a la memoria flash (F(), PSTR) y se agruparon funciones de baja prioridad en la tarea ociosa. Medido con la tecla m: a tControl (180 B) le sobran 67–106 B y a tSerial (150 B) le sobran 54–87 B, por lo que ninguna pila corre riesgo de desbordarse."));

// 9
add(H1("9. Estados y operación"),
  H2("9.1 Estados del firmware de cada portero"),
  ...FIGURA("estados_firmware.png", 580, "Máquina de estados del firmware de cada portero."),
  ...TABLA("Estados del firmware.",
    ["Estado", "Qué hace", "Sale cuando"],
    [["INICIALIZACIÓN", "Calibra: busca el tope izquierdo, mide el tiempo hasta el derecho, corrige el sentido del motor y el PWM, vuelve al centro", "Calibración correcta (LISTO) → ESPERA; fallida → FALLO"],
     ["ESPERA", "Carro detenido y calibrado", "Llega un objetivo → AUTOMÁTICO; tecla a/d → MANUAL"],
     ["AUTOMÁTICO", "Sigue los objetivos de la visión", "500 ms sin objetivo o espacio → ESPERA"],
     ["MANUAL", "Movimiento con teclas para pruebas", "400 ms sin tecla o espacio → ESPERA"],
     ["FALLO", "No acepta objetivos; solo movimiento manual", "Tecla c (recalibrar) → INICIALIZACIÓN"]],
    [18, 50, 32]),
  H2("9.2 Estados de la partida"),
  ...FIGURA("estados_partida.png", 600, "Estados de la partida (sección 10 del enunciado), gestionados por la laptop."),
  ...TABLA("Correspondencia con los estados del enunciado.",
    ["Estado del enunciado", "Implementación"],
    [["INICIALIZACIÓN", "Se abre la cámara, se conectan los puertos y cada Arduino calibra su carro"],
     ["ESPERA", "Los dos porteros respondieron LISTO; el marcador está en 0-0"],
     ["INICIO DE PARTIDA", "Tecla A (automático) con la bola al centro; tecla N reinicia el marcador"],
     ["JUEGO", "Percepción, predicción, movimiento y golpe en cada foto"],
     ["ANOTACIÓN", "Se valida el gol, se suma al marcador, se actualiza la LCD y se bloquea 2 s"],
     ["FIN", "Un jugador llega a 10 goles: se anuncia «GANA X a-b» y el marcador vuelve a 0-0"],
     ["FALLO / SEGURIDAD", "Sin objetivo 500 ms → freno; sin bola 1 s → carros al centro; calibración fallida → FALLO"]],
    [26, 74]),
  H2("9.3 Operación"),
  N("Encender las dos fuentes de 12 V y conectar los dos Arduino por USB."),
  N("Doble clic en `vision/iniciar_cancha.bat`. Cada portero se calibra solo y responde LISTO."),
  N("Si la cámara se movió: tecla K y clic en los 4 extremos de las paredes rectas."),
  N("Tecla N (marcador a 0-0), R (grabar evidencia) y A (modo automático)."),
  N("Al terminar: Esc. Los registros quedan en `vision/registros`."));

// 10
add(H1("10. Percepción, predicción e intercepción"),
  ...FIGURA("flujo_percepcion.png", 600, "Flujo de una foto, desde la cámara hasta las órdenes de movimiento y golpe."),
  H2("10.1 Percepción"),
  P("La cámara (un iPhone usado como cámara web con iVCam) captura 640 x 480 a 60 fps. Con los 4 extremos de las paredes rectas marcados una sola vez se calcula una **homografía** que transforma la imagen en una vista cenital «enderezada» donde 1 mm = 1,5 píxeles; el origen está en la cara del portero izquierdo (x) y en la pared recta de arriba (y). La vista se extiende 40 mm fuera de la cancha para ver completa la bola pegada a la pared."),
  P("La bola se separa por color en el espacio HSV (H 95–130, S 100–255, V 50–255, ajustable en vivo). La máscara se limpia con apertura y cierre morfológicos y se elige la mancha de área válida (150 a 4 000 mm²) más circular. Su centroide es la medición (x, y) en milímetros."),
  ...FIGURA("seguimiento.png", 360, "Vista de trabajo: bola detectada (círculo verde), velocidad estimada y punto de intercepción predicho en la línea del portero derecho (punto rojo)."),
  H2("10.2 Estimación (filtro de Kalman)"),
  P("Se usa un filtro de Kalman de velocidad constante con estado [x, y, vx, vy] y medición [x, y]. El intervalo dt entre fotos se toma del reloj real. El ruido del proceso modela una aceleración aleatoria de 2 000 mm/s² (frenado y rebotes) y el de la medición 3 mm. El filtro suaviza la posición, estima la velocidad y, si la bola deja de verse, sigue prediciendo hasta 0,15 s; después se reinicia. La velocidad solo se usa a partir de la tercera medición."),
  H2("10.3 Compensación de la latencia"),
  P("Se midió una latencia de ≈ 100 ms entre lo que ocurre en la cancha y su procesamiento (cámara, transmisión iVCam y proceso), tanto por WiFi como por USB. Para decidir con la posición real se adelanta la estimación: x ← x + vx·0,10 y y ← y + vy·0,10."),
  H2("10.4 Intercepción"),
  P("Para cada portero, si la bola se acerca a su línea (x_l) a más de 50 mm/s, el tiempo de llegada es t = (x_l − x)/vx y la altura de cruce sin paredes es y* = y + vy·t. Los rebotes en las paredes de arriba (y = 0) y abajo (y = 430 mm) se resuelven por reflexión en espejo: se toma y* módulo 860 mm y, si pasa de 430, se refleja (860 − y*). Si la bola se aleja, el portero sigue su altura; si no se ve durante 1 s, vuelve al centro."),
  P("La altura de cruce se convierte a la coordenada del carro con la recta medida para cada portero, carro = (y* − y₀)/(s·e), donde y₀ es la altura del portero en el tope izquierdo, s = ±1 el sentido y e la escala. Se calibra moviendo cada carro a 5 posiciones y midiendo el bloque en la imagen (Figura 13)."),
  ...FIGURA("calib_izq.png", 430, "Calibración de la posición del portero izquierdo: el carro en T = 40, 60, 105, 150 y 170 mm con la regla en mm de la vista."),
  H2("10.5 Decisión del golpe"),
  P("El golpe se ordena cuando se cumplen a la vez: faltan menos de **0,08 s** para que la bola llegue a la línea, la bola está a menos de **25 mm** de la línea y viene a más de **80 mm/s**. Los tres umbrales se eligieron con una búsqueda en cuadrícula sobre las grabaciones del 3 de noviembre: con solo el criterio de tiempo el golpe salía 0,2–0,8 s antes porque la bola frena o rebota. Después de un golpe se esperan 0,9 s antes de otro (pulso de 350 ms más el regreso del émbolo)."),
  H2("10.6 Datos inválidos e incertidumbre"),
  B("Manchas demasiado pequeñas o grandes (reflejos, la mano) se descartan por área."),
  B("Saltos imposibles entre fotos reinician la estimación."),
  B("Sin medición se usa la predicción del Kalman hasta 0,15 s; luego se declara la bola perdida."),
  B("Sin objetivos nuevos por 500 ms el Arduino frena solo (watchdog en el firmware)."),
  B("La laptop reenvía el objetivo cada 200 ms aunque no cambie, para que el watchdog no frene a un portero que ya está en su sitio."),
  H2("10.7 Limitaciones del sensor"),
  B("Latencia de ≈ 100 ms: a 1 m/s la bola avanza 100 mm antes de procesarse; la compensación depende de que la velocidad no cambie en ese tiempo."),
  B("La posición del carro no se mide: se estima por tiempo (error típico ±8 mm, hasta 14 mm)."),
  B("La cámara se recalibra cada vez que el teléfono se mueve."),
  B("Con la mano o un objeto azul en la cancha pueden aparecer detecciones falsas."));

// 11
add(H1("11. Detección de anotaciones y marcador"),
  H2("11.1 Mecanismo"),
  P("Primero se instaló un sensor infrarrojo en la portería (entrada A3 del Arduino), pero daba lecturas falsas por la luz ambiente y por la paleta del portero. Se reemplazó por la misma cámara, que ya conoce la posición de la bola respecto a la línea de gol. Con la regla inicial se contaron goles falsos (la bola quieta junto a la paleta o levantada con la mano); se endureció así:"),
  B("El centro de la bola debe pasar la cara del portero (x < 0 o x > 400 mm) entre los postes (y entre 65 y 365 mm, ±10 mm), o perderse de vista a menos de 15 mm de la cara durante 0,3 s (entró bajo el chasis)."),
  B("Y además debe venir rodando hacia esa portería a más de 150 mm/s en los últimos 0,5 s."),
  H2("11.2 Validación y conteo único"),
  B("Tras un gol se bloquean nuevos goles durante 2 s."),
  B("Y no se rearma la detección hasta que la bola vuelve a la zona central (x entre 100 y 300 mm). Así un mismo ingreso no se cuenta dos veces."),
  H2("11.3 Marcador y ganador"),
  P("Cada gol se registra en el estado de la partida, se imprime en consola, se muestra en la vista de la cámara y se envía a la LCD (línea 1: «IZQ: n  DER: n»; línea 2: mensaje). Por decisión del equipo el marcador cuenta **goles anotados** en lugar de restar vidas: el primero que llega a 10 goles gana, se anuncia «GANA X a-b» y el marcador vuelve a 0-0. Es equivalente a la regla del enunciado (10 goles recibidos equivalen a 0 puntos de vida del rival) y resultó más claro para los espectadores."));

// 12
add(H1("12. Plan y resultados de pruebas"),
  P("Antes de integrar se probaron por separado sensores, motores y actuadores (sección 13 del enunciado). Las sesiones de juego se grabaron con la tecla R: cada una deja un CSV con una fila por foto (tiempo, detección, posición medida y estimada, velocidad, objetivos y golpes) y un video MP4 anotado."),
  ...TABLA("Plan y resultados de pruebas.",
    ["#", "Prueba", "Método", "Resultado"],
    [["1", "Finales de carrera", "Presionar cada uno a mano y leer el estado (tecla p)", "OK; se detectaron y corrigieron cables invertidos y en corto"],
     ["2", "Movimiento de cada nave", "Teclas a/d y calibración automática", "Izq.: 427 ms de recorrido = 492 mm/s a PWM 190. Der.: necesita PWM 255 (92–350 mm/s, fricción variable)"],
     ["3", "Solenoide", "Tecla j (1 s encendido) y k (pulso)", "Golpe completo con 350 ms; débil con 80–120 ms"],
     ["4", "Frecuencia de la cámara", "Intervalo entre filas de los CSV (20 sesiones)", "64 fps de mediana; intervalo p95 = 30 ms"],
     ["5", "Latencia de la cámara", "medir_latencia.py (cambio de pantalla filmado)", "≈ 100 ms por WiFi y 98 ms por USB"],
     ["6", "Calibración de la vista", "Vista enderezada contra la regla en mm", "Paredes en 0 y 430 mm; error < 5 mm"],
     ["7", "Posición del carro vs. visión", "5 objetivos por portero, ajuste lineal", "Izq. y = 35 + 1,08·c; der. y = 281 − 0,97·c; residuo típico ±8 mm, máx. 14 mm"],
     ["8", "Seguimiento de la bola", "Grabación revisada cuadro por cuadro", "Seguimiento continuo con la bola en juego, sin pérdidas en la prueba del 2026-11-02"],
     ["9", "Oportunidad del golpe", "CSV con golpes vs. contacto en video (27 golpes)", "≈ 40 % a tiempo (11 de 27) tras ajustar los umbrales"],
     ["10", "Detección de goles", "Goles reales y casos trampa (bola quieta, mano)", "Con la regla estricta se eliminaron los goles falsos (antes 4-4 falso)"],
     ["11", "Partida completa", "Sesión de 455 s en automático", "103 golpes registrados; partida sin intervención en el control"],
     ["12", "Tiempos de FreeRTOS", "Tecla m tras calibrar y mover a 3 objetivos", "Periodo 16,8 ms; final de carrera → freno 0,76 ms; objetivo → control 84 µs; pila libre ≥ 54 B"]],
    [5, 21, 33, 41]),
  H2("12.1 Validación del firmware con FreeRTOS"),
  P("El firmware con FreeRTOS se cargó en los dos Arduino el 5 de noviembre de 2026. Los dos calibraron solos y respondieron LISTO, y siguieron los objetivos 40, 170 y 105 mm con error de 3 a 8 mm en el izquierdo y de 5 a 8 mm en el derecho. El golpe funcionó y repetirlo enseguida se ignoró como estaba previsto. Además se ejecutó mientras el carro calibraba, lo que demuestra que las tareas corren de forma concurrente. El portero derecho necesitó PWM 255 y llegó solo a 174 mm/s por la fricción de su riel, un problema mecánico y no del firmware. Falta repetir una partida completa (prueba 11) con esta versión. La versión anterior sin RTOS se conserva en `PORTERO_SERIAL_v1_loop` por si hace falta volver a ella durante la demostración."));

// 13
add(H1("13. Registro de problemas, decisiones y cambios de diseño"),
  ...TABLA("Problemas encontrados y cómo se resolvieron.",
    ["Problema", "Causa", "Solución / decisión"],
    [["La imagen se veía con zoom y deformada al calibrar", "Esquinas marcadas en los postes de las porterías", "Calibrar con los extremos de las paredes rectas y extender la vista 40 mm"],
     ["Video con atraso", "Latencia de cámara + iVCam (~100 ms)", "Hilo de captura con la foto más nueva + compensación de latencia"],
     ["El carro izquierdo se trababa en el tope", "A PWM 255 iba a ~1 m/s", "PWM 190 y objetivos limitados (hoy 15–205 mm)"],
     ["Recorrido real distinto al supuesto", "Se supuso 280 mm", "Medido con la cámara: 210 mm"],
     ["Posición inconsistente tras calibrar", "Regreso al centro por tiempo fijo", "Contar desde que se suelta el final de carrera (punto fijo)"],
     ["Control proporcional no llegaba", "A PWM bajo el motor casi no avanza", "Control todo-o-nada a la velocidad calibrada"],
     ["Motor del portero derecho al revés y lento", "Cableado distinto y más fricción", "Autocalibración: invierte el sentido y sube el PWM solo"],
     ["«Lado contrario» falso al calibrar", "El final de inicio seguía presionado", "Contar el final contrario solo después de soltar el de inicio"],
     ["Los dos finales leídos a la vez", "Cables de D2/D3 en corto", "Revisión de cableado + verificación en firmware (estado FALLO)"],
     ["El solenoide no golpeaba", "Jumper dañado, cable suelto, pin D8 sin señal, relé dañado", "L298N dedicado en D9/D10; se cambió el jumper"],
     ["Golpe débil", "Un L298N compartido y pulsos cortos", "L298N y fuente propios + pulso de 350 ms"],
     ["El golpe paraba el motor", "delay() bloqueaba todo el programa", "Golpe no bloqueante; en FreeRTOS, temporizador del kernel"],
     ["Golpe 0,2–0,8 s antes de tiempo", "La bola frena o rebota", "Criterio de tiempo + distancia + velocidad (búsqueda en cuadrícula)"],
     ["Goles falsos (4-4)", "Sensor IR y regla de gol simple", "Gol por cámara con velocidad mínima, bloqueo y rearme"],
     ["Detecciones falsas", "Modo «fondo» activado por accidente", "Usar el modo «color» (por defecto)"],
     ["La vista se descalibra cada día", "El teléfono se retira del laboratorio", "Marcar la posición del teléfono; recalibrar con K y medir carros"],
     ["Con FreeRTOS el Arduino no respondía al encender", "delay() se redefine como vTaskDelay y se llamaba en setup(), antes de arrancar el planificador", "Espera con millis() solo en setup(); en las tareas, vTaskDelay"],
     ["El freno bloqueaba al control 48 ms", "frenar() esperaba con vTaskDelay", "Freno no bloqueante: tControl lo suelta en un ciclo posterior (objetivo → control pasó de 50 ms a 84 µs)"],
     ["La LCD no mostraba el marcador", "La pila de la tarea ociosa (192 B) se desbordaba con snprintf al escribir la pantalla (pila libre medida: 0 B)", "Formateo manual sin snprintf y números sin el búfer de 33 B: quedan 47 B libres"],
     ["Goles por las esquinas de la portería", "El recorrido del carro no cubre los extremos de la portería", "Objetivos hasta 15 mm del tope; se propone alargar el palito de la paleta hacia la esquina descubierta"],
     ["RAM insuficiente para 5 tareas", "2 KB de RAM del Uno", "3 tareas + temporizador + supervisión en la tarea ociosa; textos en flash"]],
    [30, 30, 40]));

// 14
add(H1("14. Competencias adquiridas"),
  B("**Sistemas de tiempo real:** separar lo que tiene plazo duro (topes, pulso del solenoide) de lo que tolera atraso (pantalla, reportes); asignar prioridades por consecuencia del retraso; usar ISR, notificaciones, colas, mutex y temporizadores de FreeRTOS; razonar sobre carreras, bloqueos e inversión de prioridades."),
  B("**Sistemas embebidos con recursos limitados:** presupuestar 2 KB de RAM entre pilas, colas y kernel; medir pilas libres; mover constantes a flash."),
  B("**Visión por computadora:** homografía, segmentación por color, morfología, calibración de cámara y medición en milímetros."),
  B("**Estimación y control:** filtro de Kalman, compensación de latencia, predicción con rebotes, control todo-o-nada con estimación por tiempo."),
  B("**Electrónica de potencia:** puentes H, aislamiento entre lógica y potencia, cargas inductivas, fuentes separadas y tierra común."),
  B("**Método de ingeniería:** probar cada componente por separado, registrar datos (CSV y video), decidir con mediciones (latencia, búsqueda en cuadrícula de los umbrales) y documentar los cambios."),
  B("**Trabajo con hardware real:** diagnóstico de fallas intermitentes (cables, jumpers, relé dañado, fricción mecánica)."));

// 15
add(H1("15. Evidencia audiovisual"),
  ...TABLA("Videos solicitados (sección 15 del enunciado).",
    ["Video", "Evidencia disponible", "Estado"],
    [["Construcción o montaje", "Fotos y videos del armado en la carpeta de Drive del proyecto (Figuras 3, 5 y 6)", "Disponible"],
     ["Pruebas de movimiento de cada nave", "Calibración automática y modo manual", "Por grabar con el firmware FreeRTOS"],
     ["Prueba del golpe", "Prueba con la tecla j/k", "Por grabar"],
     ["Calibración o validación de la detección", "registros/20261030_*.mp4 y 20261102_*.mp4 (seguimiento con el estimador)", "Disponible"],
     ["Detección de anotaciones y marcador", "registros/20261103_*.mp4 (marcador en pantalla y LCD)", "Disponible"],
     ["Integración hardware–software", "registros/20261103_194123 (455 s, 103 golpes)", "Disponible (CSV); video del sistema completo por grabar"],
     ["Partida automática completa", "Partida hasta 10 goles", "Por grabar"]],
    [30, 48, 22]),
  P("Las fotografías y los videos de la construcción, del prototipo LEGO y de las primeras pruebas están en la carpeta de Drive del proyecto: https://drive.google.com/drive/folders/1vlkfr6HJXub9V8-3F7fFBQIXRdYFUJa1 . El código fuente está en https://github.com/HermanEcheverria/Porteros ."),
  P("Los videos de `vision/registros` muestran la información de diagnóstico que pide el enunciado: modo, cuadros por segundo, posición y velocidad de la bola, objetivo de cada portero, tiempo hasta el cruce y marcador."));

// 16
add(H1("16. Limitaciones y trabajo futuro"),
  B("**Golpe a tiempo ≈ 40 %:** el límite viene de la latencia de la cámara. Propuesta: mover el sensor infrarrojo a la paleta para que el Arduino dispare el golpe localmente con una interrupción, sin esperar a la laptop."),
  B("**Posición sin encoder:** un encoder en el motor eliminaría el error por tiempo."),
  B("**Portero derecho con fricción variable:** revisar la banda y el riel; su calibración falla algunos días."),
  B("**Cobertura del portero izquierdo desplazada:** correr su riel ≈ 40 mm para centrarlo en la portería."),
  B("**Recalibración de la cámara:** una base fija para el teléfono evitaría recalibrar cada día."),
  B("**Paredes transparentes y bola de acero** como en la referencia, si se cambia la visión por color por otro método."));

// Anexo
add(H1("Anexo A. Comandos de operación y prueba"),
  ...TABLA("Teclas de la ventana de la cámara (laptop).",
    ["Tecla", "Acción"],
    [["K", "Recalibrar las esquinas de la cancha (4 clics)"], ["M / G", "Modo color/fondo; guardar el color de la bola"],
     ["A", "Modo automático on/off"], ["R", "Grabar registro CSV + MP4"], ["N", "Marcador a 0-0"],
     ["L", "Recalibrar los carros"], ["C", "Cambiar de cámara"], ["Esc", "Salir"]],
    [15, 85]),
  ...TABLA("Teclas del monitor serie (Arduino, 115200 baud).",
    ["Tecla", "Acción"],
    [["a / d", "Mover a la izquierda / derecha (mientras se mantiene)"], ["x / espacio", "Soltar / frenar"],
     ["w / s", "Subir / bajar el PWM manual"], ["k", "Golpe"], ["j", "Solenoide encendido 1 s (medir con multímetro)"],
     ["c", "Recalibrar"], ["p / v", "Estado / estado en vivo"], ["m", "Mediciones de tiempo real y pila libre"]],
    [15, 85]),
  H2("Anexo B. Fragmento del firmware: creación de las tareas"),
  ...CODIGO([
    "colaObjetivo = xQueueCreate(1, sizeof(int));        // buzón: siempre el objetivo más nuevo",
    "colaOrden    = xQueueCreate(4, sizeof(char));",
    "colaLCD      = xQueueCreate(2, sizeof(MsgLCD));",
    "mtxSerial    = xSemaphoreCreateMutex();",
    "tmrGolpe     = xTimerCreate(\"Golpe\", 1, pdFALSE, NULL, finGolpe);   // de un disparo",
    "xTaskCreate(tareaControl, \"Ctrl\", 180, NULL, 3, &hControl);",
    "xTaskCreate(tareaSerial,  \"Ser\",  150, NULL, 2, &hSerial);",
    "attachInterrupt(digitalPinToInterrupt(FIN_IZQ), isrTope, CHANGE);",
    "attachInterrupt(digitalPinToInterrupt(FIN_DER), isrTope, CHANGE);",
    "",
    "void isrTope() {                                   // solo marca el instante y despierta al control",
    "  tIsrTope = micros();",
    "  BaseType_t despertar = pdFALSE;",
    "  vTaskNotifyGiveFromISR(hControl, &despertar);",
    "  if (despertar == pdTRUE) portYIELD_FROM_ISR();",
    "}",
  ]));

// ---------- documento ----------
const doc = new Document({
  creator: "Equipo Porteros Robot", title: "Porteros Robot - Documento técnico",
  styles: {
    default: { document: { run: { font: FUENTE, size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FUENTE, size: 32, bold: true, color: AZUL }, paragraph: { spacing: { before: 240, after: 160 }, keepNext: true, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FUENTE, size: 26, bold: true, color: "2E75B6" }, paragraph: { spacing: { before: 200, after: 100 }, keepNext: true, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FUENTE, size: 23, bold: true }, paragraph: { spacing: { before: 160, after: 80 }, keepNext: true, outlineLevel: 2 } },
    ],
  },
  numbering: { config: [
    { reference: "vinetas", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 540, hanging: 270 } } } }] },
    { reference: "numeros", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 540, hanging: 300 } } } }] },
  ] },
  sections: [
    { properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } } },
      children: portada },
    { properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } } },
      headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT,
        children: [new TextRun({ text: "Sistemas Informáticos en Tiempo Real  |  Porteros Robot", size: 16, color: "808080" })] })] }) },
      footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
        children: [new TextRun({ children: ["Página ", PageNumber.CURRENT], size: 18, color: "808080" })] })] }) },
      children: c },
  ],
});

const salida = path.join(__dirname, "Documento_Tecnico_Porteros_Robot.docx");
Packer.toBuffer(doc).then((b) => { fs.writeFileSync(salida, b); console.log("OK", salida); });
