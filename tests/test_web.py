from datetime import datetime

import numpy as np
import pytest
from fastapi.testclient import TestClient

from reuniones import expediente, personas, rostros
from reuniones.web import app as web
from tests.conftest import cuadro_sintetico, detector_falso


@pytest.fixture
def cliente(entorno):
    with TestClient(web.app) as prueba:
        yield prueba


def _persona_con_reunion(cliente, entorno):
    from reuniones import db

    with db.sesion() as con:
        vector = np.random.default_rng(3).normal(size=512).astype(np.float32)
        alta = personas.alta(con, "Ana Ruiz", "ana@uaemex.mx",
                             [cuadro_sintetico() for _ in range(10)],
                             detector=detector_falso({0: vector}))
        reunion_id = expediente.crear_reunion(con, alta["persona_id"], "Revalidacion",
                                              inicio=datetime(2026, 9, 14, 10, 30))
        ruta = entorno.entrada / "20260914_1030_minuta.txt"
        ruta.write_text("Acuerdo: entregar el dictamen.", encoding="utf-8")
        expediente.adjuntar(con, reunion_id, ruta, "minuta", "20260914_1030")
    return alta["persona_id"], reunion_id


def test_inicio_responde(cliente):
    respuesta = cliente.get("/")
    assert respuesta.status_code == 200
    assert "¿Quién entró?" in respuesta.text


def test_expediente_muestra_briefing_e_historial(cliente, entorno):
    persona_id, _ = _persona_con_reunion(cliente, entorno)
    respuesta = cliente.get(f"/persona/{persona_id}")
    assert respuesta.status_code == 200
    assert "Ana Ruiz" in respuesta.text
    assert "Revalidacion" in respuesta.text


def test_la_reunion_muestra_la_minuta(cliente, entorno):
    _, reunion_id = _persona_con_reunion(cliente, entorno)
    respuesta = cliente.get(f"/reunion/{reunion_id}")
    assert respuesta.status_code == 200
    assert "entregar el dictamen" in respuesta.text


def test_identificar_devuelve_candidato(cliente, entorno, monkeypatch):
    persona_id, _ = _persona_con_reunion(cliente, entorno)

    def lectura_falsa(con):
        vector = np.random.default_rng(3).normal(size=512).astype(np.float32)
        return personas.Identificacion(rostros.identificar(con, vector), 0.8, vector, 5)

    monkeypatch.setattr(personas, "identificar_con_camara", lectura_falsa)
    datos = cliente.post("/identificar").json()
    assert datos["estado"] == "identificado"
    assert datos["ir_a"] == f"/persona/{persona_id}"


def test_identificar_sin_camara_explica_el_problema(cliente, monkeypatch):
    def truena(con):
        raise RuntimeError("Falta OpenCV.")

    monkeypatch.setattr(personas, "identificar_con_camara", truena)
    respuesta = cliente.post("/identificar")
    assert respuesta.status_code == 503
    assert "OpenCV" in respuesta.json()["mensaje"]


def test_nueva_reunion_desde_el_expediente(cliente, entorno):
    persona_id, _ = _persona_con_reunion(cliente, entorno)
    respuesta = cliente.post(f"/persona/{persona_id}/reunion",
                             data={"asunto": "Segundo caso", "categoria": "becas"},
                             follow_redirects=True)
    assert respuesta.status_code == 200
    assert "Segundo caso" in respuesta.text


def test_acuerdo_se_agrega_y_se_cierra(cliente, entorno):
    _, reunion_id = _persona_con_reunion(cliente, entorno)
    cliente.post(f"/reunion/{reunion_id}/acuerdo",
                 data={"texto": "Entregar constancia", "responsable": "Ana", "compromiso": "2026-09-30"},
                 follow_redirects=True)
    pagina = cliente.get(f"/reunion/{reunion_id}").text
    assert "Entregar constancia" in pagina

    from reuniones import db
    with db.sesion() as con:
        acuerdo_id = con.execute("SELECT id FROM acuerdos").fetchone()[0]
    cliente.post(f"/acuerdo/{acuerdo_id}/estado",
                 data={"reunion_id": reunion_id, "cerrar": "1"}, follow_redirects=True)
    with db.sesion() as con:
        assert con.execute("SELECT estado FROM acuerdos").fetchone()[0] == "cerrado"


