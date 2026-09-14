"""Vectores faciales: extraccion con InsightFace y comparacion contra la galeria.

La parte matematica es numpy puro y se prueba sin camara; el modelo se carga
de forma perezosa para que el sitio web funcione en equipos sin camara.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np

from . import config, db
from .retrato import Deteccion

_motor: Any = None


# --- algebra de vectores --------------------------------------------------

def normalizar(vector: np.ndarray) -> np.ndarray:
    v = np.asarray(vector, dtype=np.float32).ravel()
    norma = float(np.linalg.norm(v))
    return v / norma if norma > 1e-8 else v


def promediar(vectores: Sequence[np.ndarray], pesos: Sequence[float] | None = None) -> np.ndarray:
    matriz = np.vstack([normalizar(v) for v in vectores])
    if pesos is not None and len(pesos) == len(vectores):
        w = np.asarray(pesos, dtype=np.float32).reshape(-1, 1)
        w = np.clip(w, 1e-3, None)
        matriz = matriz * w
        return normalizar(matriz.sum(axis=0) / w.sum())
    return normalizar(matriz.mean(axis=0))


def similitud(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(normalizar(a), normalizar(b)))


def a_blob(vector: np.ndarray) -> bytes:
    return normalizar(vector).astype(np.float32).tobytes()


def de_blob(datos: bytes) -> np.ndarray:
    return np.frombuffer(datos, dtype=np.float32)


# --- galeria y coincidencias ---------------------------------------------

@dataclass
class Candidato:
    persona_id: int
    nombre: str
    email: str
    foto: str | None
    similitud: float


@dataclass
class Resultado:
    """Veredicto de una identificacion."""

    estado: str                      # identificado | dudoso | desconocido
    candidatos: list[Candidato]

    @property
    def persona_id(self) -> int | None:
        return self.candidatos[0].persona_id if self.estado == "identificado" and self.candidatos else None


def galeria(con: sqlite3.Connection) -> tuple[list[sqlite3.Row], np.ndarray]:
    filas = con.execute(
        "SELECT r.id, r.persona_id, r.vector, p.nombre, p.email, p.foto "
        "FROM rostros r JOIN personas p ON p.id = r.persona_id"
    ).fetchall()
    if not filas:
        return [], np.zeros((0, 0), dtype=np.float32)
    matriz = np.vstack([de_blob(f["vector"]) for f in filas])
    return filas, matriz


def identificar(con: sqlite3.Connection, vector: np.ndarray, cfg=None) -> Resultado:
    cfg = cfg or config.actual().reconocimiento
    filas, matriz = galeria(con)
    if not filas:
        return Resultado("desconocido", [])

    similitudes = matriz @ normalizar(vector)
    # Una persona puede tener varios vectores: nos quedamos con su mejor parecido.
    mejor: dict[int, tuple[float, sqlite3.Row]] = {}
    for fila, valor in zip(filas, similitudes):
        pid = fila["persona_id"]
        if pid not in mejor or valor > mejor[pid][0]:
            mejor[pid] = (float(valor), fila)

    ordenados = sorted(mejor.values(), key=lambda par: par[0], reverse=True)
    candidatos = [
        Candidato(f["persona_id"], f["nombre"], f["email"], f["foto"], round(s, 4))
        for s, f in ordenados[: max(1, cfg.candidatos)]
    ]
    cima = candidatos[0].similitud
    if cima >= cfg.umbral_alto:
        estado = "identificado"
    elif cima >= cfg.umbral_bajo:
        estado = "dudoso"
    else:
        estado = "desconocido"
        candidatos = [c for c in candidatos if c.similitud >= cfg.umbral_bajo * 0.75]
    return Resultado(estado, candidatos)


def guardar_vector(con: sqlite3.Connection, persona_id: int, vector: np.ndarray,
                   calidad: float = 0.0, origen: str = "alta") -> int:
    v = normalizar(vector)
    cursor = con.execute(
        "INSERT INTO rostros (persona_id, vector, dimension, calidad, origen, creado) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (persona_id, a_blob(v), int(v.size), float(calidad), origen, db.ahora()),
    )
    return int(cursor.lastrowid)


# --- modelo ---------------------------------------------------------------

def motor(nombre: str | None = None):
    """Carga InsightFace una sola vez. Lanza un error claro si falta el paquete."""
    global _motor
    if _motor is not None:
        return _motor
    cfg = config.actual().reconocimiento
    try:
        from insightface.app import FaceAnalysis
    except ImportError as exc:  # pragma: no cover - depende del equipo
        raise RuntimeError(
            "Falta InsightFace. Instala las dependencias de vision con:\n"
            "    pip install opencv-python insightface onnxruntime"
        ) from exc
    app = FaceAnalysis(name=nombre or cfg.modelo, providers=["CPUExecutionProvider"])
    app.prepare(ctx_id=-1, det_size=(640, 640))
    _motor = app
    return app


def _a_deteccion(cara: Any) -> Deteccion:
    finos = getattr(cara, "landmark_2d_106", None)
    pose = getattr(cara, "pose", None)
    if pose is not None:
        pitch, yaw, roll = (float(pose[0]), float(pose[1]), float(pose[2]))
        pose = (yaw, pitch, roll)
    return Deteccion(
        bbox=tuple(float(v) for v in cara.bbox),          # type: ignore[arg-type]
        puntos=np.asarray(cara.kps, dtype=np.float32),
        pose=pose,
        finos=np.asarray(finos, dtype=np.float32) if finos is not None else None,
        confianza=float(getattr(cara, "det_score", 1.0)),
        vector=np.asarray(getattr(cara, "normed_embedding", getattr(cara, "embedding", [])), dtype=np.float32),
    )


def detectar(imagen: np.ndarray) -> list[Deteccion]:
    return [_a_deteccion(c) for c in motor().get(imagen)]


def principal(detecciones: Sequence[Deteccion], forma: tuple[int, int] | None = None) -> Deteccion | None:
    """El rostro de la persona atendida: el mas grande y cercano al centro.

    Asi alguien que pasa al fondo no desplaza a quien esta sentada enfrente.
    """
    if not detecciones:
        return None
    if forma is None:
        return max(detecciones, key=lambda d: d.ancho * d.alto)
    alto, ancho = forma

    def peso(d: Deteccion) -> float:
        area = (d.ancho * d.alto) / float(alto * ancho)
        cx, cy = d.centro
        distancia = ((cx - ancho / 2) ** 2 + (cy - alto / 2) ** 2) ** 0.5 / (ancho / 2)
        return area * (1.0 - 0.35 * min(1.0, distancia))

    return max(detecciones, key=peso)
