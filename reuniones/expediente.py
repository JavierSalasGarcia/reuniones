"""Reuniones, archivos del expediente, acuerdos y resumen previo."""

from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from . import config, db, personas, util

CLASES = ("original", "minuta", "adjunto")


# --- reuniones ------------------------------------------------------------

def crear_reunion(con: sqlite3.Connection, persona_id: int, asunto: str = "",
                  inicio: datetime | None = None, categoria: str = "",
                  origen: str = "presencial") -> int:
    momento = (inicio or datetime.now()).replace(microsecond=0)
    cursor = con.execute(
        "INSERT INTO reuniones (persona_id, inicio, asunto, categoria, origen, creado) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (persona_id, momento.isoformat(sep=" "), asunto.strip(), categoria, origen, db.ahora()),
    )
    return int(cursor.lastrowid)


def reunion(con: sqlite3.Connection, reunion_id: int) -> sqlite3.Row | None:
    return con.execute(
        "SELECT r.*, p.nombre, p.email, p.foto, p.reservado "
        "FROM reuniones r JOIN personas p ON p.id = r.persona_id WHERE r.id = ?",
        (reunion_id,),
    ).fetchone()


def reuniones_de(con: sqlite3.Connection, persona_id: int, limite: int = 100) -> list[sqlite3.Row]:
    return con.execute(
        "SELECT r.*, "
        "  (SELECT COUNT(*) FROM archivos a WHERE a.reunion_id = r.id AND a.clase = 'minuta') AS tiene_minuta, "
        "  (SELECT COUNT(*) FROM archivos a WHERE a.reunion_id = r.id AND a.clase = 'original') AS tiene_original, "
        "  (SELECT COUNT(*) FROM acuerdos c WHERE c.reunion_id = r.id AND c.estado = 'abierto') AS pendientes "
        "FROM reuniones r WHERE r.persona_id = ? ORDER BY r.inicio DESC LIMIT ?",
        (persona_id, limite),
    ).fetchall()


def recientes(con: sqlite3.Connection, limite: int = 20) -> list[sqlite3.Row]:
    return con.execute(
        "SELECT r.*, p.nombre, p.email, p.foto FROM reuniones r "
        "JOIN personas p ON p.id = r.persona_id ORDER BY r.inicio DESC LIMIT ?",
        (limite,),
    ).fetchall()


def actualizar(con: sqlite3.Connection, reunion_id: int, **campos) -> None:
    permitidos = {"asunto", "categoria", "notas", "fin"}
    cambios = {k: v for k, v in campos.items() if k in permitidos}
    if not cambios:
        return
    asignaciones = ", ".join(f"{k} = ?" for k in cambios)
    con.execute(f"UPDATE reuniones SET {asignaciones} WHERE id = ?",
                (*cambios.values(), reunion_id))


# --- archivos -------------------------------------------------------------

def archivos_de(con: sqlite3.Connection, reunion_id: int, clase: str | None = None) -> list[sqlite3.Row]:
    if clase:
        return con.execute(
            "SELECT * FROM archivos WHERE reunion_id = ? AND clase = ? ORDER BY creado",
            (reunion_id, clase),
        ).fetchall()
    return con.execute(
        "SELECT * FROM archivos WHERE reunion_id = ? ORDER BY clase, creado", (reunion_id,)
    ).fetchall()


def archivo(con: sqlite3.Connection, archivo_id: int) -> sqlite3.Row | None:
    return con.execute("SELECT * FROM archivos WHERE id = ?", (archivo_id,)).fetchone()


def ruta_absoluta(fila: sqlite3.Row) -> Path:
    return config.actual().datos / fila["ruta"]


def texto_de(fila: sqlite3.Row) -> str:
    ruta = ruta_absoluta(fila)
    return util.leer_texto(ruta) if ruta.exists() else ""


def adjuntar(con: sqlite3.Connection, reunion_id: int, origen: Path, clase: str,
             sello: str | None = None, mover: bool = True) -> int:
    """Guarda el archivo dentro del expediente de la persona y lo liga a la reunion."""
    if clase not in CLASES:
        raise ValueError(f"Clase de archivo desconocida: {clase}")
    cfg = config.actual()
    fila = reunion(con, reunion_id)
    if fila is None:
        raise ValueError("La reunion no existe.")

    carpeta = personas.carpeta_expediente({"id": fila["persona_id"], "nombre": fila["nombre"]})
    carpeta.mkdir(parents=True, exist_ok=True)
    sello = sello or util.sello(util.a_fecha(fila["inicio"]) or datetime.now())
    sufijo = origen.suffix or ".txt"
    nombre = f"{sello}_{clase}{sufijo}" if clase != "adjunto" else f"{sello}_{util.apodo(origen.stem)}{sufijo}"
    destino = util.ruta_unica(carpeta / nombre)

    if mover:
        shutil.move(str(origen), destino)
    else:
        shutil.copy2(origen, destino)

    relativa = str(destino.relative_to(cfg.datos)).replace("\\", "/")
    cursor = con.execute(
        "INSERT INTO archivos (reunion_id, clase, ruta, nombre, sello, sha256, bytes, creado) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(reunion_id, clase, sello) DO UPDATE SET "
        "  ruta = excluded.ruta, nombre = excluded.nombre, sha256 = excluded.sha256, bytes = excluded.bytes",
        (reunion_id, clase, relativa, origen.name, sello, util.huella(destino),
         destino.stat().st_size, db.ahora()),
    )
    if cursor.lastrowid:
        return int(cursor.lastrowid)
    existente = con.execute(
        "SELECT id FROM archivos WHERE reunion_id = ? AND clase = ? AND sello IS ?",
        (reunion_id, clase, sello),
    ).fetchone()
    return int(existente["id"]) if existente else 0


