"""Vigilancia de la carpeta de transcripciones y asociacion con las reuniones.

Sueltas en la carpeta los archivos que produce el telefono con el formato
yyyymmdd_hhmm_original.txt y yyyymmdd_hhmm_minuta.txt; el sistema los liga
solos a la reunion mas cercana en tiempo y, si hay duda, los deja en bandeja.
"""

from __future__ import annotations

import re
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from . import config, db, expediente, util

PATRON = re.compile(
    r"^(?P<fecha>\d{8})[_-](?P<hora>\d{4})[_-](?P<clase>original|minuta)\b",
    re.IGNORECASE,
)
EXTENSIONES = {".txt", ".md"}
MARGEN_AMBIGUO = timedelta(minutes=15)


@dataclass
class Analisis:
    sello: str
    momento: datetime
    clase: str


@dataclass
class Desenlace:
    estado: str            # asociado | duplicado | bandeja | ignorado
    motivo: str = ""
    reunion_id: int | None = None
    archivo_id: int | None = None
    bandeja_id: int | None = None


def analizar_nombre(nombre: str) -> Analisis | None:
    ruta = Path(nombre)
    if ruta.suffix.lower() not in EXTENSIONES:
        return None
    coincidencia = PATRON.match(util.sin_acentos(ruta.name))
    if not coincidencia:
        return None
    sello = f"{coincidencia.group('fecha')}_{coincidencia.group('hora')}"
    momento = util.de_sello(sello)
    if momento is None:
        return None
    return Analisis(sello, momento, coincidencia.group("clase").lower())


def candidatas(con: sqlite3.Connection, momento: datetime, cfg=None) -> list[sqlite3.Row]:
    """Reuniones compatibles con la hora del nombre del archivo, de la mas cercana a la mas lejana."""
    cfg = cfg or config.actual().transcripciones
    desde = momento - timedelta(hours=cfg.ventana_horas_atras)
    hasta = momento + timedelta(minutes=cfg.ventana_minutos_adelante)
    filas = con.execute(
        "SELECT r.*, p.nombre FROM reuniones r JOIN personas p ON p.id = r.persona_id "
        "WHERE r.inicio BETWEEN ? AND ? ORDER BY r.inicio DESC",
        (desde.isoformat(sep=" "), hasta.isoformat(sep=" ")),
    ).fetchall()
    return sorted(filas, key=lambda f: abs((util.a_fecha(f["inicio"]) or momento) - momento))


def _a_bandeja(con: sqlite3.Connection, ruta: Path, analisis: Analisis | None, motivo: str) -> Desenlace:
    cursor = con.execute(
        "INSERT INTO bandeja (ruta, nombre, clase, sello, motivo, detectado) "
        "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(ruta) DO UPDATE SET motivo = excluded.motivo",
        (str(ruta), ruta.name, analisis.clase if analisis else "desconocido",
         analisis.sello if analisis else None, motivo, db.ahora()),
    )
    fila = con.execute("SELECT id FROM bandeja WHERE ruta = ?", (str(ruta),)).fetchone()
    return Desenlace("bandeja", motivo, bandeja_id=int(fila["id"]) if fila else cursor.lastrowid)


def asociar(con: sqlite3.Connection, ruta: Path) -> Desenlace:
    """Intenta ligar un archivo suelto con su reunion."""
    analisis = analizar_nombre(ruta.name)
    if analisis is None:
        return Desenlace(
            "ignorado",
            "El nombre no sigue el formato yyyymmdd_hhmm_original.txt o yyyymmdd_hhmm_minuta.txt.",
        )

    posibles = candidatas(con, analisis.momento)
    if not posibles:
        return _a_bandeja(con, ruta, analisis,
                          "No hay ninguna reunion registrada cerca de esa fecha y hora.")

    if len(posibles) > 1:
        primera = abs((util.a_fecha(posibles[0]["inicio"]) or analisis.momento) - analisis.momento)
        segunda = abs((util.a_fecha(posibles[1]["inicio"]) or analisis.momento) - analisis.momento)
        if segunda - primera < MARGEN_AMBIGUO:
            nombres = ", ".join(f["nombre"] for f in posibles[:3])
            return _a_bandeja(con, ruta, analisis,
                              f"Hay mas de una reunion a esa hora ({nombres}).")

    elegida = posibles[0]
    ya = con.execute(
        "SELECT id FROM archivos WHERE reunion_id = ? AND clase = ? AND sello = ?",
        (elegida["id"], analisis.clase, analisis.sello),
    ).fetchone()
    if ya is not None:
        return Desenlace("duplicado", "Ese archivo ya estaba en el expediente.",
                         reunion_id=int(elegida["id"]), archivo_id=int(ya["id"]))

    archivo_id = expediente.adjuntar(con, int(elegida["id"]), ruta, analisis.clase, analisis.sello)
    con.execute("UPDATE bandeja SET resuelto = ? WHERE ruta = ?", (db.ahora(), str(ruta)))
    db.registrar(con, "ingesta", f"{ruta.name} -> reunion {elegida['id']} ({elegida['nombre']})")
    _indexar(con, int(elegida["id"]), archivo_id)
    return Desenlace("asociado", "", reunion_id=int(elegida["id"]), archivo_id=archivo_id)


