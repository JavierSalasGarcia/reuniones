"""Acceso a la base SQLite local."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

from . import config

ESQUEMA = Path(__file__).resolve().parent / "esquema.sql"


def ahora() -> str:
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


def conectar(ruta: Path | None = None) -> sqlite3.Connection:
    cfg = config.actual()
    ruta = ruta or cfg.base_datos
    ruta.parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False porque el servidor web atiende cada petición en el
    # hilo que le toca: la conexión es de una sola petición y nunca se comparte
    # entre dos al mismo tiempo, pero sí puede cambiar de hilo dentro de una.
    con = sqlite3.connect(ruta, detect_types=0, timeout=15.0, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = WAL")
    return con


def preparar(ruta: Path | None = None) -> sqlite3.Connection:
    """Crea la base y las tablas si no existen."""
    con = conectar(ruta)
    con.executescript(ESQUEMA.read_text(encoding="utf-8"))
    con.commit()
    return con


@contextmanager
def sesion(ruta: Path | None = None) -> Iterator[sqlite3.Connection]:
    con = preparar(ruta)
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def registrar(con: sqlite3.Connection, accion: str, detalle: str = "") -> None:
    con.execute(
        "INSERT INTO bitacora (momento, accion, detalle) VALUES (?, ?, ?)",
        (ahora(), accion, detalle),
    )


def ajuste(con: sqlite3.Connection, clave: str, predeterminado: str = "") -> str:
    fila = con.execute("SELECT valor FROM ajustes WHERE clave = ?", (clave,)).fetchone()
    return fila["valor"] if fila else predeterminado


def guardar_ajuste(con: sqlite3.Connection, clave: str, valor: str) -> None:
    con.execute(
        "INSERT INTO ajustes (clave, valor) VALUES (?, ?) "
        "ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor",
        (clave, str(valor)),
    )
