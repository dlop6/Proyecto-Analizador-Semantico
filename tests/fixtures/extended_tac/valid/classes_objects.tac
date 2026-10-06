  t0 = NEW_OBJ Punto, fields=2
  ARG t0
  ARG 3
  ARG 4
  CALL fn::Punto.constructor, argc=3
  MOV p@global[0], t0
  ARG 2
  CALL_METHOD p@global[0], mover[1], argc=1
  SET_FIELD p@global[0], y@field[1], 10
  CALL_METHOD t1, p@global[0], suma[0], argc=0
  PRINT t1
  t1 = GET_FIELD p@global[0], x@field[0]
  PRINT t1

FUNC_BEGIN fn::Punto.constructor, frame=3
  SET_FIELD this@frame[0], x@field[0], x@frame[1]
  SET_FIELD this@frame[0], y@field[1], y@frame[2]
  RETURN
FUNC_END fn::Punto.constructor, temps=0

FUNC_BEGIN fn::Punto.suma, frame=1
  t0 = GET_FIELD this@frame[0], x@field[0]
  t1 = GET_FIELD this@frame[0], y@field[1]
  t2 = BIN +, t0, t1
  RETURN t2
FUNC_END fn::Punto.suma, temps=3

FUNC_BEGIN fn::Punto.mover, frame=2
  t0 = GET_FIELD this@frame[0], x@field[0]
  t1 = BIN +, t0, dx@frame[1]
  SET_FIELD this@frame[0], x@field[0], t1
  RETURN
FUNC_END fn::Punto.mover, temps=2
