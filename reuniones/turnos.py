"""Puente entre la fila publica y los expedientes locales.

Cuando llamas a un turno, aqui se busca a la persona por su correo, se abre su
expediente y se crea la reunion con el asunto que ella misma escribio.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from . import config, db, expediente, nube, personas, util


def persona_por_email(con: sqlite3.Connection, email: str) -> sqlite3.Row | None:
    return con.execute("SELECT * FROM personas WHERE email = ?",
                       (personas.limpiar_email(email),)).fetchone()


def nombre_para_pantalla(con: sqlite3.Connection, turno: dict) -> str:
    """Respeta los casos reservados: en el monitor no se expone su nombre."""
    persona = persona_por_email(con, turno.get("email", ""))
    if persona is not None and int(persona["reservado"] or 0) == 1:
        return f"Turno {turno.get('folio', '')}".strip()
    if not config.actual().privacidad.mostrar_nombre_en_pantalla:
        return f"Turno {turno.get('folio', '')}".strip()
    partes = (turno.get("nombre") or "").split()
    return " ".join(partes[:2])


def llamar(con: sqlite3.Connection, turno: dict) -> dict:
    """Manda el turno a la pantalla y prepara el expediente."""
    nube.turno(int(turno["id"]), "llamar", nombre_para_pantalla(con, turno))
    persona = persona_por_email(con, turno.get("email", ""))
    if persona is None:
        return {"persona_id": None, "reunion_id": None,
                "email": turno.get("email", ""), "nombre": turno.get("nombre", "")}
    reunion_id = expediente.crear_reunion(con, int(persona["id"]),
                                          turno.get("asunto", ""), origen="turno")
    con.commit()
    db.registrar(con, "turno-llamado", f"{turno.get('folio')} · {persona['nombre']}")
    return {"persona_id": int(persona["id"]), "reunion_id": reunion_id,
            "email": persona["email"], "nombre": persona["nombre"]}


def cerrar(turno_id: int, accion: str) -> dict:
    """accion: atendido, ausente o cancelar."""
    return nube.turno(int(turno_id), accion)


def aprobar_cita(con: sqlite3.Connection, cita: dict, inicio: str | None = None,
                 motivo: str = "") -> dict:
    """Aprueba la reunion y se trae los archivos que la persona adjunto."""
    resultado = nube.cita(int(cita["id"]), "aprobar", inicio, motivo)
    guardar_adjuntos(con, cita)
    return resultado


def rechazar_cita(cita: dict, motivo: str) -> dict:
    return nube.cita(int(cita["id"]), "rechazar", None, motivo)


def guardar_adjuntos(con: sqlite3.Connection, cita: dict) -> list[Path]:
    """Baja los adjuntos de una cita a la carpeta local de la persona."""
    cfg = config.actual()
    persona = persona_por_email(con, cita.get("email", ""))
    if persona is not None:
        carpeta = personas.carpeta_expediente(persona)
    else:
        carpeta = cfg.adjuntos / util.apodo(cita.get("nombre", "sin-nombre"))
    guardados: list[Path] = []
    for adjunto in cita.get("adjuntos", []) or []:
        nombre = util.apodo(Path(adjunto.get("nombre", "archivo")).stem) \
            + Path(adjunto.get("nombre", "archivo")).suffix
        destino = util.ruta_unica(carpeta / f"cita-{cita['id']}-{nombre}")
        try:
            nube.descargar_adjunto(int(adjunto["id"]), destino)
        except nube.ErrorNube:
            continue
        guardados.append(destino)
    return guardados


def bloquear_reunion(inicio: datetime, minutos: int, motivo: str = "Reunión") -> dict:
    """Aparta un rato en la agenda publica para que la fila lo respete."""
    return nube.crear_bloqueo(inicio, inicio.replace(second=0, microsecond=0)
                              + _minutos(minutos), motivo)


def _minutos(cantidad: int):
    from datetime import timedelta
    return timedelta(minutes=max(1, cantidad))


def resumen_fila(datos: dict) -> dict:
    """Lo que el panel necesita mostrar de un vistazo."""
    turnos = datos.get("turnos", [])
    espera = [t for t in turnos if t.get("estado") == "espera"]
    actual = next((t for t in turnos if t.get("estado") == "llamado"), None)
    return {
        "actual": actual,
        "espera": espera,
        "atendidos": len([t for t in turnos if t.get("estado") == "atendido"]),
        "citas": datos.get("citas", []),
        "bloqueos": datos.get("bloqueos", []),
        "abierta": bool(datos.get("abierta")),
        "disponible": bool(datos.get("dependencia", {}).get("disponible")),
        "proximo_hueco": datos.get("proximo_hueco"),
    }
