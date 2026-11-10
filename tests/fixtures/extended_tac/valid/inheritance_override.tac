  t0 = NEW_OBJ Perro, fields=3
  SET_FIELD t0, patas@field[1], 4
  SET_FIELD t0, raza@field[2], "mestizo"
  ARG t0
  ARG "Rex"
  CALL fn::Perro.constructor, argc=2
  MOV a@global[0], t0
  CALL_METHOD t1, a@global[0], presentarse[1], argc=0
  PRINT t1
  t0 = NEW_OBJ Perro, fields=3
  SET_FIELD t0, patas@field[1], 4
  SET_FIELD t0, raza@field[2], "mestizo"
  ARG t0
  ARG "Toby"
  CALL fn::Perro.constructor, argc=2
  MOV p@global[1], t0
  CALL_METHOD t1, p@global[1], correr[2], argc=0
  PRINT t1
  t2 = GET_FIELD p@global[1], patas@field[1]
  PRINT t2

FUNC_BEGIN fn::Animal.constructor, frame=2
  SET_FIELD this@frame[0], nombre@field[0], nombre@frame[1]
  RETURN
FUNC_END fn::Animal.constructor, temps=0

FUNC_BEGIN fn::Animal.hablar, frame=1
  RETURN "..."
FUNC_END fn::Animal.hablar, temps=0

FUNC_BEGIN fn::Animal.presentarse, frame=1
  t0 = GET_FIELD this@frame[0], nombre@field[0]
  t1 = BIN +, t0, " dice "
  CALL_METHOD t0, this@frame[0], hablar[0], argc=0
  t2 = BIN +, t1, t0
  RETURN t2
FUNC_END fn::Animal.presentarse, temps=3

FUNC_BEGIN fn::Perro.constructor, frame=2
  SET_FIELD this@frame[0], nombre@field[0], nombre@frame[1]
  RETURN
FUNC_END fn::Perro.constructor, temps=0

FUNC_BEGIN fn::Perro.hablar, frame=1
  RETURN "guau"
FUNC_END fn::Perro.hablar, temps=0

FUNC_BEGIN fn::Perro.correr, frame=1
  t0 = GET_FIELD this@frame[0], nombre@field[0]
  t1 = BIN +, t0, " corre"
  RETURN t1
FUNC_END fn::Perro.correr, temps=2