def test_busqueda_encuentra_la_minuta(cliente, entorno):
    _persona_con_reunion(cliente, entorno)
    cliente.post("/ajustes/reindexar")
    respuesta = cliente.get("/buscar", params={"q": "dictamen"})
    assert "Revalidacion" in respuesta.text


def test_pdf_de_la_minuta(cliente, entorno):
    _, reunion_id = _persona_con_reunion(cliente, entorno)
    respuesta = cliente.get(f"/reunion/{reunion_id}/minuta.pdf")
    assert respuesta.status_code == 200
    assert respuesta.content.startswith(b"%PDF")


def test_no_se_pueden_leer_archivos_fuera_de_la_carpeta_de_datos(cliente):
    assert cliente.get("/archivo/../../etc/passwd").status_code == 404
    assert cliente.get("/archivo/no-existe.jpg").status_code == 404


def test_la_foto_se_sirve_desde_la_carpeta_de_datos(cliente, entorno):
    persona_id, _ = _persona_con_reunion(cliente, entorno)
    from reuniones import db
    with db.sesion() as con:
        foto = con.execute("SELECT foto FROM personas WHERE id = ?", (persona_id,)).fetchone()[0]
    respuesta = cliente.get(f"/archivo/{foto}")
    assert respuesta.status_code == 200 and respuesta.content[:2] == b"\xff\xd8"


def test_bandeja_ofrece_las_reuniones_cercanas(cliente, entorno):
    _persona_con_reunion(cliente, entorno)
    suelto = entorno.entrada / "20260914_1040_original.txt"
    suelto.write_text("Hablante 1: buenos dias.", encoding="utf-8")
    cliente.post("/bandeja/revisar", follow_redirects=True)
    pagina = cliente.get("/bandeja").text
    assert "20260914_1040_original.txt" in pagina or "No hay nada pendiente" in pagina


def test_alta_desde_el_sitio_exige_consentimiento(cliente):
    respuesta = cliente.post("/alta", data={"nombre": "Luis Mora", "email": "luis@uaemex.mx"})
    assert "consentimiento" in respuesta.text.lower()


def test_ajustes_muestra_el_estado(cliente):
    respuesta = cliente.get("/ajustes")
    assert respuesta.status_code == 200
    assert "Carpeta de datos" in respuesta.text


def test_la_fila_explica_si_falta_configurar_la_nube(cliente, monkeypatch):
    monkeypatch.delenv("REUNIONES_NUBE_TOKEN", raising=False)
    respuesta = cliente.get("/turnos")
    assert respuesta.status_code == 200
    assert "token" in respuesta.text.lower()


def test_la_fila_muestra_a_quien_espera(cliente, entorno, monkeypatch):
    from reuniones import nube
    from tests.test_nube import ESTADO, enchufar

    monkeypatch.setenv("REUNIONES_NUBE_TOKEN", "token-de-prueba")
    entorno.nube.url = "https://fingenieria.mx/citas"
    entorno.nube.dependencia = "sa"
    nube._cache.datos, nube._cache.momento = {}, 0.0

    import httpx
    enchufar(monkeypatch, lambda p: httpx.Response(200, json=ESTADO))
    pagina = cliente.get("/turnos").text
    assert "Luis Mora" in pagina and "Beca" in pagina
    assert "Pedro Lara" in pagina, "las solicitudes de reunión también se ven"
    nube._cache.datos, nube._cache.momento = {}, 0.0


