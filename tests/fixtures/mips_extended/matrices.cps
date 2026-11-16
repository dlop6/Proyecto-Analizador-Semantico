// matrices: arreglos cuyos elementos son arreglos
let matriz: integer[][] = [[1, 2, 3], [4, 5, 6]];
print(matriz[0][2]);
print(matriz[1][0]);

matriz[1][2] = matriz[0][0] + matriz[1][1];
print(matriz[1][2]);

let total: integer = 0;
foreach (fila in matriz) {
  foreach (valor in fila) {
    total = total + valor;
  }
}
print(total);

let fila: integer[] = matriz[0];
fila[0] = 100;
print(matriz[0][0]);
