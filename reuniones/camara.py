"""Captura de camara y escritura de imagenes. Requiere OpenCV en la laptop."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Iterator

import numpy as np

from .config import Camara as CfgCamara


def _cv2():
    try:
        import cv2  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - depende del equipo
        raise RuntimeError(
            "Falta OpenCV. Instala las dependencias de vision con:\n"
            "    pip install opencv-python insightface onnxruntime"
        ) from exc
    return cv2


def _backend(cv2, nombre: str) -> int:
    tabla = {
        "dshow": getattr(cv2, "CAP_DSHOW", 0),
        "msmf": getattr(cv2, "CAP_MSMF", 0),
        "v4l2": getattr(cv2, "CAP_V4L2", 0),
        "auto": getattr(cv2, "CAP_ANY", 0),
    }
    return tabla.get(nombre.lower(), tabla["auto"])


def abrir(cfg: CfgCamara):
    cv2 = _cv2()
    captura = cv2.VideoCapture(cfg.indice, _backend(cv2, cfg.backend))
    if not captura.isOpened():  # pragma: no cover - depende del equipo
        captura.release()
        raise RuntimeError(
            f"No se pudo abrir la camara {cfg.indice}. "
            "Revisa que ninguna otra aplicacion la este usando y que Windows "
            "tenga permitido el acceso a la camara para aplicaciones de escritorio."
        )
    captura.set(cv2.CAP_PROP_FRAME_WIDTH, cfg.ancho)
    captura.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg.alto)
    return captura


def cuadros(cfg: CfgCamara, segundos: float) -> Iterator[np.ndarray]:
    """Entrega los cuadros de la camara durante los segundos indicados."""
    captura = abrir(cfg)
    try:
        for _ in range(max(0, cfg.calentamiento)):  # deja que ajuste exposicion y enfoque
            captura.read()
        limite = time.monotonic() + segundos
        while time.monotonic() < limite:
            ok, cuadro = captura.read()
            if not ok:
                break
            yield cuadro
    finally:
        captura.release()


def grabar(cfg: CfgCamara, segundos: float, destino: Path | None = None) -> list[np.ndarray]:
    """Captura y, si se indica destino, deja tambien el video en disco.

    Sin destino no se escribe absolutamente nada: los cuadros viven en memoria
    mientras se calcula el vector del rostro y despues se descartan.
    """
    capturados: list[np.ndarray] = []
    escritor = None
    cv2 = _cv2()
    try:
        for cuadro in cuadros(cfg, segundos):
            capturados.append(cuadro)
            if destino is not None and escritor is None:
                destino.parent.mkdir(parents=True, exist_ok=True)
                alto, ancho = cuadro.shape[:2]
                escritor = cv2.VideoWriter(
                    str(destino), cv2.VideoWriter_fourcc(*"mp4v"), 15.0, (ancho, alto)
                )
            if escritor is not None:
                escritor.write(cuadro)
    finally:
        if escritor is not None:
            escritor.release()
    return capturados


def leer_video(ruta: Path) -> list[np.ndarray]:
    cv2 = _cv2()
    captura = cv2.VideoCapture(str(ruta))
    capturados: list[np.ndarray] = []
    try:
        while True:
            ok, cuadro = captura.read()
            if not ok:
                break
            capturados.append(cuadro)
    finally:
        captura.release()
    return capturados


# --- imagenes -------------------------------------------------------------

def redimensionar(imagen: np.ndarray, lado_mayor: int) -> np.ndarray:
    alto, ancho = imagen.shape[:2]
    mayor = max(alto, ancho)
    if mayor <= lado_mayor or mayor == 0:
        return imagen
    escala = lado_mayor / mayor
    nuevo = (max(1, int(round(ancho * escala))), max(1, int(round(alto * escala))))
    try:
        cv2 = _cv2()
    except RuntimeError:
        filas = (np.arange(nuevo[1]) / escala).astype(int).clip(0, alto - 1)
        columnas = (np.arange(nuevo[0]) / escala).astype(int).clip(0, ancho - 1)
        return imagen[np.ix_(filas, columnas)] if imagen.ndim == 2 else imagen[np.ix_(filas, columnas, np.arange(imagen.shape[2]))]
    return cv2.resize(imagen, nuevo, interpolation=cv2.INTER_AREA)


def guardar_jpg(imagen: np.ndarray, destino: Path, calidad: int = 92) -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)
    cv2 = _cv2()
    if not cv2.imwrite(str(destino), imagen, [int(cv2.IMWRITE_JPEG_QUALITY), calidad]):
        raise RuntimeError(f"No se pudo escribir la imagen en {destino}")
    return destino
