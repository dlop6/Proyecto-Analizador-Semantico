// inicializadores de atributos (en el new, antes del constructor) y clase sin constructor
class Contador {
  let valor: integer = 0;
  let nombre: string = "contador";
  function incrementar(): integer {
    this.valor = this.valor + 1;
    return this.valor;
  }
}
let c: Contador = new Contador();
c.incrementar();
print(c.incrementar());
