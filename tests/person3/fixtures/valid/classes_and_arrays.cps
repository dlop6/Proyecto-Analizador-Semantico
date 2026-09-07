// fixture valida: herencia, this, new, override valido, llamadas a metodo heredado y
// propio, arreglos homogeneos/anidados/vacios, indices, foreach.

class Animal {
    let name: string;

    function constructor(name: string) {
        this.name = name;
    }

    function hablar(): string {
        return this.name + " hace ruido.";
    }

    function nombre(): string {
        return this.name;
    }
}

class Perro : Animal {
    function constructor(name: string) {
        this.name = name;
    }

    function hablar(): string {
        return this.name + " ladra.";
    }
}

let generico: Animal = new Animal("Bicho");
let perro: Animal = new Perro("Rex");
print(generico.hablar());
print(perro.hablar());
print(perro.nombre());

let numeros: integer[] = [1, 2, 3, 4, 5];
let matriz: integer[][] = [[1, 2], [3, 4]];
let vacio: integer[] = [];

print(numeros[0]);
print(matriz[0][1]);

numeros[0] = 10;
matriz[0][1] = 20;

foreach (n in numeros) {
    print(n);
}
