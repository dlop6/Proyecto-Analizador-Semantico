  ARG 3
  CALL t0, fn::externa, argc=1
  PRINT t0

FUNC_BEGIN fn::externa.sumar.escalar, frame=0
  t0 = BIN *, acumulado@frame^2[1], base@frame^2[0]
  RETURN t0
FUNC_END fn::externa.sumar.escalar, temps=1

FUNC_BEGIN fn::externa.sumar, frame=1
  t0 = BIN +, acumulado@frame^1[1], n@frame[0]
  MOV acumulado@frame^1[1], t0
  CALL t0, fn::externa.sumar.escalar, argc=0, link=0
  RETURN t0
FUNC_END fn::externa.sumar, temps=1

FUNC_BEGIN fn::externa.doble, frame=1
  t0 = BIN *, n@frame[0], 2
  RETURN t0
FUNC_END fn::externa.doble, temps=1

FUNC_BEGIN fn::externa, frame=2
  MOV acumulado@frame[1], 0
  ARG 1
  CALL fn::externa.sumar, argc=1, link=0
  ARG base@frame[0]
  CALL t0, fn::externa.doble, argc=1
  ARG t0
  CALL t0, fn::externa.sumar, argc=1, link=0
  RETURN t0
FUNC_END fn::externa, temps=1