def quitar_archivo(con: sqlite3.Connection, archivo_id: int, borrar_disco: bool = False) -> None:
    fila = archivo(con, archivo_id)
    if fila is None:
        return
    if borrar_disco:
        ruta = ruta_absoluta(fila)
        if ruta.exists():
            ruta.unlink()
    con.execute("DELETE FROM archivos WHERE id = ?", (archivo_id,))


# --- acuerdos -------------------------------------------------------------

def agregar_acuerdo(con: sqlite3.Connection, reunion_id: int, texto: str,
                    responsable: str = "", compromiso: str | None = None) -> int:
    cursor = con.execute(
        "INSERT INTO acuerdos (reunion_id, texto, responsable, compromiso, creado) "
        "VALUES (?, ?, ?, ?, ?)",
        (reunion_id, texto.strip(), responsable.strip(), compromiso, db.ahora()),
    )
    return int(cursor.lastrowid)


def acuerdos_de(con: sqlite3.Connection, reunion_id: int) -> list[sqlite3.Row]:
    return con.execute(
        "SELECT * FROM acuerdos WHERE reunion_id = ? ORDER BY estado, compromiso IS NULL, compromiso",
        (reunion_id,),
    ).fetchall()


def pendientes_de(con: sqlite3.Connection, persona_id: int) -> list[sqlite3.Row]:
    return con.execute(
        "SELECT c.*, r.inicio, r.asunto FROM acuerdos c JOIN reuniones r ON r.id = c.reunion_id "
        "WHERE r.persona_id = ? AND c.estado = 'abierto' "
        "ORDER BY c.compromiso IS NULL, c.compromiso, r.inicio DESC",
        (persona_id,),
    ).fetchall()


def cerrar_acuerdo(con: sqlite3.Connection, acuerdo_id: int, cerrado: bool = True) -> None:
    con.execute(
        "UPDATE acuerdos SET estado = ?, cerrado = ? WHERE id = ?",
        ("cerrado" if cerrado else "abierto", db.ahora() if cerrado else None, acuerdo_id),
    )


# --- resumen previo -------------------------------------------------------

def briefing(con: sqlite3.Connection, persona_id: int) -> dict:
    """Lo que necesitas saber en los segundos en que la persona se sienta."""
    persona = con.execute("SELECT * FROM personas WHERE id = ?", (persona_id,)).fetchone()
    if persona is None:
        return {}
    historial = reuniones_de(con, persona_id, limite=5)
    total = con.execute(
        "SELECT COUNT(*) AS n FROM reuniones WHERE persona_id = ?", (persona_id,)
    ).fetchone()["n"]
    abiertos = pendientes_de(con, persona_id)
    ultimo_envio = con.execute(
        "SELECT e.* FROM envios e JOIN reuniones r ON r.id = e.reunion_id "
        "WHERE r.persona_id = ? AND e.estado = 'enviado' ORDER BY e.enviado DESC LIMIT 1",
        (persona_id,),
    ).fetchone()
    return {
        "persona": persona,
        "visitas": total,
        "ultima": historial[0] if historial else None,
        "historial": historial,
        "pendientes": abiertos,
        "ultimo_envio": ultimo_envio,
    }


def resumen_en_lineas(datos: dict) -> list[str]:
    """El briefing en frases cortas, para leerlo de un vistazo."""
    if not datos:
        return []
    persona = datos["persona"]
    lineas = [f"{persona['nombre']} · {persona['email']}"]
    if datos["visitas"]:
        ultima = datos["ultima"]
        lineas.append(
            f"{datos['visitas']} visita(s). La ultima fue el {util.fecha_corta(ultima['inicio'])}"
            + (f" por «{ultima['asunto']}»." if ultima["asunto"] else ".")
        )
    else:
        lineas.append("Primera visita registrada.")
    if datos["pendientes"]:
        primero = datos["pendientes"][0]
        vence = f", comprometido para el {util.fecha_corta(primero['compromiso'])}" if primero["compromiso"] else ""
        lineas.append(f"{len(datos['pendientes'])} pendiente(s). El mas proximo: {util.recortar_texto(primero['texto'], 90)}{vence}.")
    if datos["ultimo_envio"]:
        lineas.append(f"Ultima minuta enviada el {util.fecha_corta(datos['ultimo_envio']['enviado'])}.")
    return lineas
