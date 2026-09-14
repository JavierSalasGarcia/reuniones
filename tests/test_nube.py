import httpx
import pytest

from reuniones import config, expediente, nube, turnos


@pytest.fixture
def nube_lista(entorno, monkeypatch):
    """Configura la nube y la enchufa a un servidor simulado."""
    monkeypatch.setenv("REUNIONES_NUBE_TOKEN", "token-de-prueba")
    entorno.nube.url = "https://fingenieria.mx/citas"
    entorno.nube.dependencia = "sa"
    nube._cache.datos = {}
    nube._cache.momento = 0.0
    yield entorno
    nube._cache.datos = {}
    nube._cache.momento = 0.0


def enchufar(monkeypatch, manejador):
    """Sustituye el cliente HTTP por uno que responde con `manejador`."""
    llamadas = []

    def manejador_registrado(peticion: httpx.Request) -> httpx.Response:
        llamadas.append(peticion)
        return manejador(peticion)

    def cliente_falso():
        return httpx.Client(base_url="https://fingenieria.mx/citas",
                            headers={"Authorization": f"Bearer {config.actual().token_nube}"},
                            transport=httpx.MockTransport(manejador_registrado))

    monkeypatch.setattr(nube, "_cliente", cliente_falso)
    return llamadas


ESTADO = {
    "dependencia": {"clave": "sa", "nombre": "Subdirección", "disponible": True, "duracion_max": 10},
    "ahora": "2026-09-14 10:00:00",
    "abierta": True,
    "atencion": "atendiendo",
    "jornada": {"apertura": "08:30", "cierre": "15:00", "tope": "14:00", "estado": "abierta"},
    "disponible_hasta": "2026-09-14 12:00:00",
    "no_disponible_hasta": None,
    "motivo_cierre": "",
    "citas_aprobadas": [{"id": 9, "nombre": "Rosa Lima", "email": "rosa@uaemex.mx",
                         "asunto": "Servicio social", "confirmada": "2026-09-16 12:00:00",
                         "propuesta": "2026-09-16 12:00:00", "minutos": 30}],
    "proximo_hueco": "2026-09-14 10:24:00",
    "turnos": [
        {"id": 1, "folio": 1, "nombre": "Ana Ruiz", "email": "ana@uaemex.mx", "asunto": "Revalidación",
         "minutos": 10, "estado": "llamado", "estimado": "2026-09-14 10:00:00",
         "transcurridos": 14, "restan": -4},
        {"id": 2, "folio": 2, "nombre": "Luis Mora", "email": "luis@uaemex.mx", "asunto": "Beca",
         "minutos": 5, "estado": "espera", "estimado": "2026-09-14 10:12:00"},
        {"id": 3, "folio": 3, "nombre": "Sara Díaz", "email": "sara@uaemex.mx", "asunto": "Firma",
         "minutos": 5, "estado": "atendido", "estimado": None},
    ],
    "citas": [{"id": 7, "nombre": "Pedro Lara", "email": "pedro@uaemex.mx", "asunto": "Proyecto",
               "propuesta": "2026-09-16 11:00:00", "minutos": 30, "adjuntos": []}],
    "bloqueos": [],
    "horarios": [{"dia": 1, "inicio": "09:00", "fin": "14:00"}],
}


def test_sin_token_avisa_que_falta_configurar(entorno, monkeypatch):
    monkeypatch.delenv("REUNIONES_NUBE_TOKEN", raising=False)
    listo, motivo = nube.configurada()
    assert not listo and ".env" in motivo


def test_estado_pide_su_dependencia_con_el_token(nube_lista, monkeypatch):
    llamadas = enchufar(monkeypatch, lambda p: httpx.Response(200, json=ESTADO))
    datos = nube.estado()

    assert datos["abierta"] is True
    peticion = llamadas[0]
    assert peticion.url.path.endswith("/api")
    assert dict(peticion.url.params) == {"d": "sa", "accion": "estado"}
    assert peticion.headers["Authorization"] == "Bearer token-de-prueba"


