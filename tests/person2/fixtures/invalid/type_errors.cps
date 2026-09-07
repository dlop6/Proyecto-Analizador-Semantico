// fixture invalida: junta varios errores de tipos para probar que se acumulan todos

let a: integer = "no es un entero";
const b: string = 5;

function suma(x: integer, y: integer): integer {
    return x + y;
}

let c = suma(1, "dos");
let d = w + 1;

if (a) {
    print("condicion no booleana");
}

function f(): integer {
    return "tipo incorrecto";
}

switch (a) {
    case "texto":
        print("case incompatible");
}
