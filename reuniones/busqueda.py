"""Busqueda sobre minutas y transcripciones.

Por omision todo ocurre en la laptop: palabras clave con SQLite y significado
con un modelo local de vectores. Gemini solo entra si tu lo pides de forma
explicita, y en ese caso solo viajan los fragmentos encontrados.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np

from . import config, db, expediente, util

_modelo: Any = None
_modelo_fallido = False


# --- fragmentacion --------------------------------------------------------

def fragmentar(texto: str, palabras: int = 180, traslape: int = 40) -> list[str]:
    piezas = texto.split()
    if not piezas:
        return []
    paso = max(1, palabras - max(0, traslape))
    fragmentos = []
    for inicio in range(0, len(piezas), paso):
        trozo = piezas[inicio: inicio + palabras]
        if trozo:
            fragmentos.append(" ".join(trozo))
        if inicio + palabras >= len(piezas):
            break
    return fragmentos


# --- modelo local de vectores --------------------------------------------

def modelo_local():
    """Carga el modelo de embeddings si esta instalado; si no, devuelve None."""
    global _modelo, _modelo_fallido
    if _modelo is not None or _modelo_fallido:
        return _modelo
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        _modelo_fallido = True
        return None
    try:
        _modelo = SentenceTransformer(config.actual().busqueda.modelo_local)
    except Exception:  # sin modelo descargado seguimos con palabras clave
        _modelo_fallido = True
        return None
    return _modelo


def vectorizar(textos: Sequence[str]) -> np.ndarray | None:
    modelo = modelo_local()
    if modelo is None or not textos:
        return None
    vectores = modelo.encode(list(textos), normalize_embeddings=True, show_progress_bar=False)
    return np.asarray(vectores, dtype=np.float32)


# --- indice ---------------------------------------------------------------

def indexar_archivo(con: sqlite3.Connection, archivo_id: int) -> int:
    fila = expediente.archivo(con, archivo_id)
    if fila is None or fila["clase"] not in ("minuta", "original"):
        return 0
    texto = expediente.texto_de(fila)
    if not texto.strip():
        return 0
    cfg = config.actual().busqueda
    con.execute("DELETE FROM fragmentos WHERE archivo_id = ?", (archivo_id,))
    piezas = fragmentar(texto, cfg.fragmento_palabras, cfg.traslape_palabras)
    vectores = vectorizar(piezas)
    for orden, pieza in enumerate(piezas):
        vector = vectores[orden] if vectores is not None else None
        con.execute(
            "INSERT INTO fragmentos (reunion_id, archivo_id, clase, orden, texto, vector, dimension) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (fila["reunion_id"], archivo_id, fila["clase"], orden, pieza,
             vector.astype(np.float32).tobytes() if vector is not None else None,
             int(vector.size) if vector is not None else None),
        )
    return len(piezas)


def reindexar(con: sqlite3.Connection) -> int:
    total = 0
    for fila in con.execute("SELECT id FROM archivos WHERE clase IN ('minuta','original')").fetchall():
        total += indexar_archivo(con, int(fila["id"]))
    con.commit()
    return total


# --- consulta -------------------------------------------------------------

@dataclass
class Hallazgo:
    fragmento_id: int
    reunion_id: int
    persona: str
    persona_id: int
    inicio: str
    asunto: str
    clase: str
    texto: str
    puntaje: float
    via: str  # palabras | significado | ambos


def _fts(con: sqlite3.Connection, consulta: str, limite: int) -> dict[int, float]:
    termino = " OR ".join(
        f'"{p}"' for p in util.sin_acentos(consulta).split() if len(p) > 2
    )
    if not termino:
        return {}
    try:
        filas = con.execute(
            "SELECT rowid, bm25(fragmentos_fts) AS puntaje FROM fragmentos_fts "
            "WHERE fragmentos_fts MATCH ? ORDER BY puntaje LIMIT ?",
            (termino, limite * 3),
        ).fetchall()
    except sqlite3.OperationalError:
        return {}
    # bm25 devuelve valores negativos donde mas negativo es mejor.
    return {int(f["rowid"]): 1.0 / (1.0 + max(0.0, float(f["puntaje"]) + 20.0)) for f in filas}


def _vectorial(con: sqlite3.Connection, consulta: str, limite: int) -> dict[int, float]:
    vector = vectorizar([consulta])
    if vector is None:
        return {}
    filas = con.execute("SELECT id, vector FROM fragmentos WHERE vector IS NOT NULL").fetchall()
    if not filas:
        return {}
    matriz = np.vstack([np.frombuffer(f["vector"], dtype=np.float32) for f in filas])
    similitudes = matriz @ vector[0]
    mejores = np.argsort(-similitudes)[: limite * 3]
    return {int(filas[i]["id"]): float(similitudes[i]) for i in mejores if similitudes[i] > 0.25}


def buscar(con: sqlite3.Connection, consulta: str, limite: int | None = None,
           persona_id: int | None = None) -> list[Hallazgo]:
    """Busqueda hibrida: palabras clave y significado, fusionadas por puntaje."""
    limite = limite or config.actual().busqueda.resultados
    consulta = consulta.strip()
    if not consulta:
        return []

    por_palabras = _fts(con, consulta, limite)
    por_significado = _vectorial(con, consulta, limite)
    claves = set(por_palabras) | set(por_significado)
    if not claves:
        return []

    marcadores = ",".join("?" * len(claves))
    filas = con.execute(
        f"SELECT f.id, f.reunion_id, f.clase, f.texto, r.inicio, r.asunto, r.persona_id, p.nombre "
        f"FROM fragmentos f JOIN reuniones r ON r.id = f.reunion_id "
        f"JOIN personas p ON p.id = r.persona_id WHERE f.id IN ({marcadores})",
        tuple(claves),
    ).fetchall()

    hallazgos: list[Hallazgo] = []
    for fila in filas:
        if persona_id is not None and fila["persona_id"] != persona_id:
            continue
        clave = int(fila["id"])
        palabras = por_palabras.get(clave, 0.0)
        significado = por_significado.get(clave, 0.0)
        via = "ambos" if palabras and significado else ("palabras" if palabras else "significado")
        hallazgos.append(Hallazgo(
            fragmento_id=clave,
            reunion_id=int(fila["reunion_id"]),
            persona=fila["nombre"],
            persona_id=int(fila["persona_id"]),
            inicio=fila["inicio"],
            asunto=fila["asunto"],
            clase=fila["clase"],
            texto=fila["texto"],
            puntaje=round(0.45 * palabras + 0.55 * significado, 4),
            via=via,
        ))
    hallazgos.sort(key=lambda h: h.puntaje, reverse=True)
    return hallazgos[:limite]


# --- redaccion opcional con Gemini ---------------------------------------

PLANTILLA = (
    "Eres asistente de la {titular}. Responde en espanol, en un parrafo breve y "
    "concreto, usando unicamente los fragmentos de minutas que siguen. Si no "
    "alcanzan para responder, dilo con claridad.\n\n"
    "Pregunta: {consulta}\n\nFragmentos:\n{fragmentos}"
)


def hay_gemini() -> bool:
    return bool(config.actual().clave_gemini)


def responder(con: sqlite3.Connection, consulta: str, hallazgos: Sequence[Hallazgo] | None = None) -> str:
    """Redacta una respuesta con Gemini. Envia a Google solo los fragmentos hallados."""
    cfg = config.actual()
    if not cfg.clave_gemini:
        raise RuntimeError(
            "No hay GEMINI_API_KEY configurada en el archivo .env; la busqueda "
            "local sigue funcionando sin ella."
        )
    hallazgos = hallazgos if hallazgos is not None else buscar(con, consulta)
    if not hallazgos:
        return "No encontre nada en las minutas sobre eso."
    try:
        from google import genai
    except ImportError as exc:
        raise RuntimeError("Falta el paquete google-genai: pip install google-genai") from exc

    contexto = "\n\n".join(
        f"[{i + 1}] {h.persona} · {util.fecha_corta(h.inicio)} · {h.asunto or 'sin asunto'}\n{h.texto}"
        for i, h in enumerate(hallazgos)
    )
    cliente = genai.Client(api_key=cfg.clave_gemini)
    respuesta = cliente.models.generate_content(
        model=cfg.busqueda.gemini_modelo,
        contents=PLANTILLA.format(titular=cfg.general.titular, consulta=consulta, fragmentos=contexto),
    )
    db.registrar(con, "gemini", f"consulta: {util.recortar_texto(consulta, 80)}")
    return (respuesta.text or "").strip()