def test_el_estado_se_guarda_un_momento(nube_lista, monkeypatch):
    llamadas = enchufar(monkeypatch, lambda p: httpx.Response(200, json=ESTADO))
    nube.estado()
    nube.estado()
    assert len(llamadas) == 1, "no vuelve a salir a internet por cada clic"
    nube.estado(forzar=True)
    assert len(llamadas) == 2


def test_token_rechazado_se_explica(nube_lista, monkeypatch):
    enchufar(monkeypatch, lambda p: httpx.Response(401, json={"error": "no autorizado"}))
    with pytest.raises(nube.ErrorNube, match="token"):
        nube.estado()


def test_sin_internet_se_conserva_lo_ultimo_conocido(nube_lista, monkeypatch):
    enchufar(monkeypatch, lambda p: httpx.Response(200, json=ESTADO))
    nube.estado()

    def truena(peticion):
        raise httpx.ConnectError("sin red")

    nube._cache.momento = 0.0          # obliga a salir de nuevo a la red
    enchufar(monkeypatch, truena)
    datos, error = nube.estado_seguro()
    assert error and datos["turnos"], "la interfaz sigue mostrando la fila anterior"


def test_llamar_turno_manda_la_accion_correcta(nube_lista, monkeypatch):
    llamadas = enchufar(monkeypatch, lambda p: httpx.Response(200, json={"ok": True}))
    nube.turno(2, "llamar", "Luis Mora")

    import json
    cuerpo = json.loads(llamadas[0].content)
    assert dict(llamadas[0].url.params)["accion"] == "turno"
    assert cuerpo == {"id": 2, "accion": "llamar", "nombre_publico": "Luis Mora"}


def test_disponibilidad_y_bloqueos(nube_lista, monkeypatch):
    import json
    from datetime import datetime

    llamadas = enchufar(monkeypatch, lambda p: httpx.Response(200, json={"ok": True}))
    nube.disponibilidad(False, "En junta de consejo")
    nube.crear_bloqueo(datetime(2026, 9, 14, 11, 0), datetime(2026, 9, 14, 12, 0), "Consejo")

    assert json.loads(llamadas[0].content) == {"disponible": False, "mensaje": "En junta de consejo"}
    assert json.loads(llamadas[1].content) == {"inicio": "2026-09-14 11:00:00",
                                               "fin": "2026-09-14 12:00:00", "motivo": "Consejo"}


def test_direcciones_publicas(nube_lista):
    assert nube.url_publica() == "https://fingenieria.mx/citas/sa"
    assert nube.url_publica("pantalla") == "https://fingenieria.mx/citas/sa/pantalla"


def test_resumen_separa_la_fila(nube_lista):
    resumen = turnos.resumen_fila(ESTADO)
    assert resumen["actual"]["folio"] == 1
    assert [t["folio"] for t in resumen["espera"]] == [2]
    assert resumen["atendidos"] == 1
    assert len(resumen["citas"]) == 1


def test_el_nombre_en_pantalla_protege_los_casos_reservados(con, nube_lista):
    con.execute("INSERT INTO personas (nombre, email, reservado, creado, actualizado) "
                "VALUES ('Ana Ruiz López', 'ana@uaemex.mx', 1, '', '')")
    turno = {"id": 1, "folio": 4, "nombre": "Ana Ruiz López", "email": "ana@uaemex.mx"}
    assert turnos.nombre_para_pantalla(con, turno) == "Turno 4"

    otro = {"id": 2, "folio": 5, "nombre": "Luis Mora Sánchez", "email": "luis@uaemex.mx"}
    assert turnos.nombre_para_pantalla(con, otro) == "Luis Mora"


def test_llamar_abre_expediente_y_crea_la_reunion(con, nube_lista, monkeypatch):
    enchufar(monkeypatch, lambda p: httpx.Response(200, json={"ok": True}))
    cursor = con.execute("INSERT INTO personas (nombre, email, creado, actualizado) "
                         "VALUES ('Luis Mora', 'luis@uaemex.mx', '', '')")
    persona_id = int(cursor.lastrowid)

    enlace = turnos.llamar(con, ESTADO["turnos"][1])
    assert enlace["persona_id"] == persona_id
    reunion = expediente.reunion(con, enlace["reunion_id"])
    assert reunion["asunto"] == "Beca" and reunion["origen"] == "turno"


