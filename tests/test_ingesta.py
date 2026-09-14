from datetime import datetime, timedelta
from pathlib import Path

from reuniones import expediente, ingesta


def _persona(con, nombre, email):
    cursor = con.execute(
        "INSERT INTO personas (nombre, email, creado, actualizado) VALUES (?, ?, '', '')",
        (nombre, email),
    )
    return int(cursor.lastrowid)


def _archivo(entorno, nombre, texto="Hablante 1: buenos dias.\nHablante 2: buenos dias."):
    ruta = entorno.entrada / nombre
    ruta.write_text(texto, encoding="utf-8")
    return ruta


def test_analiza_el_nombre_del_telefono():
    analisis = ingesta.analizar_nombre("20260914_1035_original.txt")
    assert analisis.clase == "original"
    assert analisis.momento == datetime(2026, 9, 14, 10, 35)
    assert ingesta.analizar_nombre("20260914_1035_minuta.TXT").clase == "minuta"
    assert ingesta.analizar_nombre("notas sueltas.txt") is None
    assert ingesta.analizar_nombre("20260914_1035_original.mp3") is None


def test_asocia_con_la_reunion_mas_cercana(con, entorno):
    pid = _persona(con, "Ana Ruiz", "ana@uaemex.mx")
    inicio = datetime(2026, 9, 14, 10, 30)
    reunion_id = expediente.crear_reunion(con, pid, "Revalidacion", inicio=inicio)

    desenlace = ingesta.asociar(con, _archivo(entorno, "20260914_1035_original.txt"))
    assert desenlace.estado == "asociado"
    assert desenlace.reunion_id == reunion_id

    archivos = expediente.archivos_de(con, reunion_id, "original")
    assert len(archivos) == 1
    guardado = entorno.datos / archivos[0]["ruta"]
    assert guardado.exists() and guardado.name == "20260914_1035_original.txt"
    assert "Hablante 1" in expediente.texto_de(archivos[0])


def test_minuta_y_original_conviven_en_la_misma_reunion(con, entorno):
    pid = _persona(con, "Luis Mora", "luis@uaemex.mx")
    reunion_id = expediente.crear_reunion(con, pid, "Beca", inicio=datetime(2026, 9, 14, 12, 0))
    ingesta.asociar(con, _archivo(entorno, "20260914_1200_original.txt"))
    ingesta.asociar(con, _archivo(entorno, "20260914_1200_minuta.txt", "Acuerdo: entregar constancia."))
    assert len(expediente.archivos_de(con, reunion_id)) == 2


def test_sin_reunion_cercana_va_a_la_bandeja(con, entorno):
    pid = _persona(con, "Sara Diaz", "sara@uaemex.mx")
    expediente.crear_reunion(con, pid, "Otra cosa", inicio=datetime(2026, 9, 10, 9, 0))
    desenlace = ingesta.asociar(con, _archivo(entorno, "20260914_1035_minuta.txt"))
    assert desenlace.estado == "bandeja"
    assert con.execute("SELECT COUNT(*) FROM bandeja WHERE resuelto IS NULL").fetchone()[0] == 1


def test_dos_reuniones_a_la_misma_hora_van_a_la_bandeja(con, entorno):
    uno = _persona(con, "Ana Ruiz", "ana@uaemex.mx")
    dos = _persona(con, "Luis Mora", "luis@uaemex.mx")
    expediente.crear_reunion(con, uno, "A", inicio=datetime(2026, 9, 14, 10, 30))
    expediente.crear_reunion(con, dos, "B", inicio=datetime(2026, 9, 14, 10, 33))
    desenlace = ingesta.asociar(con, _archivo(entorno, "20260914_1035_minuta.txt"))
    assert desenlace.estado == "bandeja"
    assert "mas de una reunion" in desenlace.motivo


def test_asignacion_manual_desde_la_bandeja(con, entorno):
    pid = _persona(con, "Ana Ruiz", "ana@uaemex.mx")
    reunion_id = expediente.crear_reunion(con, pid, "Tutoria",
                                          inicio=datetime(2026, 9, 1, 11, 0))
    desenlace = ingesta.asociar(con, _archivo(entorno, "20260914_1035_minuta.txt"))
    assert desenlace.estado == "bandeja"
    manual = ingesta.asignar_manual(con, desenlace.bandeja_id, reunion_id)
    assert manual.estado == "asociado"
    assert len(expediente.archivos_de(con, reunion_id, "minuta")) == 1
    assert con.execute("SELECT COUNT(*) FROM bandeja").fetchone()[0] == 0


def test_no_duplica_el_mismo_archivo(con, entorno):
    pid = _persona(con, "Ana Ruiz", "ana@uaemex.mx")
    reunion_id = expediente.crear_reunion(con, pid, "Caso", inicio=datetime(2026, 9, 14, 10, 30))
    ingesta.asociar(con, _archivo(entorno, "20260914_1035_minuta.txt"))
    segundo = ingesta.asociar(con, _archivo(entorno, "20260914_1035_minuta.txt"))
    assert segundo.estado == "duplicado"
    assert len(expediente.archivos_de(con, reunion_id, "minuta")) == 1


def test_revisar_carpeta_procesa_lo_que_ya_estaba(con, entorno):
    pid = _persona(con, "Ana Ruiz", "ana@uaemex.mx")
    expediente.crear_reunion(con, pid, "Caso", inicio=datetime(2026, 9, 14, 10, 30))
    _archivo(entorno, "20260914_1035_minuta.txt")
    _archivo(entorno, "lista de pendientes.txt")
    resultados = dict(ingesta.revisar_carpeta(con))
    assert resultados["20260914_1035_minuta.txt"].estado == "asociado"
    assert resultados["lista de pendientes.txt"].estado == "ignorado"


def test_ventana_hacia_atras_respeta_la_configuracion(con, entorno):
    pid = _persona(con, "Ana Ruiz", "ana@uaemex.mx")
    momento = datetime(2026, 9, 14, 10, 35)
    lejos = momento - timedelta(hours=entorno.transcripciones.ventana_horas_atras + 1)
    expediente.crear_reunion(con, pid, "Vieja", inicio=lejos)
    assert ingesta.candidatas(con, momento) == []


def test_lee_archivos_en_codificacion_de_windows(con, entorno):
    pid = _persona(con, "Ana Ruiz", "ana@uaemex.mx")
    reunion_id = expediente.crear_reunion(con, pid, "Caso", inicio=datetime(2026, 9, 14, 10, 30))
    ruta = entorno.entrada / "20260914_1035_minuta.txt"
    ruta.write_bytes("Revisión de la calificación del señor Muñoz.".encode("cp1252"))
    ingesta.asociar(con, ruta)
    texto = expediente.texto_de(expediente.archivos_de(con, reunion_id, "minuta")[0])
    assert "calificación" in texto and "Muñoz" in texto


def test_esperar_copia_tolera_que_el_archivo_desaparezca(tmp_path):
    fantasma = tmp_path / "20260914_1035_minuta.txt"
    assert ingesta.esperar_copia(fantasma, intentos=2, pausa=0.01) is False


def test_esperar_copia_acepta_archivo_ya_escrito(tmp_path):
    ruta = tmp_path / "20260914_1035_minuta.txt"
    ruta.write_text("contenido", encoding="utf-8")
    assert ingesta.esperar_copia(ruta, intentos=3, pausa=0.01) is True
