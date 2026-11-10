// break y continue dentro de foreach anidados saltan al bucle mas interno
let tabla: integer[][] = [[1, 2, 3], [4, 5, 6]];
let total: integer = 0;
foreach (fila in tabla) {
  foreach (valor in fila) {
    if (valor == 2) { continue; }
    if (valor > 5) { break; }
    total = total + valor;
  }
}
print(total);
