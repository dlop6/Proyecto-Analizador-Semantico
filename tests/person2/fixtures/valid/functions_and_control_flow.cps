// fixture valida: cubre declaraciones, expresiones, funciones/recursion y control de flujo

let contador: integer = 0;
const limite: integer = 10;
let nombre = "compiscript";

function esPar(n: integer): boolean {
    return n % 2 == 0;
}

function factorial(n: integer): integer {
    if (n <= 1) {
        return 1;
    }
    return n * factorial(n - 1);
}

function combinar(a: integer, b: integer) {
    if (a > b) {
        return a;
    }
    return b;
}

while (contador < limite) {
    if (esPar(contador)) {
        print(contador);
    }
    contador = contador + 1;
}

for (let i: integer = 0; i < limite; i = i + 1) {
    switch (i) {
        case 0:
            print("cero");
        case 1:
            print("uno");
        default:
            print("otro");
    }
}

let resultado: integer = factorial(5);
let mayor = combinar(1, 2);
let esValido: boolean = resultado > 0 && mayor > 0 || false;
