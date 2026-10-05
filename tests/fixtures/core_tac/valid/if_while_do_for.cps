// if/else, while, do-while y for (con y sin condicion)
let i: integer = 0;
let suma: integer = 0;
if (i == 0) {
    print("cero");
} else {
    print("otro");
}
if (suma > 100) {
    print("grande");
}
while (i < 5) {
    suma = suma + i;
    i = i + 1;
}
do {
    i = i - 1;
} while (i > 0);
for (let k: integer = 0; k < 3; k = k + 1) {
    print(k);
}
for (i = 0; ; i = i + 1) {
    if (i > 2) {
        break;
    }
}
