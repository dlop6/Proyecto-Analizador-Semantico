// try/catch: el error de runtime (indice fuera de rango) llega a la variable del catch
let datos: integer[] = [1, 2];
function leer(i: integer): integer {
  try {
    return datos[i];
  } catch (error) {
    print(error);
  }
  return -1;
}
try {
  print(datos[5]);
} catch (e) {
  print("fuera de rango: " + e);
}
print(leer(0));
