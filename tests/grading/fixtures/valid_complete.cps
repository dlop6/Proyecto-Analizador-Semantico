// Debe compilar sin diagnosticos: tipos, funciones, clases, scopes y arreglos.
class Animal {
  let nombre: string;

  function constructor(nombre: string) {
    this.nombre = nombre;
  }

  function hablar(): string {
    return this.nombre;
  }
}

function sumar(a: integer, b: integer): integer {
  return a + b;
}

let animal: Animal = new Animal("Luna");
let numeros = [sumar(1, 2), 4];

foreach (n in numeros) {
  if (n > 0) {
    print(animal.hablar());
  }
}
