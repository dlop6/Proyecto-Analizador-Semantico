// fixture invalida: junta varios errores de arreglos para probar que se acumulan todos

let mixto = [1, "dos", true];     // CPS-207: sin tipo comun entre los elementos

let numeros: integer[] = [1, 2, 3];
let indice: string = "cero";
print(numeros[indice]);           // CPS-205: el indice debe ser integer

let x: integer = 5;
print(x[0]);                      // CPS-206: no es indexable

numeros[0] = "no es un entero";   // CPS-204: tipo incompatible al asignar un elemento
