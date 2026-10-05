  ARG 5
  CALL t0, fn::factorial, argc=1
  PRINT t0
  ARG 10
  CALL t0, fn::fibonacci, argc=1
  PRINT t0
  ARG 4
  CALL t1, fn::esPar, argc=1
  PRINT t1

FUNC_BEGIN fn::factorial, frame=1
  t0 = BIN <=, n@frame[0], 1
  IF_FALSE t0, L_if_end_0
  RETURN 1
LABEL L_if_end_0
  t1 = BIN -, n@frame[0], 1
  ARG t1
  CALL t1, fn::factorial, argc=1
  t2 = BIN *, n@frame[0], t1
  RETURN t2
FUNC_END fn::factorial, temps=2

FUNC_BEGIN fn::fibonacci, frame=1
  t0 = BIN <, n@frame[0], 2
  IF_FALSE t0, L_if_end_1
  RETURN n@frame[0]
LABEL L_if_end_1
  t1 = BIN -, n@frame[0], 1
  ARG t1
  CALL t1, fn::fibonacci, argc=1
  t2 = BIN -, n@frame[0], 2
  ARG t2
  CALL t2, fn::fibonacci, argc=1
  t3 = BIN +, t1, t2
  RETURN t3
FUNC_END fn::fibonacci, temps=3

FUNC_BEGIN fn::esPar, frame=1
  t0 = BIN ==, n@frame[0], 0
  IF_FALSE t0, L_if_end_2
  RETURN true
LABEL L_if_end_2
  t1 = BIN -, n@frame[0], 1
  ARG t1
  CALL t0, fn::esImpar, argc=1
  RETURN t0
FUNC_END fn::esPar, temps=1

FUNC_BEGIN fn::esImpar, frame=1
  t0 = BIN ==, n@frame[0], 0
  IF_FALSE t0, L_if_end_3
  RETURN false
LABEL L_if_end_3
  t1 = BIN -, n@frame[0], 1
  ARG t1
  CALL t0, fn::esPar, argc=1
  RETURN t0
FUNC_END fn::esImpar, temps=1
