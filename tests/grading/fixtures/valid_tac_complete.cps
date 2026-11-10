// Debe compilar sin diagnosticos y mostrar el TAC de todos los rubros:
// variables, aritmetica, logica, arreglos, control de flujo, funciones,
// recursion, clases, herencia, try/catch y reciclaje de temporales.
class Animal {
  let nombre: string;
  let energia: integer = 10;

  function constructor(nombre: string) {
    this.nombre = nombre;
  }

  function hablar(): string {
    return "...";
  }

  function presentarse(): string {
    return this.nombre + " dice " + this.hablar();
  }
}

class Perro : Animal {
  function constructor(nombre: string) {
    this.nombre = nombre;
  }

  function hablar(): string {
    return "guau";
  }
}

function factorial(n: integer): integer {
  if (n <= 1) {
    return 1;
  }
  return n * factorial(n - 1);
}

const LIMITE: integer = 3;
let perro: Animal = new Perro("Rex");
let numeros: integer[] = [1, 2, 3, 4];
let suma: integer = 0;

foreach (n in numeros) {
  if (n > LIMITE || n == 0) {
    break;
  }
  suma = suma + factorial(n);
}

let i: integer = 0;
while (i < 2 && suma > 0) {
  numeros[i] = numeros[i] * 2;
  i = i + 1;
}

switch (suma) {
  case 9:
    print("nueve");
  default:
    print(perro.presentarse());
}

try {
  print(numeros[10]);
} catch (error) {
  print("indice fuera de rango: " + error);
}
