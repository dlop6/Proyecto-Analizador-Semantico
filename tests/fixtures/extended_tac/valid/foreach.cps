// foreach: indice + LEN + ARR_GET, el arreglo se evalua una sola vez
let nombres: string[] = ["ana", "beto", "carla"];
let saludo: string = "";
foreach (nombre in nombres) {
  saludo = saludo + nombre;
  print(nombre);
}
print(saludo);
