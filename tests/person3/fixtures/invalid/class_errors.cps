// fixture invalida: junta varios errores de clases para probar que se acumulan todos

class Animal {
    let name: string;

    function constructor(name: string) {
        this.name = name;
    }

    function hablar(n: integer): string {
        return this.name;
    }
}

class Perro : Animal {
    // firma distinta a la heredada (aridad y tipo de retorno) -> CPS-202
    function hablar(): boolean {
        return true;
    }
}

let a: Animal = new Animal("Rex");

print(a.edad);              // CPS-200: miembro inexistente
print(a.hablar("x", "y"));  // CPS-212: aridad incorrecta en llamada a metodo
print(a.hablar(true));      // CPS-213: argumento incompatible en llamada a metodo
print(a.name());            // CPS-201: 'name' no es un metodo invocable

let mal1: Animal = new Animal(1, 2, 3); // CPS-210: aridad incorrecta en 'new'
let mal2: Animal = new Animal(true);    // CPS-211: argumento incompatible en 'new'

a.name = 5; // CPS-203: tipo incompatible en la asignacion de un atributo

let n: integer = 5;
print(n.algo); // CPS-208: acceso a miembro sobre algo que no es un objeto