def test_la_agenda_muestra_el_horario_publicado(cliente, entorno, monkeypatch):
    from reuniones import nube
    from tests.test_nube import ESTADO, enchufar

    monkeypatch.setenv("REUNIONES_NUBE_TOKEN", "token-de-prueba")
    entorno.nube.url = "https://fingenieria.mx/citas"
    entorno.nube.dependencia = "sa"
    nube._cache.datos, nube._cache.momento = {}, 0.0

    import httpx
    enchufar(monkeypatch, lambda p: httpx.Response(200, json=ESTADO))
    pagina = cliente.get("/agenda").text
    assert "Horario semanal" in pagina and "09:00" in pagina
    nube._cache.datos, nube._cache.momento = {}, 0.0


def test_la_pagina_de_minutas_del_servidor_lista_lo_guardado(cliente, entorno, monkeypatch):
    from reuniones import nube

    persona_id, _ = _persona_con_reunion(cliente, entorno)
    monkeypatch.setattr(nube, "minutas", lambda email="": [
        {"id": 5, "fecha": "2026-09-14 10:30:00", "nombre": "20260914_1030_minuta_ana.pdf",
         "asunto": "Revalidación", "estado": "enviada", "enviado": "2026-09-14 11:00:00",
         "destinatario": "ana@uaemex.mx", "detalle": ""}])
    pagina = cliente.get(f"/persona/{persona_id}/servidor").text
    assert "20260914_1030_minuta_ana.pdf" in pagina
    assert "Reenviar" in pagina


def test_si_el_servidor_no_responde_la_pagina_lo_dice(cliente, entorno, monkeypatch):
    from reuniones import nube

    persona_id, _ = _persona_con_reunion(cliente, entorno)

    def truena(email=""):
        raise nube.ErrorNube("No se pudo consultar el expediente del servidor: sin red")

    monkeypatch.setattr(nube, "minutas", truena)
    pagina = cliente.get(f"/persona/{persona_id}/servidor").text
    assert "sin red" in pagina


def _conectar_nube(entorno, monkeypatch, estado=None):
    """Deja el panel hablando con una nube simulada."""
    import httpx

    from reuniones import nube
    from tests.test_nube import ESTADO, enchufar

    monkeypatch.setenv("REUNIONES_NUBE_TOKEN", "token-de-prueba")
    entorno.nube.url = "https://fingenieria.mx/citas"
    entorno.nube.dependencia = "sa"
    nube._cache.datos, nube._cache.momento = {}, 0.0
    enchufar(monkeypatch, lambda p: httpx.Response(200, json=estado or ESTADO))
    return nube


def test_la_fila_anuncia_hasta_que_hora_estas_disponible(cliente, entorno, monkeypatch):
    nube = _conectar_nube(entorno, monkeypatch)
    pagina = cliente.get("/turnos").text
    assert "Disponible hasta 12:00" in pagina
    assert "Terminar la jornada" in pagina, "estando abierto se puede cerrar o pausar"
    assert "Cancelar la cola" in pagina
    nube._cache.datos, nube._cache.momento = {}, 0.0


def test_si_no_has_llegado_el_panel_ofrece_abrir(cliente, entorno, monkeypatch):
    from tests.test_nube import ESTADO

    pausada = dict(ESTADO, atencion="pausada", disponible_hasta=None)
    nube = _conectar_nube(entorno, monkeypatch, pausada)
    pagina = cliente.get("/turnos").text
    assert "Disponible a partir de las 08:30" in pagina
    assert "Llegué, abrir atención" in pagina
    nube._cache.datos, nube._cache.momento = {}, 0.0


def test_las_citas_confirmadas_se_pueden_cancelar_desde_el_panel(cliente, entorno, monkeypatch):
    nube = _conectar_nube(entorno, monkeypatch)
    pagina = cliente.get("/turnos").text
    assert "Rosa Lima" in pagina and "Cancelar la cita" in pagina
    nube._cache.datos, nube._cache.momento = {}, 0.0


