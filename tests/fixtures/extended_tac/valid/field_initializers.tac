  t0 = NEW_OBJ Contador, fields=2
  SET_FIELD t0, valor@field[0], 0
  SET_FIELD t0, nombre@field[1], "contador"
  MOV c@global[0], t0
  CALL_METHOD c@global[0], incrementar[0], argc=0
  CALL_METHOD t1, c@global[0], incrementar[0], argc=0
  PRINT t1

FUNC_BEGIN fn::Contador.incrementar, frame=1
  t0 = GET_FIELD this@frame[0], valor@field[0]
  t1 = BIN +, t0, 1
  SET_FIELD this@frame[0], valor@field[0], t1
  t0 = GET_FIELD this@frame[0], valor@field[0]
  RETURN t0
FUNC_END fn::Contador.incrementar, temps=2
