// if/else, while, do-while, for, switch, break, continue y ternario
let i: integer = 0;
let suma: integer = 0;
while (i < 5) {
    i = i + 1;
    if (i == 3) {
        continue;
    }
    suma = suma + i;
}
print(suma);

do {
    i = i - 2;
} while (i > 0);
print(i);

for (let k: integer = 1; k <= 20; k = k + 1) {
    if (k % 7 == 0) {
        print("multiplo de 7: " + k);
        break;
    }
}

for (let f: integer = 1; f <= 3; f = f + 1) {
    let fila: string = "";
    for (let c: integer = 1; c <= f; c = c + 1) {
        fila = fila + "*";
    }
    print(fila);
}

let dia: integer = 3;
switch (dia) {
    case 1:
        print("lunes");
    case 3:
        print("miercoles");
    case 5:
        print("viernes");
    default:
        print("otro dia");
}
switch (dia + 10) {
    case 1:
        print("no");
    default:
        print("default");
}

if (suma > 10) {
    print("suma grande");
} else {
    print("suma chica");
}
print(i < 0 ? "negativo" : "no negativo");
