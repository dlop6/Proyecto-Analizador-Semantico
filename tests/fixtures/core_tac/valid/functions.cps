// declaracion, parametros, return con y sin valor, llamadas como valor y como sentencia
function sumar(a: integer, b: integer): integer {
    return a + b;
}
function saludar(nombre: string) {
    print("hola " + nombre);
}
function nada() {
    return;
}
let total: integer = sumar(1, sumar(2, 3));
saludar("ana");
nada();
sumar(4, 5);
print(sumar(total, 1) * 2);
