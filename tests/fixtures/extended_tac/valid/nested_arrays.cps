// arreglos multidimensionales: un arreglo cuyos elementos son arreglos
let matriz: integer[][] = [[1, 2], [3, 4]];
matriz[1][0] = matriz[0][1] + 5;
let fila: integer[] = matriz[1];
print(fila[0]);
