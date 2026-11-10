  t0 = NEW_ARR 2
  t1 = NEW_OBJ Rectangulo, fields=3
  SET_FIELD t1, nombre@field[0], "figura"
  ARG t1
  ARG 2
  ARG 3
  CALL fn::Rectangulo.constructor, argc=3
  ARR_SET t0, 0, t1
  t1 = NEW_OBJ Cuadrado, fields=3
  SET_FIELD t1, nombre@field[0], "figura"
  ARG t1
  ARG 4
  CALL fn::Cuadrado.constructor, argc=2
  ARR_SET t0, 1, t1
  MOV figuras@global[0], t0
  t0 = NEW_ARR 2
  ARR_SET t0, 0, 0
  ARR_SET t0, 1, 0
  MOV areas@global[1], t0
  MOV i@global[2], 0
LABEL L_while_cond_3
  t2 = BIN <, i@global[2], 2
  IF_FALSE t2, L_while_end_4
  MOV t0, areas@global[1]
  MOV t3, i@global[2]
  t1 = ARR_GET figuras@global[0], i@global[2]
  CALL_METHOD t4, t1, area[0], argc=0
  ARR_SET t0, t3, t4
  t3 = BIN +, i@global[2], 1
  MOV i@global[2], t3
  GOTO L_while_cond_3
LABEL L_while_end_4
  TRY_BEGIN L_try_handler_5
  t0 = ARR_GET figuras@global[0], 0
  CALL_METHOD t5, t0, describir[1], argc=0
  PRINT t5
  ARG figuras@global[0]
  CALL t3, fn::sumarAreas, argc=1
  PRINT t3
  t3 = ARR_GET areas@global[1], 3
  PRINT t3
  TRY_END
  GOTO L_try_end_6
LABEL L_try_handler_5
  CATCH err@global[3]
  t5 = BIN +, "error: ", err@global[3]
  PRINT t5
LABEL L_try_end_6

FUNC_BEGIN fn::Figura.area, frame=1
  RETURN 0
FUNC_END fn::Figura.area, temps=0

FUNC_BEGIN fn::Figura.describir, frame=1
  t0 = GET_FIELD this@frame[0], nombre@field[0]
  RETURN t0
FUNC_END fn::Figura.describir, temps=1

FUNC_BEGIN fn::Rectangulo.constructor, frame=3
  SET_FIELD this@frame[0], ancho@field[1], ancho@frame[1]
  SET_FIELD this@frame[0], alto@field[2], alto@frame[2]
  SET_FIELD this@frame[0], nombre@field[0], "rectangulo"
  RETURN
FUNC_END fn::Rectangulo.constructor, temps=0

FUNC_BEGIN fn::Rectangulo.area, frame=1
  t0 = GET_FIELD this@frame[0], ancho@field[1]
  t1 = GET_FIELD this@frame[0], alto@field[2]
  t2 = BIN *, t0, t1
  RETURN t2
FUNC_END fn::Rectangulo.area, temps=3

FUNC_BEGIN fn::Cuadrado.constructor, frame=2
  SET_FIELD this@frame[0], ancho@field[1], lado@frame[1]
  SET_FIELD this@frame[0], alto@field[2], lado@frame[1]
  SET_FIELD this@frame[0], nombre@field[0], "cuadrado"
  RETURN
FUNC_END fn::Cuadrado.constructor, temps=0

FUNC_BEGIN fn::sumarAreas, frame=3
  MOV total@frame[1], 0
  MOV t0, figuras@frame[0]
  MOV t1, 0
  t2 = LEN t0
LABEL L_foreach_cond_0
  t3 = BIN <, t1, t2
  IF_FALSE t3, L_foreach_end_2
  t4 = ARR_GET t0, t1
  MOV f@frame[2], t4
  CALL_METHOD t5, f@frame[2], area[0], argc=0
  t6 = BIN +, total@frame[1], t5
  MOV total@frame[1], t6
LABEL L_foreach_step_1
  t1 = BIN +, t1, 1
  GOTO L_foreach_cond_0
LABEL L_foreach_end_2
  RETURN total@frame[1]
FUNC_END fn::sumarAreas, temps=5
