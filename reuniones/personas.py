"""Alta de personas, fotografia de credencial e identificacion en camara."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable, Sequence

import numpy as np

from . import camara, config, db, retrato, rostros, util
from .retrato import Deteccion, Puntaje

MAX_VECTORES = 8  # por persona; mas alla de esto no mejora y solo pesa


class ErrorAlta(Exception):
    """Problemas previsibles del alta que la interfaz debe explicar al usuario."""


@dataclass
class Cuadro:
    indice: int
    imagen: np.ndarray
    deteccion: Deteccion
    puntaje: Puntaje


Detector = Callable[[np.ndarray], Sequence[Deteccion]]


# --- correo ---------------------------------------------------------------

def limpiar_email(email: str) -> str:
    return email.strip().lower()


def es_institucional(email: str, dominio: str | None = None) -> bool:
    dominio = (dominio or config.actual().general.dominio_institucional).lower().lstrip("@")
    correo = limpiar_email(email)
    return "@" in correo and correo.split("@", 1)[1].endswith(dominio)


# --- evaluacion de cuadros ------------------------------------------------

def evaluar(cuadros: Sequence[np.ndarray], detector: Detector | None = None) -> list[Cuadro]:
    """Puntua cada cuadro del video y los devuelve del mejor al peor."""
    detector = detector or rostros.detectar
    evaluados: list[Cuadro] = []
    for indice, imagen in enumerate(cuadros):
        detecciones = detector(imagen)
        principal = rostros.principal(detecciones, imagen.shape[:2])
        if principal is None:
            continue
        evaluados.append(Cuadro(indice, imagen, principal, retrato.puntuar(imagen, principal)))
    evaluados.sort(key=lambda c: c.puntaje.total, reverse=True)
    return evaluados


def diversos(evaluados: Sequence[Cuadro], cuantos: int, separacion: int = 4) -> list[Cuadro]:
    """Los mejores cuadros, evitando quedarnos con instantes casi identicos."""
    elegidos: list[Cuadro] = []
    for cuadro in evaluados:
        if all(abs(cuadro.indice - otro.indice) >= separacion for otro in elegidos):
            elegidos.append(cuadro)
        if len(elegidos) >= cuantos:
            break
    return elegidos


def construir_retrato(cuadro: Cuadro, cfg=None) -> np.ndarray:
    cfg = cfg or config.actual().retrato
    caja = retrato.caja_credencial(cuadro.deteccion, cfg)
    recorte = retrato.recortar(cuadro.imagen, caja)
    recorte = retrato.normalizar_color(recorte)
    return camara.redimensionar(recorte, cfg.lado_mayor_px)


def _vector_promedio(elegidos: Sequence[Cuadro]) -> np.ndarray | None:
    vectores = [c.deteccion.vector for c in elegidos if c.deteccion.vector is not None and c.deteccion.vector.size]
    if not vectores:
        return None
    pesos = [c.puntaje.total for c in elegidos if c.deteccion.vector is not None and c.deteccion.vector.size]
    return rostros.promediar(vectores, pesos)


# --- alta -----------------------------------------------------------------

def alta(con: sqlite3.Connection, nombre: str, email: str, cuadros: Sequence[np.ndarray],
         video: Path | None = None, detector: Detector | None = None,
         adscripcion: str = "", tipo: str = "otro", consentimiento: bool = True) -> dict:
    """Registra a la persona a partir del video breve del primer encuentro."""
    cfg = config.actual()
    nombre = " ".join(nombre.split())
    correo = limpiar_email(email)
    if not nombre:
        raise ErrorAlta("Falta el nombre de la persona.")
    if "@" not in correo:
        raise ErrorAlta("El correo no es valido.")
    if con.execute("SELECT id FROM personas WHERE email = ?", (correo,)).fetchone():
        raise ErrorAlta(f"Ya existe un expediente con el correo {correo}.")

    evaluados = evaluar(cuadros, detector)
    if not evaluados:
        raise ErrorAlta(
            "No se detecto ningun rostro en el video. Revisa la iluminacion y "
            "que la persona quede de frente a la camara."
        )

    momento = db.ahora()
    cursor = con.execute(
        "INSERT INTO personas (nombre, email, adscripcion, tipo, consentimiento, creado, actualizado) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (nombre, correo, adscripcion, tipo, momento if consentimiento else None, momento, momento),
    )
    persona_id = int(cursor.lastrowid)

    base = f"{persona_id:04d}-{util.apodo(nombre)}"
    principales = diversos(evaluados, 1 + cfg.retrato.alternativas)
    rutas: list[str] = []
    for posicion, cuadro in enumerate(principales):
        imagen = construir_retrato(cuadro, cfg.retrato)
        nombre_archivo = f"{base}.jpg" if posicion == 0 else f"{base}-alt{posicion}.jpg"
        destino = camara.guardar_jpg(imagen, cfg.fotos / nombre_archivo)
        rutas.append(str(destino.relative_to(cfg.datos)).replace("\\", "/"))

    para_vector = diversos(evaluados, cfg.reconocimiento.rostros_por_alta, separacion=2)
    promedio = _vector_promedio(para_vector)
    if promedio is not None:
        rostros.guardar_vector(con, persona_id, promedio,
                               calidad=para_vector[0].puntaje.total, origen="alta")
        for cuadro in para_vector[:2]:
            if cuadro.deteccion.vector is not None and cuadro.deteccion.vector.size:
                rostros.guardar_vector(con, persona_id, cuadro.deteccion.vector,
                                       calidad=cuadro.puntaje.total, origen="alta-cuadro")

    ruta_video = None
    expira = None
    if video is not None and cfg.privacidad.guardar_video_alta:
        ruta_video = str(Path(video).relative_to(cfg.datos)).replace("\\", "/")
        expira = (date.today() + timedelta(days=cfg.video.retencion_dias)).isoformat()

    con.execute(
        "UPDATE personas SET foto = ?, alternativas = ?, video = ?, video_expira = ?, actualizado = ? "
        "WHERE id = ?",
        (rutas[0] if rutas else None, "|".join(rutas[1:]), ruta_video, expira, db.ahora(), persona_id),
    )
    db.registrar(con, "alta", f"{nombre} <{correo}>")
    return {
        "persona_id": persona_id,
        "foto": rutas[0] if rutas else None,
        "alternativas": rutas[1:],
        "puntaje": round(evaluados[0].puntaje.total, 4),
        "partes": {k: round(v, 3) for k, v in evaluados[0].puntaje.partes.items()},
        "cuadros_con_rostro": len(evaluados),
        "video": ruta_video,
        "video_expira": expira,
    }


def alta_con_camara(con: sqlite3.Connection, nombre: str, email: str, **extra) -> dict:
    cfg = config.actual()
    cfg.crear_carpetas()
    destino = cfg.videos / f"{util.sello(datetime.now())}-{util.apodo(nombre)}.mp4"
    guardar = cfg.privacidad.guardar_video_alta
    cuadros = camara.grabar(cfg.camara, cfg.camara.segundos_alta, destino if guardar else None)
    if not cuadros:
        raise ErrorAlta("La camara no entrego ningun cuadro.")
    return alta(con, nombre, email, cuadros, destino if guardar else None, **extra)


# --- identificacion -------------------------------------------------------

@dataclass
class Identificacion:
    resultado: rostros.Resultado
    calidad: float
    vector: np.ndarray | None
    cuadros_con_rostro: int


def identificar(con: sqlite3.Connection, cuadros: Sequence[np.ndarray],
                detector: Detector | None = None) -> Identificacion:
    evaluados = evaluar(cuadros, detector)
    if not evaluados:
        return Identificacion(rostros.Resultado("desconocido", []), 0.0, None, 0)
    mejores = diversos(evaluados, 3, separacion=2)
    vector = _vector_promedio(mejores)
    if vector is None:
        return Identificacion(rostros.Resultado("desconocido", []), 0.0, None, len(evaluados))
    resultado = rostros.identificar(con, vector)
    return Identificacion(resultado, round(mejores[0].puntaje.total, 4), vector, len(evaluados))


def identificar_con_camara(con: sqlite3.Connection) -> Identificacion:
    """Dos segundos de camara en vivo. No se escribe nada en disco."""
    cfg = config.actual()
    cuadros = camara.grabar(cfg.camara, cfg.camara.segundos_identificacion, None)
    return identificar(con, cuadros)


def reforzar(con: sqlite3.Connection, persona_id: int, vector: np.ndarray, calidad: float = 0.0) -> bool:
    """Guarda el vector de una visita para que el reconocimiento mejore con el tiempo."""
    total = con.execute(
        "SELECT COUNT(*) AS n FROM rostros WHERE persona_id = ?", (persona_id,)
    ).fetchone()["n"]
    if total >= MAX_VECTORES:
        return False
    rostros.guardar_vector(con, persona_id, vector, calidad, origen="visita")
    return True


# --- mantenimiento de fotos ----------------------------------------------

def reprocesar_foto(con: sqlite3.Connection, persona_id: int, posicion: int = 1) -> str:
    """Vuelve a elegir la fotografia usando el video del alta, si aun existe."""
    cfg = config.actual()
    fila = con.execute("SELECT * FROM personas WHERE id = ?", (persona_id,)).fetchone()
    if fila is None:
        raise ErrorAlta("La persona no existe.")
    if not fila["video"]:
        raise ErrorAlta("El video del alta ya fue borrado; toma un video nuevo para cambiar la foto.")
    ruta = cfg.datos / fila["video"]
    if not ruta.exists():
        raise ErrorAlta("El video del alta ya no esta en disco.")

    evaluados = evaluar(camara.leer_video(ruta))
    if not evaluados:
        raise ErrorAlta("No se detectaron rostros en el video guardado.")
    elegidos = diversos(evaluados, max(2, posicion + 1))
    cuadro = elegidos[min(posicion, len(elegidos) - 1)]
    imagen = construir_retrato(cuadro, cfg.retrato)
    nombre_archivo = f"{persona_id:04d}-{util.apodo(fila['nombre'])}.jpg"
    destino = camara.guardar_jpg(imagen, cfg.fotos / nombre_archivo)
    relativa = str(destino.relative_to(cfg.datos)).replace("\\", "/")
    con.execute("UPDATE personas SET foto = ?, actualizado = ? WHERE id = ?",
                (relativa, db.ahora(), persona_id))
    return relativa


def carpeta_expediente(fila: sqlite3.Row | dict) -> Path:
    cfg = config.actual()
    return cfg.expedientes / f"{int(fila['id']):04d}-{util.apodo(fila['nombre'])}"


def buscar(con: sqlite3.Connection, texto: str = "", limite: int = 50) -> list[sqlite3.Row]:
    patron = f"%{texto.strip()}%"
    return con.execute(
        "SELECT p.*, "
        "  (SELECT COUNT(*) FROM reuniones r WHERE r.persona_id = p.id) AS reuniones, "
        "  (SELECT MAX(r.inicio) FROM reuniones r WHERE r.persona_id = p.id) AS ultima "
        "FROM personas p "
        "WHERE ? = '' OR p.nombre LIKE ? OR p.email LIKE ? OR p.adscripcion LIKE ? "
        "ORDER BY ultima IS NULL, ultima DESC, p.nombre "
        "LIMIT ?",
        (texto.strip(), patron, patron, patron, limite),
    ).fetchall()
