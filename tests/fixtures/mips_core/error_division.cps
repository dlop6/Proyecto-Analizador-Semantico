// division entre cero: el error ($v1 = 1) sube por dos funciones y termina el programa
function dividir(a: integer, b: integer): integer {
    return a / b;
}
function promedio(total: integer, cantidad: integer): integer {
    let p: integer = dividir(total, cantidad);
    print("promedio calculado");
    return p;
}
print(promedio(90, 3));
print(promedio(10, 0));
print("esto no se imprime");
