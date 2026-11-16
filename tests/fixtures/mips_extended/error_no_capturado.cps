// error de runtime sin try: termina de forma controlada con el mensaje
let datos: integer[] = [1, 2, 3];
function leer(i: integer): integer {
  return datos[i];
}
print(leer(0));
print(leer(5));
print("no se imprime");
