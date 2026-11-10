// programa integral: arreglos, foreach, clases, herencia, metodos y try/catch
class Figura {
  let nombre: string = "figura";
  function area(): integer { return 0; }
  function describir(): string { return this.nombre; }
}
class Rectangulo : Figura {
  let ancho: integer;
  let alto: integer;
  function constructor(ancho: integer, alto: integer) {
    this.ancho = ancho;
    this.alto = alto;
    this.nombre = "rectangulo";
  }
  function area(): integer { return this.ancho * this.alto; }
}
class Cuadrado : Rectangulo {
  function constructor(lado: integer) {
    this.ancho = lado;
    this.alto = lado;
    this.nombre = "cuadrado";
  }
}
function sumarAreas(figuras: Rectangulo[]): integer {
  let total: integer = 0;
  foreach (f in figuras) {
    total = total + f.area();
  }
  return total;
}
// los arreglos son invariantes: el literal tiene tipo Rectangulo[] (ancestro comun)
let figuras: Rectangulo[] = [new Rectangulo(2, 3), new Cuadrado(4)];
let areas: integer[] = [0, 0];
let i: integer = 0;
while (i < 2) {
  areas[i] = figuras[i].area();
  i = i + 1;
}
try {
  print(figuras[0].describir());
  print(sumarAreas(figuras));
  print(areas[3]);
} catch (err) {
  print("error: " + err);
}