def test_llamar_a_alguien_nuevo_no_inventa_expediente(con, nube_lista, monkeypatch):
    enchufar(monkeypatch, lambda p: httpx.Response(200, json={"ok": True}))
    enlace = turnos.llamar(con, ESTADO["turnos"][1])
    assert enlace["persona_id"] is None and enlace["reunion_id"] is None
    assert enlace["email"] == "luis@uaemex.mx"


# --- jornada: llegar, pausar, cerrar y cancelar la cola -------------------

def test_la_leyenda_dice_hasta_que_hora_estas_disponible():
    assert turnos.leyenda(ESTADO) == "Disponible hasta 12:00"
    ocupado = dict(ESTADO, atencion="ocupado", no_disponible_hasta="2026-09-14 14:00:00")
    assert turnos.leyenda(ocupado) == "No disponible hasta 14:00"
    pausada = dict(ESTADO, atencion="pausada")
    assert turnos.leyenda(pausada) == "Disponible a partir de las 08:30"
    cerrada = dict(ESTADO, atencion="cerrada", motivo_cierre="Salí a una emergencia")
    assert turnos.leyenda(cerrada) == "Salí a una emergencia"


def test_abrir_manda_la_hora_de_cierre_y_el_tope(nube_lista, monkeypatch):
    import json

    llamadas = enchufar(monkeypatch, lambda p: httpx.Response(200, json={"ok": True, "jornada": {}}))
    nube.abrir("15:00", "14:00")
    cuerpo = json.loads(llamadas[0].content)
    assert dict(llamadas[0].url.params)["accion"] == "abrir"
    assert cuerpo["cierre"] == "15:00" and cuerpo["tope"] == "14:00"


def test_pausar_convierte_los_minutos_en_hora_de_regreso(nube_lista, monkeypatch):
    import json

    llamadas = enchufar(monkeypatch, lambda p: httpx.Response(200, json={"ok": True}))
    nube.pausar(minutos=45, motivo="Videoconferencia")
    cuerpo = json.loads(llamadas[0].content)
    assert cuerpo == {"motivo": "Videoconferencia", "minutos": 45}


def test_cancelar_la_cola_avisa_cuantos_fueron(nube_lista, monkeypatch):
    enchufar(monkeypatch, lambda p: httpx.Response(200, json={
        "ok": True, "cancelados": 3, "avisados": ["a@uaemex.mx", "b@uaemex.mx", "c@uaemex.mx"]}))
    resultado = nube.cancelar_cola("Salida de emergencia")
    assert resultado["cancelados"] == 3
    assert len(resultado["avisados"]) == 3


def test_configurar_la_jornada_de_otro_dia(nube_lista, monkeypatch):
    import json

    llamadas = enchufar(monkeypatch, lambda p: httpx.Response(200, json={"ok": True, "jornada": {}}))
    nube.configurar_jornada("2026-09-15", "10:00", "14:00", "13:00")
    cuerpo = json.loads(llamadas[0].content)
    assert cuerpo == {"fecha": "2026-09-15", "apertura": "10:00", "cierre": "14:00", "tope": "13:00"}


def test_cancelar_una_cita_confirmada(nube_lista, monkeypatch):
    import json

    llamadas = enchufar(monkeypatch, lambda p: httpx.Response(200, json={"ok": True, "cita": {}}))
    turnos.cancelar_cita({"id": 9}, "Me mandaron a una comisión")
    cuerpo = json.loads(llamadas[0].content)
    assert cuerpo["accion"] == "cancelar" and cuerpo["motivo"] == "Me mandaron a una comisión"


def test_el_resumen_separa_citas_confirmadas_de_solicitudes(nube_lista):
    resumen = turnos.resumen_fila(ESTADO)
    assert len(resumen["citas"]) == 1 and resumen["citas"][0]["nombre"] == "Pedro Lara"
    assert len(resumen["confirmadas"]) == 1 and resumen["confirmadas"][0]["nombre"] == "Rosa Lima"
    assert resumen["leyenda"] == "Disponible hasta 12:00"
