// clases y objetos: new, constructor, this, campos con inicializador, metodos
class Contador {
  let valor: integer = 0;
  let nombre: string;
  function constructor(nombre: string, inicio: integer) {
    this.nombre = nombre;
    this.valor = inicio;
  }
  function incrementar(paso: integer): integer {
    this.valor = this.valor + paso;
    return this.valor;
  }
  function describir(): string {
    return this.nombre + "=" + this.valor;
  }
}

let c: Contador = new Contador("clics", 5);
print(c.incrementar(3));
print(c.incrementar(2));
print(c.describir());

let otro: Contador = new Contador("otro", 0);
otro.valor = 41;
print(otro.incrementar(1));
print(c.valor);

class Punto {
  let x: integer = 1;
  let y: integer = 2;
}
let p: Punto = new Punto();
p.y = p.x + 10;
print(p.y);
