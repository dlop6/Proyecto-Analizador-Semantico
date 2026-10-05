  MOV n@global[0], 4
  t0 = BIN %, n@global[0], 2
  t1 = BIN ==, t0, 0
  IF_FALSE t1, L_tern_else_0
  MOV t2, "par"
  GOTO L_tern_end_1
LABEL L_tern_else_0
  MOV t2, "impar"
LABEL L_tern_end_1
  MOV paridad@global[1], t2
  t1 = BIN <, n@global[0], 0
  IF_FALSE t1, L_tern_else_2
  t3 = UN -, n@global[0]
  MOV t0, t3
  GOTO L_tern_end_3
LABEL L_tern_else_2
  MOV t0, n@global[0]
LABEL L_tern_end_3
  MOV abs@global[2], t0
  t1 = BIN >, n@global[0], 10
  IF_FALSE t1, L_tern_else_4
  MOV t0, 2
  GOTO L_tern_end_5
LABEL L_tern_else_4
  t1 = BIN >, n@global[0], 2
  IF_FALSE t1, L_tern_else_6
  MOV t3, 1
  GOTO L_tern_end_7
LABEL L_tern_else_6
  MOV t3, 0
LABEL L_tern_end_7
  MOV t0, t3
LABEL L_tern_end_5
  MOV anidado@global[3], t0
