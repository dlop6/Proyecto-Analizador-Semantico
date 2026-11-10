// herencia: campos heredados primero, override reutiliza el slot del padre
class Animal {
  let nombre: string;
  let patas: integer = 4;
  function constructor(nombre: string) { this.nombre = nombre; }
  function hablar(): string { return "..."; }
  function presentarse(): string { return this.nombre + " dice " + this.hablar(); }
}
class Perro : Animal {
  let raza: string = "mestizo";
  function constructor(nombre: string) { this.nombre = nombre; }
  function hablar(): string { return "guau"; }
  function correr(): string { return this.nombre + " corre"; }
}
let a: Animal = new Perro("Rex");
print(a.presentarse());
let p: Perro = new Perro("Toby");
print(p.correr());
print(p.patas);
