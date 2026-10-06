  MOV PI@global[0], 314
  MOV greeting@global[1], "Hello, Compiscript!"
  t0 = NEW_ARR 5
  ARR_SET t0, 0, 1
  ARR_SET t0, 1, 2
  ARR_SET t0, 2, 3
  ARR_SET t0, 3, 4
  ARR_SET t0, 4, 5
  MOV numbers@global[3], t0
  t0 = NEW_ARR 2
  t1 = NEW_ARR 2
  ARR_SET t1, 0, 1
  ARR_SET t1, 1, 2
  ARR_SET t0, 0, t1
  t1 = NEW_ARR 2
  ARR_SET t1, 0, 3
  ARR_SET t1, 1, 4
  ARR_SET t0, 1, t1
  MOV matrix@global[4], t0
  ARG 5
  CALL t2, fn::makeAdder, argc=1
  MOV addFive@global[5], t2
  t3 = BIN +, "5 + 1 = ", addFive@global[5]
  PRINT t3
  t4 = BIN >, addFive@global[5], 5
  IF_FALSE t4, L_if_else_0
  PRINT "Greater than 5"
  GOTO L_if_end_1
LABEL L_if_else_0
  PRINT "5 or less"
LABEL L_if_end_1
LABEL L_while_cond_2
  t4 = BIN <, addFive@global[5], 10
  IF_FALSE t4, L_while_end_3
  t2 = BIN +, addFive@global[5], 1
  MOV addFive@global[5], t2
  GOTO L_while_cond_2
LABEL L_while_end_3
LABEL L_do_body_4
  t3 = BIN +, "Result is now ", addFive@global[5]
  PRINT t3
  t2 = BIN -, addFive@global[5], 1
  MOV addFive@global[5], t2
LABEL L_do_cond_5
  t4 = BIN >, addFive@global[5], 7
  IF_TRUE t4, L_do_body_4
LABEL L_do_end_6
  MOV i@global[9], 0
LABEL L_for_cond_7
  t4 = BIN <, i@global[9], 3
  IF_FALSE t4, L_for_end_9
  t3 = BIN +, "Loop index: ", i@global[9]
  PRINT t3
LABEL L_for_step_8
  t2 = BIN +, i@global[9], 1
  MOV i@global[9], t2
  GOTO L_for_cond_7
LABEL L_for_end_9
  MOV t0, numbers@global[3]
  MOV t2, 0
  t5 = LEN t0
LABEL L_foreach_cond_10
  t4 = BIN <, t2, t5
  IF_FALSE t4, L_foreach_end_12
  t6 = ARR_GET t0, t2
  MOV n@global[10], t6
  t4 = BIN ==, n@global[10], 3
  IF_FALSE t4, L_if_end_13
  GOTO L_foreach_step_11
LABEL L_if_end_13
  t3 = BIN +, "Number: ", n@global[10]
  PRINT t3
  t4 = BIN >, n@global[10], 4
  IF_FALSE t4, L_if_end_14
  GOTO L_foreach_end_12
LABEL L_if_end_14
LABEL L_foreach_step_11
  t2 = BIN +, t2, 1
  GOTO L_foreach_cond_10
LABEL L_foreach_end_12
  MOV t2, addFive@global[5]
  t4 = BIN ==, t2, 7
  IF_TRUE t4, L_switch_case_15
  t4 = BIN ==, t2, 6
  IF_TRUE t4, L_switch_case_16
  GOTO L_switch_default_17
LABEL L_switch_case_15
  PRINT "It's seven"
  GOTO L_switch_end_18
LABEL L_switch_case_16
  PRINT "It's six"
  GOTO L_switch_end_18
LABEL L_switch_default_17
  PRINT "Something else"
  GOTO L_switch_end_18
LABEL L_switch_end_18
  TRY_BEGIN L_try_handler_19
  t2 = ARR_GET numbers@global[3], 10
  MOV risky@global[11], t2
  t3 = BIN +, "Risky access: ", risky@global[11]
  PRINT t3
  TRY_END
  GOTO L_try_end_20
LABEL L_try_handler_19
  CATCH err@global[12]
  t3 = BIN +, "Caught an error: ", err@global[12]
  PRINT t3
LABEL L_try_end_20
  t0 = NEW_OBJ Dog, fields=1
  ARG t0
  ARG "Rex"
  CALL fn::Animal.constructor, argc=2
  MOV dog@global[6], t0
  CALL_METHOD t3, dog@global[6], speak[0], argc=0
  PRINT t3
  t2 = ARR_GET numbers@global[3], 0
  MOV first@global[7], t2
  t3 = BIN +, "First number: ", first@global[7]
  PRINT t3
  ARG 2
  CALL t0, fn::getMultiples, argc=1
  MOV multiples@global[8], t0
  t2 = ARR_GET multiples@global[8], 0
  t3 = BIN +, "Multiples of 2: ", t2
  t7 = BIN +, t3, ", "
  t2 = ARR_GET multiples@global[8], 1
  t3 = BIN +, t7, t2
  PRINT t3
  PRINT "Program finished."

FUNC_BEGIN fn::makeAdder, frame=1
  t0 = BIN +, x@frame[0], 1
  RETURN t0
FUNC_END fn::makeAdder, temps=1

FUNC_BEGIN fn::Animal.constructor, frame=2
  SET_FIELD this@frame[0], name@field[0], name@frame[1]
  RETURN
FUNC_END fn::Animal.constructor, temps=0

FUNC_BEGIN fn::Animal.speak, frame=1
  t0 = GET_FIELD this@frame[0], name@field[0]
  t1 = BIN +, t0, " makes a sound."
  RETURN t1
FUNC_END fn::Animal.speak, temps=2

FUNC_BEGIN fn::Dog.speak, frame=1
  t0 = GET_FIELD this@frame[0], name@field[0]
  t1 = BIN +, t0, " barks."
  RETURN t1
FUNC_END fn::Dog.speak, temps=2

FUNC_BEGIN fn::getMultiples, frame=2
  t0 = NEW_ARR 5
  t1 = BIN *, n@frame[0], 1
  ARR_SET t0, 0, t1
  t1 = BIN *, n@frame[0], 2
  ARR_SET t0, 1, t1
  t1 = BIN *, n@frame[0], 3
  ARR_SET t0, 2, t1
  t1 = BIN *, n@frame[0], 4
  ARR_SET t0, 3, t1
  t1 = BIN *, n@frame[0], 5
  ARR_SET t0, 4, t1
  MOV result@frame[1], t0
  RETURN result@frame[1]
FUNC_END fn::getMultiples, temps=2

FUNC_BEGIN fn::factorial, frame=1
  t0 = BIN <=, n@frame[0], 1
  IF_FALSE t0, L_if_end_21
  RETURN 1
LABEL L_if_end_21
  t1 = BIN -, n@frame[0], 1
  ARG t1
  CALL t1, fn::factorial, argc=1
  t2 = BIN *, n@frame[0], t1
  RETURN t2
FUNC_END fn::factorial, temps=2
