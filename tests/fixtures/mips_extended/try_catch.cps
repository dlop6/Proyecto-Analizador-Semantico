// try/catch: captura local, anidada, propagada por dos funciones y codigo normal sin catch
let datos: integer[] = [1, 2, 3];

try {
  print("sin error");
} catch (e) {
  print("no se imprime");
}

try {
  print(datos[3]);
  print("no se imprime");
} catch (e) {
  print("capturado: " + e);
}

try {
  try {
    print(datos[-1]);
  } catch (interno) {
    print("interno: " + interno);
    print(10 / (datos[0] - 1));
  }
} catch (externo) {
  print("externo: " + externo);
}

function leer(i: integer): integer {
  return datos[i];
}
function intermedio(i: integer): integer {
  let valor: integer = leer(i);
  print("no se imprime si falla");
  return valor + 1;
}
try {
  print(intermedio(1));
  print(intermedio(7));
} catch (e) {
  print("propagado: " + e);
}

class Nodo {
  let valor: integer = 7;
}
let n: Nodo = null;
try {
  print(n.valor);
} catch (e) {
  print("objeto: " + e);
}
print("fin");
