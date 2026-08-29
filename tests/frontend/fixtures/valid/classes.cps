class Animal {
  let name: string;

  function constructor(name: string) {
    this.name = name;
  }

  function speak(): string {
    return this.name + " hace ruido.";
  }
}

class Perro : Animal {
  function speak(): string {
    return this.name + " ladra.";
  }
}

let p: Perro = new Perro("Rex");
print(p.speak());
