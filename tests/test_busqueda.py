from datetime import datetime

from reuniones import busqueda, expediente


def _minuta(con, entorno, nombre, email, sello, texto, asunto=""):
    pid = int(con.execute(
        "INSERT INTO personas (nombre, email, creado, actualizado) VALUES (?, ?, '', '')",
        (nombre, email)).lastrowid)
    inicio = datetime.strptime(sello, "%Y%m%d_%H%M")
    reunion_id = expediente.crear_reunion(con, pid, asunto, inicio=inicio)
    ruta = entorno.entrada / f"{sello}_minuta.txt"
    ruta.write_text(texto, encoding="utf-8")
    archivo_id = expediente.adjuntar(con, reunion_id, ruta, "minuta", sello)
    busqueda.indexar_archivo(con, archivo_id)
    return reunion_id


def test_fragmenta_con_traslape():
    texto = " ".join(str(i) for i in range(400))
    piezas = busqueda.fragmentar(texto, 100, 20)
    assert len(piezas) == 5
    assert piezas[0].split()[-20:] == piezas[1].split()[:20]


def test_encuentra_por_palabra_clave(con, entorno):
    reunion_id = _minuta(con, entorno, "Ana Ruiz", "ana@uaemex.mx", "20260914_1030",
                         "Se revisó su solicitud de revalidación de materias de otra universidad.",
                         asunto="Revalidación")
    _minuta(con, entorno, "Luis Mora", "luis@uaemex.mx", "20260915_1030",
            "Se trató el pago de la beca de manutención del semestre.")

    hallazgos = busqueda.buscar(con, "revalidacion")
    assert hallazgos and hallazgos[0].reunion_id == reunion_id
    assert hallazgos[0].persona == "Ana Ruiz"


def test_la_busqueda_ignora_acentos(con, entorno):
    _minuta(con, entorno, "Ana Ruiz", "ana@uaemex.mx", "20260914_1030",
            "Revisión de la calificación del examen extraordinario.")
    assert busqueda.buscar(con, "calificacion")
    assert busqueda.buscar(con, "revisión")


def test_puede_limitarse_a_una_persona(con, entorno):
    uno = _minuta(con, entorno, "Ana Ruiz", "ana@uaemex.mx", "20260914_1030",
                  "Solicitud de constancia de estudios.")
    _minuta(con, entorno, "Luis Mora", "luis@uaemex.mx", "20260915_1030",
            "Solicitud de constancia de estudios.")
    persona_id = con.execute("SELECT persona_id FROM reuniones WHERE id = ?", (uno,)).fetchone()[0]
    hallazgos = busqueda.buscar(con, "constancia", persona_id=persona_id)
    assert hallazgos and {h.persona for h in hallazgos} == {"Ana Ruiz"}


def test_reindexar_recorre_todo(con, entorno):
    _minuta(con, entorno, "Ana Ruiz", "ana@uaemex.mx", "20260914_1030", "Texto de prueba uno.")
    _minuta(con, entorno, "Luis Mora", "luis@uaemex.mx", "20260915_1030", "Texto de prueba dos.")
    assert busqueda.reindexar(con) == 2


def test_consulta_vacia_no_devuelve_nada(con):
    assert busqueda.buscar(con, "   ") == []
