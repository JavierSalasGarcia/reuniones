"""Envio de la minuta.

El servidor de correo institucional rechaza los mensajes que salen de la
laptop, asi que por omision la minuta en PDF sube a fingenieria.mx y desde
alli se envia, quedando ademas guardada en el expediente del servidor. Si no
hay conexion, el envio queda pendiente y se reintenta solo.

Regla que no cambia: solo sale la minuta. La transcripcion original nunca se
adjunta ni se cita; se queda en este equipo.
"""

from __future__ import annotations

import smtplib
import sqlite3
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path

from . import config, db, expediente, informe, nube, util

CUERPO = """Estimada o estimado {nombre}:

Adjunto la minuta de nuestra reunion del {fecha}{asunto}, para que quede como
antecedente de lo tratado y de los acuerdos alcanzados.

Si encuentra alguna imprecision, le agradecere que me lo haga saber.

Saludos cordiales,
{titular}
"""


class ErrorCorreo(Exception):
    """Fallas de configuracion o de entrega que la interfaz debe mostrar."""


def por_servidor() -> bool:
    return config.actual().correo.via != "laptop"


def configurado() -> tuple[bool, str]:
    if por_servidor():
        return nube.configurada()
    cfg = config.actual().correo
    if not cfg.servidor:
        return False, "Falta el servidor SMTP en config.toml."
    if not (cfg.remitente or cfg.usuario):
        return False, "Falta el correo remitente en config.toml."
    if not config.actual().clave_smtp:
        return False, "Falta REUNIONES_SMTP_PASSWORD en el archivo .env."
    return True, ""


def _conexion():
    cfg = config.actual().correo
    clave = config.actual().clave_smtp
    if cfg.puerto == 465:
        servidor = smtplib.SMTP_SSL(cfg.servidor, cfg.puerto, timeout=30)
    else:
        servidor = smtplib.SMTP(cfg.servidor, cfg.puerto, timeout=30)
        if cfg.starttls:
            servidor.starttls()
    if cfg.usuario:
        servidor.login(cfg.usuario, clave)
    return servidor


def probar() -> str:
    listo, motivo = configurado()
    if not listo:
        raise ErrorCorreo(motivo)
    if por_servidor():
        try:
            nube.estado(forzar=True)
        except nube.ErrorNube as error:
            raise ErrorCorreo(str(error)) from error
        return "El servidor de fingenieria.mx responde; desde ahí saldrán las minutas."
    try:
        with _conexion() as servidor:
            servidor.noop()
    except smtplib.SMTPAuthenticationError as exc:
        raise ErrorCorreo(
            "El servidor rechazo el usuario o la contrasena. Si tu cuenta usa "
            "verificacion en dos pasos, necesitas una contrasena de aplicacion."
        ) from exc
    except OSError as exc:
        raise ErrorCorreo(f"No se pudo conectar con el servidor de correo: {exc}") from exc
    return "Conexion con el servidor de correo correcta."


def _remitente() -> str:
    cfg = config.actual().correo
    direccion = cfg.remitente or cfg.usuario
    return formataddr((cfg.remitente_nombre or config.actual().general.titular, direccion))


def _registrar(con: sqlite3.Connection, reunion_id: int, destinatario: str, asunto: str,
               estado: str, detalle: str, envio_id: int | None = None) -> int:
    """Deja constancia del envio; si se reintenta, actualiza el mismo renglon."""
    if envio_id is not None:
        con.execute(
            "UPDATE envios SET destinatario = ?, asunto = ?, estado = ?, detalle = ?, enviado = ? "
            "WHERE id = ?",
            (destinatario, asunto, estado, detalle, db.ahora(), envio_id),
        )
        con.commit()
        return envio_id
    cursor = con.execute(
        "INSERT INTO envios (reunion_id, destinatario, asunto, estado, detalle, enviado) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (reunion_id, destinatario, asunto, estado, detalle, db.ahora()),
    )
    con.commit()
    return int(cursor.lastrowid)


def enviar_minuta(con: sqlite3.Connection, reunion_id: int, destinatario: str | None = None,
                  mensaje: str = "", adjunto: Path | None = None,
                  envio_id: int | None = None) -> dict:
    """Manda la minuta en PDF y deja constancia en el expediente."""
    listo, motivo = configurado()
    if not listo:
        raise ErrorCorreo(motivo)

    fila = expediente.reunion(con, reunion_id)
    if fila is None:
        raise ErrorCorreo("La reunión no existe.")
    para = (destinatario or fila["email"] or "").strip().lower()
    if "@" not in para:
        raise ErrorCorreo("La persona no tiene un correo válido registrado.")

    pdf = adjunto or informe.minuta_pdf(con, reunion_id)
    titulo = f"Minuta de reunión · {util.fecha_corta(fila['inicio'])}"
    if fila["asunto"]:
        titulo += f" · {util.recortar_texto(fila['asunto'], 60)}"

    if por_servidor():
        return _enviar_por_servidor(con, fila, pdf, para, titulo, mensaje, envio_id)
    return _enviar_por_laptop(con, fila, pdf, para, titulo, mensaje, envio_id)


