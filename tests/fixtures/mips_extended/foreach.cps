// foreach con break y continue (reusan las etiquetas del lazo)
let datos: integer[] = [1, 2, 3, 4, 5, 6, 7, 8];
let pares: integer = 0;
foreach (d in datos) {
  if (d % 2 == 1) {
    continue;
  }
  if (d > 6) {
    break;
  }
  pares = pares + d;
  print(d);
}
print(pares);

let nombres: string[] = ["ana", "beto"];
let saludo: string = "hola";
foreach (nombre in nombres) {
  saludo = saludo + " " + nombre;
}
print(saludo);
