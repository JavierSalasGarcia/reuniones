"""El respaldo de la pantalla y el encendido del monitor de la entrada."""

import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from reuniones import nube
from reuniones.web import kiosco as vista_kiosco

RAIZ = Path(__file__).resolve().parent.parent
ENERGIA = RAIZ / "kiosco" / "energia.sh"


@pytest.fixture
def pantalla(entorno, monkeypatch):
    monkeypatch.setenv("REUNIONES_NUBE_TOKEN", "token-de-prueba")
    entorno.nube.url = "https://fingenieria.mx/citas"
    entorno.nube.dependencia = "sa"
    nube._cache.datos, nube._cache.momento = {}, 0.0
    with TestClient(vista_kiosco.app) as cliente:
        yield cliente
    nube._cache.datos, nube._cache.momento = {}, 0.0


def test_la_pantalla_local_muestra_la_fila(pantalla, monkeypatch):
    from tests.test_nube import ESTADO, enchufar

    enchufar(monkeypatch, lambda p: httpx.Response(200, json=ESTADO))
    pagina = pantalla.get("/").text
    assert "Ana Ruiz" in pagina, "el turno en curso aparece grande"
    assert "Luis Mora" in pagina


def test_sin_conexion_conserva_lo_ultimo_y_lo_advierte(pantalla, monkeypatch):
    from tests.test_nube import ESTADO, enchufar

    enchufar(monkeypatch, lambda p: httpx.Response(200, json=ESTADO))
    pantalla.get("/estado.json")

    def truena(peticion):
        raise httpx.ConnectError("sin red")

    nube._cache.momento = 0.0
    enchufar(monkeypatch, truena)
    datos = pantalla.get("/estado.json").json()
    assert datos["desfasado"] is True
    assert datos["actual"]["folio"] == 1, "sigue mostrando lo último que se supo"
    assert "conexión" in datos["mensaje"]


def test_la_pantalla_local_no_expone_expedientes(pantalla):
    assert pantalla.get("/personas").status_code == 404
    assert pantalla.get("/persona/1").status_code == 404
    assert pantalla.get("/buscar").status_code == 404


def _decidir(tmp_path, horarios) -> str:
    """Corre el guion de encendido con un horario simulado."""
    estado = tmp_path / "estado.json"
    estado.write_text(json.dumps({"horarios": horarios}), encoding="utf-8")
    conf = tmp_path / "kiosco.conf"
    conf.write_text(f'URL_PRUEBA="file://{estado}"\nMARGEN=20\n', encoding="utf-8")
    salida = subprocess.run(["bash", str(ENERGIA), "--consultar"],
                            env={"REUNIONES_CONF": str(conf), "PATH": "/usr/bin:/bin"},
                            capture_output=True, text=True, timeout=30)
    return salida.stdout.strip()


def test_el_monitor_se_enciende_dentro_del_horario(tmp_path):
    ahora = datetime.now()
    hoy = ahora.isoweekday()
    horario = [{"dia": hoy,
                "inicio": (ahora - timedelta(hours=1)).strftime("%H:%M"),
                "fin": (ahora + timedelta(hours=1)).strftime("%H:%M")}]
    assert _decidir(tmp_path, horario) == "1"


def test_el_monitor_se_apaga_fuera_del_horario(tmp_path):
    ahora = datetime.now()
    hoy = ahora.isoweekday()
    inicio = ahora - timedelta(hours=5)
    horario = [{"dia": hoy, "inicio": inicio.strftime("%H:%M"),
                "fin": (inicio + timedelta(hours=1)).strftime("%H:%M")}]
    assert _decidir(tmp_path, horario) == "0"


def test_el_monitor_se_apaga_los_dias_sin_horario(tmp_path):
    otro_dia = (datetime.now().isoweekday() % 7) + 1
    assert _decidir(tmp_path, [{"dia": otro_dia, "inicio": "00:00", "fin": "23:59"}]) == "0"


def _con_horas_fijas(tmp_path, encendido: str, apagado: str) -> str:
    """Corre el guion sin horario publicado, con las horas de respaldo."""
    conf = tmp_path / "kiosco.conf"
    conf.write_text(
        'URL_PRUEBA="file:///no-existe.json"\n'
        f'HORA_ENCENDIDO="{encendido}"\nHORA_APAGADO="{apagado}"\nMARGEN=0\n',
        encoding="utf-8")
    salida = subprocess.run(["bash", str(ENERGIA), "--consultar"],
                            env={"REUNIONES_CONF": str(conf), "PATH": "/usr/bin:/bin"},
                            capture_output=True, text=True, timeout=30)
    return salida.stdout.strip()


def test_sin_horario_publicado_usa_las_horas_fijas(tmp_path):
    # Ventana que cubre el dia entero: sea la hora que sea, toca encendida.
    assert _con_horas_fijas(tmp_path, "00:01", "23:58") == "1"


def test_las_horas_fijas_tambien_apagan(tmp_path):
    ahora = datetime.now()
    # Una ventana de una hora que con seguridad no contiene a la actual.
    fuera = (ahora + timedelta(hours=6)).replace(minute=0)
    if fuera.date() != ahora.date():
        fuera = ahora.replace(hour=0, minute=0) + timedelta(hours=2)
    assert _con_horas_fijas(tmp_path, f"{fuera:%H:%M}",
                            f"{fuera + timedelta(minutes=59):%H:%M}") == "0"


def test_un_horario_que_cruza_la_medianoche_se_entiende(tmp_path):
    ahora = datetime.now()
    inicio = (ahora - timedelta(hours=2)).strftime("%H:%M")
    fin = (ahora + timedelta(hours=2)).strftime("%H:%M")
    # A las 23:00, esa ventana termina al día siguiente: debe seguir encendida.
    assert _con_horas_fijas(tmp_path, inicio, fin) == "1"


def test_la_pantalla_local_respeta_los_nombres_apagados(pantalla, monkeypatch):
    import httpx

    from tests.test_nube import ESTADO, enchufar

    discreta = dict(ESTADO)
    discreta["dependencia"] = dict(ESTADO["dependencia"], mostrar_nombres=False)
    enchufar(monkeypatch, lambda p: httpx.Response(200, json=discreta))

    datos = pantalla.get("/estado.json").json()
    assert datos["nombres"] is False
    assert datos["actual"]["nombre"] == "Pasa por favor"
    assert datos["siguientes"][0]["nombre"] == ""

    pagina = pantalla.get("/").text
    assert "Ana Ruiz" not in pagina and "Luis Mora" not in pagina
    assert "Pasa por favor" in pagina


def test_con_nombres_encendidos_la_pantalla_local_los_muestra(pantalla, monkeypatch):
    import httpx

    from tests.test_nube import ESTADO, enchufar

    enchufar(monkeypatch, lambda p: httpx.Response(200, json=ESTADO))
    datos = pantalla.get("/estado.json").json()
    assert datos["nombres"] is True
    assert datos["actual"]["nombre"] == "Ana Ruiz"
