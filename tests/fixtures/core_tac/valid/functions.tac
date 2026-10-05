  ARG 1
  ARG 2
  ARG 3
  CALL t0, fn::sumar, argc=2
  ARG t0
  CALL t0, fn::sumar, argc=2
  MOV total@global[0], t0
  ARG "ana"
  CALL fn::saludar, argc=1
  CALL fn::nada, argc=0
  ARG 4
  ARG 5
  CALL fn::sumar, argc=2
  ARG total@global[0]
  ARG 1
  CALL t0, fn::sumar, argc=2
  t1 = BIN *, t0, 2
  PRINT t1

FUNC_BEGIN fn::sumar, frame=2
  t0 = BIN +, a@frame[0], b@frame[1]
  RETURN t0
FUNC_END fn::sumar, temps=1

FUNC_BEGIN fn::saludar, frame=1
  t0 = BIN +, "hola ", nombre@frame[0]
  PRINT t0
  RETURN
FUNC_END fn::saludar, temps=1

FUNC_BEGIN fn::nada, frame=0
  RETURN
FUNC_END fn::nada, temps=0