def test_la_agenda_permite_dejar_lista_la_jornada_de_otro_dia(cliente, entorno, monkeypatch):
    nube = _conectar_nube(entorno, monkeypatch)
    pagina = cliente.get("/agenda").text
    assert "Jornada de un día" in pagina and "Llego a las" in pagina
    nube._cache.datos, nube._cache.momento = {}, 0.0


def test_el_panel_avisa_cuando_la_reunion_se_paso_de_tiempo(cliente, entorno, monkeypatch):
    nube = _conectar_nube(entorno, monkeypatch)
    pagina = cliente.get("/turnos").text
    assert "Llevan 14 de 10 minutos" in pagina and "4 de más" in pagina
    nube._cache.datos, nube._cache.momento = {}, 0.0


def test_se_suben_minuta_y_transcripcion_de_una_vez(cliente, entorno):
    _, reunion_id = _persona_con_reunion(cliente, entorno)
    respuesta = cliente.post(
        f"/reunion/{reunion_id}/adjunto",
        files=[
            ("archivos", ("20260914_1030_minuta.txt", b"Acuerdo: revisar el caso.", "text/plain")),
            ("archivos", ("20260914_1030_original.txt", b"Hablante 1: buenos dias.", "text/plain")),
        ],
        data={"clase": "auto"},
        follow_redirects=True,
    )
    assert respuesta.status_code == 200
    assert "revisar el caso" in respuesta.text and "buenos dias" in respuesta.text

    from reuniones import db, expediente
    with db.sesion() as con:
        clases = sorted(a["clase"] for a in expediente.archivos_de(con, reunion_id))
    assert clases == ["minuta", "original"], "cada archivo quedó en su lugar por su nombre"


def test_un_archivo_sin_el_formato_del_telefono_se_guarda_como_adjunto(cliente, entorno):
    _, reunion_id = _persona_con_reunion(cliente, entorno)
    cliente.post(f"/reunion/{reunion_id}/adjunto",
                 files=[("archivos", ("notas sueltas.txt", b"apuntes", "text/plain"))],
                 data={"clase": "auto"}, follow_redirects=True)

    from reuniones import db, expediente
    with db.sesion() as con:
        clases = [a["clase"] for a in expediente.archivos_de(con, reunion_id)]
    assert "adjunto" in clases


def test_se_puede_decir_a_mano_que_es_cada_archivo(cliente, entorno):
    _, reunion_id = _persona_con_reunion(cliente, entorno)
    cliente.post(f"/reunion/{reunion_id}/adjunto",
                 files=[("archivos", ("minuta del martes.txt", b"lo acordado", "text/plain"))],
                 data={"clase": "minuta"}, follow_redirects=True)

    from reuniones import db, expediente
    with db.sesion() as con:
        minutas = expediente.archivos_de(con, reunion_id, "minuta")
    assert len(minutas) == 1


def test_el_panel_ofrece_llamar_al_siguiente_y_marcar_que_no_llego(cliente, entorno, monkeypatch):
    nube = _conectar_nube(entorno, monkeypatch)
    pagina = cliente.get("/turnos").text
    assert "Llamar al siguiente: 2 · Luis Mora" in pagina
    assert "No llegó" in pagina
    nube._cache.datos, nube._cache.momento = {}, 0.0


def test_llamar_al_siguiente_toma_al_primero_de_la_fila(cliente, entorno, monkeypatch):
    import httpx

    from reuniones import nube, turnos
    from tests.test_nube import ESTADO

    _conectar_nube(entorno, monkeypatch)
    nube.estado(forzar=True)

    llamados = []
    monkeypatch.setattr(turnos, "llamar", lambda con, turno: llamados.append(turno) or
                        {"persona_id": None, "reunion_id": None, "email": turno["email"],
                         "nombre": turno["nombre"]})
    cliente.post("/turnos/siguiente", follow_redirects=False)
    assert [t["folio"] for t in llamados] == [2], "el que sigue, no el que ya está adentro"
    nube._cache.datos, nube._cache.momento = {}, 0.0