def _enviar_por_servidor(con: sqlite3.Connection, fila: sqlite3.Row, pdf: Path, para: str,
                         titulo: str, mensaje: str, envio_id: int | None) -> dict:
    """Sube la minuta a fingenieria.mx y pide que salga de ahí."""
    try:
        minuta = nube.subir_minuta(pdf, fila["nombre"], para, fila["asunto"] or "",
                                   fila["inicio"], int(fila["id"]))
        nube.enviar_minuta(int(minuta["id"]), para, mensaje)
    except nube.ErrorEnvio as error:
        _registrar(con, int(fila["id"]), para, titulo, "error", str(error), envio_id)
        raise ErrorCorreo(f"El servidor no pudo entregar el correo: {error}") from error
    except nube.ErrorNube as error:
        # Sin conexión no se pierde nada: queda pendiente y se reintenta solo.
        _registrar(con, int(fila["id"]), para, titulo, "pendiente", str(error), envio_id)
        return {"estado": "pendiente", "destinatario": para, "asunto": titulo,
                "detalle": str(error)}

    _registrar(con, int(fila["id"]), para, titulo, "enviado",
               f"{minuta.get('nombre', pdf.name)} · desde el servidor", envio_id)
    db.registrar(con, "envio", f"minuta reunión {fila['id']} -> {para} (servidor)")
    con.commit()
    return {"estado": "enviado", "destinatario": para, "asunto": titulo,
            "adjunto": minuta.get("nombre", pdf.name), "minuta_servidor": minuta.get("id")}


def _enviar_por_laptop(con: sqlite3.Connection, fila: sqlite3.Row, pdf: Path, para: str,
                       titulo: str, mensaje: str, envio_id: int | None) -> dict:
    """Salida directa por SMTP desde este equipo."""
    cfg = config.actual()
    correo = EmailMessage()
    correo["From"] = _remitente()
    correo["To"] = para
    if cfg.correo.responder_a:
        correo["Reply-To"] = cfg.correo.responder_a
    if cfg.correo.copia_oculta:
        correo["Bcc"] = cfg.correo.copia_oculta
    correo["Subject"] = titulo
    correo.set_content(mensaje.strip() or CUERPO.format(
        nombre=fila["nombre"].split()[0] if fila["nombre"] else "",
        fecha=util.fecha_larga(fila["inicio"]),
        asunto=f", sobre «{fila['asunto']}»" if fila["asunto"] else "",
        titular=cfg.general.titular,
    ))
    correo.add_attachment(pdf.read_bytes(), maintype="application", subtype="pdf",
                          filename=pdf.name)
    try:
        with _conexion() as servidor:
            servidor.send_message(correo)
    except Exception as error:
        _registrar(con, int(fila["id"]), para, titulo, "error", str(error), envio_id)
        raise ErrorCorreo(f"No se pudo enviar el correo: {error}") from error

    _registrar(con, int(fila["id"]), para, titulo, "enviado", pdf.name, envio_id)
    db.registrar(con, "envio", f"minuta reunión {fila['id']} -> {para}")
    con.commit()
    return {"estado": "enviado", "destinatario": para, "asunto": titulo, "adjunto": pdf.name}


def pendientes(con: sqlite3.Connection) -> list[sqlite3.Row]:
    return con.execute(
        "SELECT * FROM envios WHERE estado = 'pendiente' ORDER BY id"
    ).fetchall()


def reintentar_pendientes(con: sqlite3.Connection) -> int:
    """Vuelve a intentar lo que quedó esperando conexión. Lo llama el latido."""
    enviados = 0
    for envio in pendientes(con):
        try:
            resultado = enviar_minuta(con, int(envio["reunion_id"]), envio["destinatario"],
                                      envio_id=int(envio["id"]))
        except (ErrorCorreo, ValueError):
            continue   # sigue pendiente o quedó marcado como error
        if resultado.get("estado") == "enviado":
            enviados += 1
    return enviados


def envios_de(con: sqlite3.Connection, reunion_id: int) -> list[sqlite3.Row]:
    return con.execute(
        "SELECT * FROM envios WHERE reunion_id = ? ORDER BY enviado DESC", (reunion_id,)
    ).fetchall()
