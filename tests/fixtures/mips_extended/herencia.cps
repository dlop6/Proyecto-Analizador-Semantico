// herencia: campos heredados, override por vtable, metodo heredado y referencia al padre
class Figura {
  let nombre: string;
  let lados: integer = 0;
  function constructor(nombre: string) { this.nombre = nombre; }
  function area(): integer { return 0; }
  function describir(): string { return this.nombre + " con area " + this.area(); }
}
class Rectangulo : Figura {
  let ancho: integer;
  let alto: integer;
  function constructor(ancho: integer, alto: integer) {
    this.nombre = "rectangulo";
    this.lados = 4;
    this.ancho = ancho;
    this.alto = alto;
  }
  function area(): integer { return this.ancho * this.alto; }
}
class Cuadrado : Rectangulo {
  function constructor(lado: integer) {
    this.nombre = "cuadrado";
    this.lados = 4;
    this.ancho = lado;
    this.alto = lado;
  }
}
class Triangulo : Figura {
  let base: integer;
  let altura: integer;
  function constructor(base: integer, altura: integer) {
    this.nombre = "triangulo";
    this.lados = 3;
    this.base = base;
    this.altura = altura;
  }
  function area(): integer { return this.base * this.altura / 2; }
}

let figuras: Figura[] = [new Rectangulo(3, 4), new Cuadrado(5), new Triangulo(6, 2), new Figura("punto")];
foreach (f in figuras) {
  print(f.describir());
}
let r: Rectangulo = new Cuadrado(2);
print(r.area());
print(r.lados);
let g: Figura = r;
print(g.area());
