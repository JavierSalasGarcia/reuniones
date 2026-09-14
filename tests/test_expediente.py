from datetime import datetime

from reuniones import expediente, informe


def _con_reunion(con, entorno, asunto="Revalidacion de materias", minuta="Acuerdo: entregar el dictamen."):
    pid = int(con.execute(
        "INSERT INTO personas (nombre, email, creado, actualizado) VALUES "
        "('Ana Ruiz', 'ana@uaemex.mx', '', '')").lastrowid)
    reunion_id = expediente.crear_reunion(con, pid, asunto, inicio=datetime(2026, 9, 14, 10, 30))
    ruta = entorno.entrada / "20260914_1030_minuta.txt"
    ruta.write_text(minuta, encoding="utf-8")
    expediente.adjuntar(con, reunion_id, ruta, "minuta", "20260914_1030")
    return pid, reunion_id


def test_archivo_queda_dentro_del_expediente_de_la_persona(con, entorno):
    pid, reunion_id = _con_reunion(con, entorno)
    archivo = expediente.archivos_de(con, reunion_id, "minuta")[0]
    ruta = entorno.datos / archivo["ruta"]
    assert ruta.parent.parent == entorno.expedientes
    assert "ana-ruiz" in ruta.parent.name
    assert archivo["sha256"] and archivo["bytes"] > 0


def test_briefing_resume_lo_que_importa(con, entorno):
    pid, reunion_id = _con_reunion(con, entorno)
    expediente.agregar_acuerdo(con, reunion_id, "Entregar constancia de estudios",
                               "Ana Ruiz", "2026-09-30")
    lineas = expediente.resumen_en_lineas(expediente.briefing(con, pid))
    texto = " ".join(lineas)
    assert "Ana Ruiz" in texto
    assert "Revalidacion" in texto
    assert "constancia" in texto
    assert "30/09/2026" in texto


def test_acuerdos_se_cierran_y_dejan_de_ser_pendientes(con, entorno):
    pid, reunion_id = _con_reunion(con, entorno)
    acuerdo_id = expediente.agregar_acuerdo(con, reunion_id, "Revisar el caso con Control Escolar")
    assert len(expediente.pendientes_de(con, pid)) == 1
    expediente.cerrar_acuerdo(con, acuerdo_id)
    assert expediente.pendientes_de(con, pid) == []


def test_minuta_en_pdf_se_genera(con, entorno):
    _, reunion_id = _con_reunion(con, entorno, minuta="Se acordó revisar la calificación.")
    expediente.agregar_acuerdo(con, reunion_id, "Revisar calificación", "Subdirección", "2026-10-01")
    pdf = informe.minuta_pdf(con, reunion_id)
    assert pdf.exists() and pdf.stat().st_size > 800
    assert pdf.read_bytes().startswith(b"%PDF")


def test_expediente_completo_en_pdf(con, entorno):
    pid, _ = _con_reunion(con, entorno)
    pdf = informe.expediente_pdf(con, pid)
    assert pdf.exists() and pdf.read_bytes().startswith(b"%PDF")


def test_historial_ordena_de_lo_mas_reciente_a_lo_mas_viejo(con, entorno):
    pid, _ = _con_reunion(con, entorno)
    expediente.crear_reunion(con, pid, "Caso nuevo", inicio=datetime(2026, 9, 20, 9, 0))
    expediente.crear_reunion(con, pid, "Caso viejo", inicio=datetime(2026, 1, 5, 9, 0))
    asuntos = [r["asunto"] for r in expediente.reuniones_de(con, pid)]
    assert asuntos[0] == "Caso nuevo" and asuntos[-1] == "Caso viejo"
