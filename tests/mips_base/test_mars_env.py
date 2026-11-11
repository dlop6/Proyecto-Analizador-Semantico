"""infraestructura: el helper tiene que distinguir exito, error de ensamblado, de ejecucion y limite de pasos."""
import pytest

from tests.mips_base.mars_runner import JAR_PATH, run_mars

PRINT_42 = ".text\nmain:\n li $a0, 42\n li $v0, 1\n syscall\n li $v0, 10\n syscall\n"


def test_jar_de_mars_esta_presente():
    assert JAR_PATH.is_file(), "correr tools/fetch_mars.sh o tools/fetch_mars.ps1"


def test_programa_valido_imprime_y_devuelve_registros():
    result = run_mars(PRINT_42, registers=("$sp", "$fp"))
    assert result.ok
    assert result.stdout.strip() == "42"
    assert result.registers["$sp"] == 0x7FFFEFFC
    assert result.registers["$fp"] == 0


def test_error_de_ensamblado_se_detecta():
    result = run_mars(".text\nmain:\n bogus $t0\n")
    assert result.assembly_error and not result.runtime_error and not result.ok


def test_error_de_ejecucion_se_detecta():
    result = run_mars(".text\nmain:\n li $t0, 0\n lw $t2, 0($t0)\n")
    assert result.runtime_error and not result.assembly_error and not result.ok


def test_limite_de_pasos_corta_un_bucle_infinito():
    result = run_mars(".text\nmain:\nloop:\n j loop\n", max_steps=500)
    assert result.step_limit_hit and not result.ok


def test_division_por_cero_es_error_de_ejecucion():
    result = run_mars(".text\nmain:\n li $t0, 5\n li $t1, 0\n div $t2, $t0, $t1\n li $v0, 10\n syscall\n")
    # el backend tiene que chequear el divisor antes: mars no deja seguir
    assert result.runtime_error and "break instruction" in result.raw


def test_lw_con_etiqueta_mas_offset_jalr_y_div_de_tres_operandos_funcionan():
    source = (
        ".data\narr: .word 7, 9\n.text\nmain:\n lw $t0, arr+4\n la $t1, f\n jalr $t1\n"
        " li $v0, 10\n syscall\nf:\n li $t3, 20\n li $t4, 6\n div $t5, $t3, $t4\n rem $t6, $t3, $t4\n jr $ra\n"
    )
    result = run_mars(source, registers=("$t0", "$t5", "$t6"))
    assert result.ok
    assert result.registers == {"$t0": 9, "$t5": 3, "$t6": 2}


def test_el_limite_de_pasos_es_obligatorio_y_positivo():
    with pytest.raises(ValueError):
        run_mars(PRINT_42, max_steps=0)


def test_etiquetas_con_punto_son_validas_y_con_dos_puntos_no():
    assert run_mars(".text\nfoo.bar:\n li $v0, 10\n syscall\n").ok
    assert run_mars(".text\nfoo::bar:\n nop\n").assembly_error
