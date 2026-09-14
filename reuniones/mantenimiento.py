"""Tareas de limpieza: retencion de videos y archivos huerfanos."""

from __future__ import annotations

import sqlite3
from datetime import date

from . import config, db, util


def borrar_videos_vencidos(con: sqlite3.Connection) -> list[str]:
    """Borra los videos del alta cuya fecha de retencion ya paso."""
    cfg = config.actual()
    hoy = date.today().isoformat()
    borrados: list[str] = []
    filas = con.execute(
        "SELECT id, nombre, video, video_expira FROM personas "
        "WHERE video IS NOT NULL AND video_expira IS NOT NULL AND video_expira <= ?",
        (hoy,),
    ).fetchall()
    for fila in filas:
        ruta = cfg.datos / fila["video"]
        if ruta.exists():
            try:
                ruta.unlink()
            except OSError:
                continue
        borrados.append(fila["video"])
        con.execute(
            "UPDATE personas SET video = NULL, video_expira = NULL, actualizado = ? WHERE id = ?",
            (db.ahora(), fila["id"]),
        )
        db.registrar(con, "video-borrado", f"{fila['nombre']}: {fila['video']}")
    con.commit()
    return borrados


def limpiar_temporal(dias: int = 2) -> int:
    """Quita los PDF generados para envio que ya no hacen falta."""
    cfg = config.actual()
    if not cfg.temporal.exists():
        return 0
    limite = date.today().toordinal() - dias
    quitados = 0
    for ruta in cfg.temporal.iterdir():
        if ruta.is_file() and date.fromtimestamp(ruta.stat().st_mtime).toordinal() < limite:
            try:
                ruta.unlink()
                quitados += 1
            except OSError:
                pass
    return quitados


def resumen(con: sqlite3.Connection) -> dict:
    def cuenta(consulta: str) -> int:
        return int(con.execute(consulta).fetchone()[0])

    cfg = config.actual()
    proximo = con.execute(
        "SELECT MIN(video_expira) AS fecha FROM personas WHERE video IS NOT NULL"
    ).fetchone()["fecha"]
    return {
        "personas": cuenta("SELECT COUNT(*) FROM personas"),
        "reuniones": cuenta("SELECT COUNT(*) FROM reuniones"),
        "minutas": cuenta("SELECT COUNT(*) FROM archivos WHERE clase = 'minuta'"),
        "originales": cuenta("SELECT COUNT(*) FROM archivos WHERE clase = 'original'"),
        "pendientes_bandeja": cuenta("SELECT COUNT(*) FROM bandeja WHERE resuelto IS NULL"),
        "acuerdos_abiertos": cuenta("SELECT COUNT(*) FROM acuerdos WHERE estado = 'abierto'"),
        "fragmentos": cuenta("SELECT COUNT(*) FROM fragmentos"),
        "videos_guardados": cuenta("SELECT COUNT(*) FROM personas WHERE video IS NOT NULL"),
        "proximo_borrado": util.fecha_corta(proximo) or proximo or "",
        "carpeta_datos": str(cfg.datos),
    }
