  t0 = NEW_OBJ Saludo, fields=1
  SET_FIELD t0, texto@field[0], "hola"
  MOV s@global[0], t0
  ARG "mundo"
  CALL_METHOD t1, s@global[0], decir[0], argc=1
  PRINT t1

FUNC_BEGIN fn::Saludo.decir.armar, frame=0
  t0 = GET_FIELD this@frame^1[0], texto@field[0]
  t1 = BIN +, t0, " "
  t0 = BIN +, t1, nombre@frame^1[1]
  RETURN t0
FUNC_END fn::Saludo.decir.armar, temps=2

FUNC_BEGIN fn::Saludo.decir, frame=2
  CALL t0, fn::Saludo.decir.armar, argc=0, link=0
  RETURN t0
FUNC_END fn::Saludo.decir, temps=1
