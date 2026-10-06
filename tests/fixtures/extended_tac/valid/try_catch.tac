  t0 = NEW_ARR 2
  ARR_SET t0, 0, 1
  ARR_SET t0, 1, 2
  MOV datos@global[0], t0
  TRY_BEGIN L_try_handler_2
  t1 = ARR_GET datos@global[0], 5
  PRINT t1
  TRY_END
  GOTO L_try_end_3
LABEL L_try_handler_2
  CATCH e@global[1]
  t2 = BIN +, "fuera de rango: ", e@global[1]
  PRINT t2
LABEL L_try_end_3
  ARG 0
  CALL t1, fn::leer, argc=1
  PRINT t1

FUNC_BEGIN fn::leer, frame=2
  TRY_BEGIN L_try_handler_0
  t0 = ARR_GET datos@global[0], i@frame[0]
  RETURN t0
  TRY_END
  GOTO L_try_end_1
LABEL L_try_handler_0
  CATCH error@frame[1]
  PRINT error@frame[1]
LABEL L_try_end_1
  t0 = UN -, 1
  RETURN t0
FUNC_END fn::leer, temps=1