def asignar_manual(con: sqlite3.Connection, bandeja_id: int, reunion_id: int) -> Desenlace:
    fila = con.execute("SELECT * FROM bandeja WHERE id = ?", (bandeja_id,)).fetchone()
    if fila is None:
        return Desenlace("ignorado", "El pendiente ya no existe.")
    ruta = Path(fila["ruta"])
    if not ruta.exists():
        con.execute("DELETE FROM bandeja WHERE id = ?", (bandeja_id,))
        return Desenlace("ignorado", "El archivo ya no esta en la carpeta.")
    clase = fila["clase"] if fila["clase"] in expediente.CLASES else "adjunto"
    archivo_id = expediente.adjuntar(con, reunion_id, ruta, clase, fila["sello"])
    con.execute("DELETE FROM bandeja WHERE id = ?", (bandeja_id,))
    _indexar(con, reunion_id, archivo_id)
    return Desenlace("asociado", "", reunion_id=reunion_id, archivo_id=archivo_id)


def _indexar(con: sqlite3.Connection, reunion_id: int, archivo_id: int | None) -> None:
    if not archivo_id:
        return
    try:
        from . import busqueda
        busqueda.indexar_archivo(con, archivo_id)
    except Exception as error:  # el indice no debe bloquear la ingesta
        db.registrar(con, "indice-error", f"archivo {archivo_id}: {error}")


def revisar_carpeta(con: sqlite3.Connection, carpeta: Path | None = None) -> list[tuple[str, Desenlace]]:
    """Procesa lo que ya estaba en la carpeta (por ejemplo al arrancar el sistema)."""
    cfg = config.actual()
    carpeta = carpeta or cfg.entrada
    carpeta.mkdir(parents=True, exist_ok=True)
    resultados: list[tuple[str, Desenlace]] = []
    for ruta in sorted(carpeta.iterdir()):
        if not ruta.is_file() or ruta.suffix.lower() not in EXTENSIONES:
            continue
        pendiente = con.execute(
            "SELECT id FROM bandeja WHERE ruta = ? AND resuelto IS NULL", (str(ruta),)
        ).fetchone()
        if pendiente is not None:
            continue  # ya esta en bandeja esperando decision tuya
        resultados.append((ruta.name, asociar(con, ruta)))
    con.commit()
    return resultados


def esperar_copia(ruta: Path, intentos: int = 20, pausa: float = 0.3) -> bool:
    """Espera a que el archivo termine de copiarse antes de tocarlo."""
    anterior = -1
    for _ in range(intentos):
        try:
            actual = ruta.stat().st_size
        except OSError:  # alguien mas ya lo movio o lo borro
            return False
        if actual == anterior and actual > 0:
            return True
        anterior = actual
        time.sleep(pausa)
    return ruta.exists()


class Vigilante:
    """Observa la carpeta de transcripciones mientras el servidor esta encendido."""

    def __init__(self, carpeta: Path | None = None) -> None:
        self.carpeta = carpeta or config.actual().entrada
        self._observador = None

    def iniciar(self) -> None:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer

        carpeta = self.carpeta
        carpeta.mkdir(parents=True, exist_ok=True)

        class Manejador(FileSystemEventHandler):
            def _procesar(self, ruta_texto: str) -> None:
                ruta = Path(ruta_texto)
                if ruta.suffix.lower() not in EXTENSIONES or not esperar_copia(ruta):
                    return
                try:
                    with db.sesion() as con:
                        asociar(con, ruta)
                except Exception as error:
                    # Un archivo raro no debe tumbar la vigilancia de la carpeta.
                    with db.sesion() as con:
                        db.registrar(con, "ingesta-error", f"{ruta.name}: {error}")

            def on_created(self, evento):  # noqa: N802
                if not evento.is_directory:
                    self._procesar(evento.src_path)

            def on_moved(self, evento):  # noqa: N802
                if not evento.is_directory:
                    self._procesar(evento.dest_path)

        self._observador = Observer()
        self._observador.schedule(Manejador(), str(carpeta), recursive=False)
        self._observador.daemon = True
        self._observador.start()

    def detener(self) -> None:
        if self._observador is not None:
            self._observador.stop()
            self._observador.join(timeout=3)
            self._observador = None
