// this desde una funcion anidada dentro de un metodo: acceso nonlocal por static link
class Saludo {
  let texto: string = "hola";
  function decir(nombre: string): string {
    function armar(): string {
      return this.texto + " " + nombre;
    }
    return armar();
  }
}
let s: Saludo = new Saludo();
print(s.decir("mundo"));
