"""Envio de la minuta por correo institucional.

Regla del sistema: solo sale la minuta. La transcripcion original nunca se
adjunta ni se cita; se queda en la laptop.
"""

from __future__ import annotations

import smtplib
import sqlite3
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path

from . import config, db, expediente, informe, util

CUERPO = """Estimada o estimado {nombre}:

Adjunto la minuta de nuestra reunion del {fecha}{asunto}, para que quede como
antecedente de lo tratado y de los acuerdos alcanzados.

Si encuentra alguna imprecision, le agradecere que me lo haga saber.

Saludos cordiales,
{titular}
"""


class ErrorCorreo(Exception):
    """Fallas de configuracion o de entrega que la interfaz debe mostrar."""


def configurado() -> tuple[bool, str]:
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


def enviar_minuta(con: sqlite3.Connection, reunion_id: int, destinatario: str | None = None,
                  mensaje: str = "", adjunto: Path | None = None) -> dict:
    """Manda la minuta en PDF a la persona y deja constancia en el expediente."""
    listo, motivo = configurado()
    if not listo:
        raise ErrorCorreo(motivo)

    fila = expediente.reunion(con, reunion_id)
    if fila is None:
        raise ErrorCorreo("La reunion no existe.")
    para = (destinatario or fila["email"] or "").strip()
    if "@" not in para:
        raise ErrorCorreo("La persona no tiene un correo valido registrado.")

    pdf = adjunto or informe.minuta_pdf(con, reunion_id)
    cfg = config.actual()
    asunto_reunion = fila["asunto"] or ""
    titulo = f"Minuta de reunion · {util.fecha_corta(fila['inicio'])}"
    if asunto_reunion:
        titulo += f" · {util.recortar_texto(asunto_reunion, 60)}"

    correo = EmailMessage()
    correo["From"] = _remitente()
    correo["To"] = para
    if cfg_correo := config.actual().correo.responder_a:
        correo["Reply-To"] = cfg_correo   # las respuestas llegan a tu buzon institucional
    if cfg.correo.copia_oculta:
        correo["Bcc"] = cfg.correo.copia_oculta
    correo["Subject"] = titulo
    cuerpo = mensaje.strip() or CUERPO.format(
        nombre=fila["nombre"].split()[0] if fila["nombre"] else "",
        fecha=util.fecha_larga(fila["inicio"]),
        asunto=f", sobre «{asunto_reunion}»" if asunto_reunion else "",
        titular=cfg.general.titular,
    )
    correo.set_content(cuerpo)
    correo.add_attachment(pdf.read_bytes(), maintype="application", subtype="pdf",
                          filename=pdf.name)

    try:
        with _conexion() as servidor:
            servidor.send_message(correo)
    except Exception as exc:
        con.execute(
            "INSERT INTO envios (reunion_id, destinatario, asunto, estado, detalle, enviado) "
            "VALUES (?, ?, ?, 'error', ?, ?)",
            (reunion_id, para, titulo, str(exc), db.ahora()),
        )
        con.commit()
        raise ErrorCorreo(f"No se pudo enviar el correo: {exc}") from exc

    con.execute(
        "INSERT INTO envios (reunion_id, destinatario, asunto, estado, detalle, enviado) "
        "VALUES (?, ?, ?, 'enviado', ?, ?)",
        (reunion_id, para, titulo, pdf.name, db.ahora()),
    )
    db.registrar(con, "envio", f"minuta reunion {reunion_id} -> {para}")
    con.commit()
    return {"destinatario": para, "asunto": titulo, "adjunto": pdf.name}


def envios_de(con: sqlite3.Connection, reunion_id: int) -> list[sqlite3.Row]:
    return con.execute(
        "SELECT * FROM envios WHERE reunion_id = ? ORDER BY enviado DESC", (reunion_id,)
    ).fetchall()
