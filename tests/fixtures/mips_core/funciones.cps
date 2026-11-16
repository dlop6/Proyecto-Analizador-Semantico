// parametros (0 a 5), retorno con y sin valor, llamadas como sentencia y como argumento
let llamadas: integer = 0;
function registrar() {
    llamadas = llamadas + 1;
}
function cero(): integer {
    registrar();
    return 42;
}
function uno(a: integer): integer {
    registrar();
    return a * 2;
}
function cinco(a: integer, b: integer, c: integer, d: integer, e: integer): integer {
    registrar();
    return a * 10000 + b * 1000 + c * 100 + d * 10 + e;
}
function saludo(nombre: string, veces: integer): string {
    let r: string = "";
    for (let i: integer = 0; i < veces; i = i + 1) {
        r = r + "hola " + nombre + "!";
    }
    return r;
}
function maximo(a: integer, b: integer): integer {
    if (a > b) {
        return a;
    }
    return b;
}
print(cero());
print(uno(uno(3)));
print(cinco(1, 2, 3, 4, 5));
print(cinco(uno(1), cero() / 42, maximo(3, 1), maximo(2, 4), 5));
print(saludo("ana", 2));
cero();
print(llamadas);
