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
    """Envío directo por SMTP desde la laptop (via = laptop)."""
    SMTPFalso.enviados = []
    entorno.correo.via = "laptop"
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
    entorno.correo.via = "laptop"
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


def test_las_respuestas_llegan_al_correo_institucional(con, correo_listo):
    correo_listo.correo.responder_a = "javier.salas@uaemex.mx"
    reunion_id = _reunion(con, correo_listo)
    correo.enviar_minuta(con, reunion_id)
    assert SMTPFalso.enviados[0]["Reply-To"] == "javier.salas@uaemex.mx"


# --- envío a través del servidor de fingenieria.mx ------------------------

@pytest.fixture
def envio_por_servidor(entorno, monkeypatch):
    """Registra lo que se le pide al servidor en lugar de salir a la red."""
    from reuniones import nube

    entorno.correo.via = "servidor"
    entorno.nube.url = "https://fingenieria.mx/citas"
    entorno.nube.dependencia = "sa"
    monkeypatch.setenv("REUNIONES_NUBE_TOKEN", "token-de-prueba")

    movimientos = {"subidas": [], "envios": []}

    def subir(pdf, persona, email, asunto="", fecha=None, reunion_local=None):
        movimientos["subidas"].append({
            "archivo": pdf, "contenido": pdf.read_bytes(), "persona": persona,
            "email": email, "asunto": asunto, "fecha": fecha, "reunion": reunion_local,
        })
        return {"id": 77, "nombre": pdf.name, "estado": "guardada"}

    def enviar(minuta_id, destinatario, mensaje=""):
        movimientos["envios"].append({"id": minuta_id, "para": destinatario, "mensaje": mensaje})
        return {"ok": True}

    monkeypatch.setattr(nube, "subir_minuta", subir)
    monkeypatch.setattr(nube, "enviar_minuta", enviar)
    return movimientos


def test_la_minuta_sube_al_servidor_y_de_ahi_se_manda(con, envio_por_servidor, entorno):
    reunion_id = _reunion(con, entorno)
    resultado = correo.enviar_minuta(con, reunion_id)

    assert resultado["estado"] == "enviado"
    subida = envio_por_servidor["subidas"][0]
    assert subida["email"] == "ana@uaemex.mx"
    assert subida["reunion"] == reunion_id
    assert subida["contenido"].startswith(b"%PDF"), "sube el PDF, no el texto"
    assert envio_por_servidor["envios"] == [{"id": 77, "para": "ana@uaemex.mx", "mensaje": ""}]

    registro = correo.envios_de(con, reunion_id)
    assert len(registro) == 1 and registro[0]["estado"] == "enviado"
    assert "servidor" in registro[0]["detalle"]


def test_al_servidor_solo_sube_la_minuta(con, envio_por_servidor, entorno):
    reunion_id = _reunion(con, entorno, original="Hablante 2: esto es confidencial.")
    correo.enviar_minuta(con, reunion_id)
    subidas = envio_por_servidor["subidas"]
    assert len(subidas) == 1
    assert b"confidencial" not in subidas[0]["contenido"]


def test_sin_conexion_el_envio_queda_pendiente(con, envio_por_servidor, entorno, monkeypatch):
    from reuniones import nube

    def sin_red(*args, **kwargs):
        raise nube.ErrorNube("No se pudo hablar con el servidor: sin red")

    monkeypatch.setattr(nube, "subir_minuta", sin_red)
    reunion_id = _reunion(con, entorno)
    resultado = correo.enviar_minuta(con, reunion_id)

    assert resultado["estado"] == "pendiente"
    registro = correo.envios_de(con, reunion_id)
    assert registro[0]["estado"] == "pendiente"
    assert len(correo.pendientes(con)) == 1


def test_lo_pendiente_se_reintenta_y_no_duplica_el_registro(con, envio_por_servidor, entorno,
                                                            monkeypatch):
    from reuniones import nube

    def sin_red(*args, **kwargs):
        raise nube.ErrorNube("sin red")

    monkeypatch.setattr(nube, "subir_minuta", sin_red)
    reunion_id = _reunion(con, entorno)
    correo.enviar_minuta(con, reunion_id)
    pendiente = correo.pendientes(con)[0]

    def subir(pdf, persona, email, asunto="", fecha=None, reunion_local=None):
        return {"id": 78, "nombre": pdf.name}

    monkeypatch.setattr(nube, "subir_minuta", subir)
    assert correo.reintentar_pendientes(con) == 1

    registro = correo.envios_de(con, reunion_id)
    assert len(registro) == 1, "se actualiza el mismo renglón, no se agrega otro"
    assert registro[0]["id"] == pendiente["id"]
    assert registro[0]["estado"] == "enviado"
    assert correo.pendientes(con) == []


def test_si_el_servidor_rechaza_el_correo_no_queda_pendiente(con, envio_por_servidor, entorno,
                                                             monkeypatch):
    from reuniones import nube

    def rechaza(minuta_id, destinatario, mensaje=""):
        raise nube.ErrorEnvio("el buzón de destino no existe")

    monkeypatch.setattr(nube, "enviar_minuta", rechaza)
    reunion_id = _reunion(con, entorno)
    with pytest.raises(correo.ErrorCorreo, match="no pudo entregar"):
        correo.enviar_minuta(con, reunion_id)

    registro = correo.envios_de(con, reunion_id)
    assert registro[0]["estado"] == "error"
    assert correo.pendientes(con) == [], "un rechazo no se reintenta solo"


def test_sin_token_del_servidor_avisa_que_falta_configurar(con, entorno, monkeypatch):
    monkeypatch.delenv("REUNIONES_NUBE_TOKEN", raising=False)
    entorno.correo.via = "servidor"
    reunion_id = _reunion(con, entorno)
    with pytest.raises(correo.ErrorCorreo, match=".env"):
        correo.enviar_minuta(con, reunion_id)
