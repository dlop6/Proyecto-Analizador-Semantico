// error semantico dentro de try/catch: tambien bloquea el ir
try {
  let x: integer = "texto";
} catch (e) {
  print(noDeclarado);
}
