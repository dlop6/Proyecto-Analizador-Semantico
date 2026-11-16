// arreglos: literal, lectura, escritura indexada, longitud via foreach y arreglo vacio
let numeros: integer[] = [10, 20, 30, 40];
print(numeros[0]);
print(numeros[3]);
numeros[1] = numeros[0] + numeros[2];
print(numeros[1]);

let i: integer = 2;
numeros[i] = numeros[i] * 2;
print(numeros[i]);

let suma: integer = 0;
foreach (n in numeros) {
  suma = suma + n;
}
print(suma);

let vacio: integer[] = [];
let cuenta: integer = 0;
foreach (x in vacio) {
  cuenta = cuenta + 1;
}
print(cuenta);

let uno: string[] = ["solo"];
print(uno[0]);

let banderas: boolean[] = [true, false];
print(banderas[1]);
