from datetime import datetime

import pytest

from reuniones import correo, expediente


class SMTPFalso:
    """Servidor de correo simulado que guarda lo que se le entrega."""

    enviados: list = []

    def __init__(self, servidor, puerto, timeout=0):
        self.servidor = servidor

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def starttls(self):
        self.tls = True

    def login(self, usuario, clave):
        self.usuario = usuario

    def send_message(self, mensaje):
        SMTPFalso.enviados.append(mensaje)

    def noop(self):
        return (250, b"ok")


@pytest.fixture
def correo_listo(entorno, monkeypatch):
    SMTPFalso.enviados = []
    monkeypatch.setenv("REUNIONES_SMTP_PASSWORD", "secreta")
    entorno.correo.servidor = "smtp.uaemex.mx"
    entorno.correo.usuario = "subdireccion@uaemex.mx"
    entorno.correo.remitente = "subdireccion@uaemex.mx"
    monkeypatch.setattr("smtplib.SMTP", SMTPFalso)
    return entorno


def _reunion(con, entorno, minuta="Acuerdo: revisar el caso.", original="Hablante 1: hola."):
    pid = int(con.execute(
        "INSERT INTO personas (nombre, email, creado, actualizado) VALUES "
        "('Ana Ruiz', 'ana@uaemex.mx', '', '')").lastrowid)
    reunion_id = expediente.crear_reunion(con, pid, "Revalidacion",
                                          inicio=datetime(2026, 9, 14, 10, 30))
    for clase, texto in (("minuta", minuta), ("original", original)):
        ruta = entorno.entrada / f"20260914_1030_{clase}.txt"
        ruta.write_text(texto, encoding="utf-8")
        expediente.adjuntar(con, reunion_id, ruta, clase, "20260914_1030")
    return reunion_id


def test_envia_la_minuta_y_deja_constancia(con, correo_listo):
    reunion_id = _reunion(con, correo_listo)
    resultado = correo.enviar_minuta(con, reunion_id)

    assert resultado["destinatario"] == "ana@uaemex.mx"
    mensaje = SMTPFalso.enviados[0]
    adjuntos = [p for p in mensaje.iter_attachments()]
    assert len(adjuntos) == 1
    assert adjuntos[0].get_content_type() == "application/pdf"

    registro = correo.envios_de(con, reunion_id)
    assert len(registro) == 1 and registro[0]["estado"] == "enviado"


def test_la_transcripcion_original_nunca_viaja(con, correo_listo):
    reunion_id = _reunion(con, correo_listo, original="Hablante 2: esto es confidencial.")
    correo.enviar_minuta(con, reunion_id)
    crudo = SMTPFalso.enviados[0].as_string()
    assert "confidencial" not in crudo
    assert "_original" not in crudo


def test_sin_configuracion_avisa_en_lugar_de_fallar(con, entorno, monkeypatch):
    entorno.correo.remitente = "subdireccion@uaemex.mx"
    monkeypatch.delenv("REUNIONES_SMTP_PASSWORD", raising=False)
    reunion_id = _reunion(con, entorno)
    with pytest.raises(correo.ErrorCorreo, match="SMTP_PASSWORD"):
        correo.enviar_minuta(con, reunion_id)


def test_falla_de_entrega_queda_registrada(con, correo_listo, monkeypatch):
    reunion_id = _reunion(con, correo_listo)

    def truena(self, mensaje):
        raise OSError("servidor fuera de linea")

    monkeypatch.setattr(SMTPFalso, "send_message", truena)
    with pytest.raises(correo.ErrorCorreo):
        correo.enviar_minuta(con, reunion_id)
    registro = correo.envios_de(con, reunion_id)
    assert registro[0]["estado"] == "error" and "fuera de linea" in registro[0]["detalle"]


def test_sin_minuta_no_hay_nada_que_enviar(con, correo_listo):
    pid = int(con.execute(
        "INSERT INTO personas (nombre, email, creado, actualizado) VALUES "
        "('Luis Mora', 'luis@uaemex.mx', '', '')").lastrowid)
    reunion_id = expediente.crear_reunion(con, pid, "Sin papeles")
    with pytest.raises(ValueError, match="minuta"):
        correo.enviar_minuta(con, reunion_id)
