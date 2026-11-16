// comparaciones, !, && y || con cortocircuito
function avisa(nombre: string, valor: boolean): boolean {
    print("evalua " + nombre);
    return valor;
}
let n: integer = 7;
print(n == 7);
print(n != 7);
print(n < 10 && n > 5);
print(n <= 6 || n >= 8);
print(!(n > 3));
print(avisa("a", false) && avisa("b", true));
print(avisa("c", true) || avisa("d", true));
print(avisa("e", true) && avisa("f", false));
let rango: boolean = n > 0 && n < 100 && n % 2 == 1;
print(rango);
print(rango == !false);
