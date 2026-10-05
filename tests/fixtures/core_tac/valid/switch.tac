  MOV opcion@global[0], 2
  MOV t0, opcion@global[0]
  t1 = BIN ==, t0, 1
  IF_TRUE t1, L_switch_case_0
  t1 = BIN ==, t0, 2
  IF_TRUE t1, L_switch_case_1
  GOTO L_switch_default_2
LABEL L_switch_case_0
  PRINT "uno"
  GOTO L_switch_end_3
LABEL L_switch_case_1
  PRINT "dos"
  GOTO L_switch_end_3
  GOTO L_switch_end_3
LABEL L_switch_default_2
  PRINT "otro"
  GOTO L_switch_end_3
LABEL L_switch_end_3
  t0 = BIN *, opcion@global[0], 2
  t1 = BIN ==, t0, 4
  IF_TRUE t1, L_switch_case_4
  GOTO L_switch_end_5
LABEL L_switch_case_4
  PRINT "cuatro"
  GOTO L_switch_end_5
LABEL L_switch_end_5
  MOV i@global[1], 0
LABEL L_while_cond_6
  t1 = BIN <, i@global[1], 3
  IF_FALSE t1, L_while_end_7
  t0 = BIN +, i@global[1], 1
  MOV i@global[1], t0
  MOV t0, i@global[1]
  t1 = BIN ==, t0, 2
  IF_TRUE t1, L_switch_case_8
  GOTO L_switch_default_9
LABEL L_switch_case_8
  GOTO L_while_cond_6
  GOTO L_switch_end_10
LABEL L_switch_default_9
  PRINT i@global[1]
  GOTO L_switch_end_10
LABEL L_switch_end_10
  GOTO L_while_cond_6
LABEL L_while_end_7
