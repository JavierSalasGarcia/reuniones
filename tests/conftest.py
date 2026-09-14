"""Piezas comunes de las pruebas: carpeta de datos aislada y rostros simulados."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reuniones import config, db  # noqa: E402
from reuniones.retrato import Deteccion  # noqa: E402


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    """Configuracion apuntando a una carpeta temporal."""
    monkeypatch.setenv("REUNIONES_DATOS", str(tmp_path / "datos"))
    cfg = config.recargar(ruta=Path("no-existe.toml"))
    cfg.crear_carpetas()
    yield cfg
    config.recargar(ruta=Path("no-existe.toml"))


@pytest.fixture
def con(entorno):
    conexion = db.preparar()
    yield conexion
    conexion.commit()
    conexion.close()


def cuadro_sintetico(nitido: bool = True, tamano=(720, 1280)) -> np.ndarray:
    """Imagen con textura; nitida o suavizada, para distinguir enfoque."""
    generador = np.random.default_rng(7)
    imagen = (generador.random((*tamano, 3)) * 90 + 90).astype(np.float32)
    if not nitido:  # promedio en bloques: equivale a desenfoque
        imagen = imagen.reshape(tamano[0] // 8, 8, tamano[1] // 8, 8, 3).mean(axis=(1, 3))
        imagen = np.repeat(np.repeat(imagen, 8, axis=0), 8, axis=1)
    return imagen.astype(np.uint8)


def deteccion(centro=(640, 350), alto=260, giro=0.0, vector=None) -> Deteccion:
    """Rostro simulado; `giro` desplaza la nariz para simular cabeza girada."""
    cx, cy = centro
    ancho = alto * 0.78
    separacion = ancho * 0.32
    puntos = np.array([
        [cx - separacion, cy - alto * 0.12],
        [cx + separacion, cy - alto * 0.12],
        [cx + giro, cy + alto * 0.10],
        [cx - separacion * 0.7, cy + alto * 0.28],
        [cx + separacion * 0.7, cy + alto * 0.28],
    ], dtype=np.float32)
    return Deteccion(
        bbox=(cx - ancho / 2, cy - alto / 2, cx + ancho / 2, cy + alto / 2),
        puntos=puntos,
        vector=vector,
    )


def detector_falso(vectores: dict[int, np.ndarray] | None = None, alto: int = 260):
    """Devuelve un detector que ve un rostro por cuadro, con el vector indicado."""
    def detectar(imagen, _contador=[0]):  # noqa: B006
        indice = _contador[0]
        _contador[0] += 1
        vector = (vectores or {}).get(indice)
        if vector is None and vectores:
            vector = next(iter(vectores.values()))
        return [deteccion(alto=alto, vector=vector)]
    return detectar
