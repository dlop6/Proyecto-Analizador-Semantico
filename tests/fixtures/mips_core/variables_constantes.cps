// variables globales y locales, constantes, valores por defecto y asignacion encadenada
const BASE: integer = 100;
let contador: integer = 0;
var nombre: string = "compiscript";
let activo: boolean = true;
let sinValor: integer;

function local(p: integer): integer {
    let a: integer;
    let b: integer = p + BASE;
    a = b * 2;
    return a;
}

contador = contador + 1;
let x: integer = 0;
let y: integer = 0;
x = y = BASE + contador;
print(contador);
print(nombre);
print(activo);
print(sinValor);
print(x);
print(y);
print(local(5));
