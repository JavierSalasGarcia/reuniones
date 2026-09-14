"""Eleccion del mejor cuadro del video y recorte tipo credencial.

Todo aqui es numpy puro para poder probarlo sin camara ni OpenCV.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

import numpy as np

from .config import Retrato as CfgRetrato

# Pesos del puntaje compuesto. Suman 1.0.
PESOS = {
    "nitidez": 0.26,
    "frontalidad": 0.24,
    "tamano": 0.14,
    "centrado": 0.08,
    "ojos": 0.12,
    "boca": 0.08,
    "exposicion": 0.08,
}


@dataclass
class Deteccion:
    """Un rostro detectado en un cuadro, en coordenadas de pixel."""

    bbox: tuple[float, float, float, float]          # x1, y1, x2, y2
    puntos: np.ndarray                               # (5,2): ojo izq, ojo der, nariz, boca izq, boca der
    pose: tuple[float, float, float] | None = None   # yaw, pitch, roll en grados
    finos: np.ndarray | None = None                  # landmarks 106 si el modelo los da
    confianza: float = 1.0
    vector: np.ndarray | None = None                 # embedding facial

    @property
    def ancho(self) -> float:
        return self.bbox[2] - self.bbox[0]

    @property
    def alto(self) -> float:
        return self.bbox[3] - self.bbox[1]

    @property
    def centro(self) -> tuple[float, float]:
        return ((self.bbox[0] + self.bbox[2]) / 2, (self.bbox[1] + self.bbox[3]) / 2)


@dataclass
class Puntaje:
    total: float
    partes: dict[str, float] = field(default_factory=dict)

    def __lt__(self, otro: "Puntaje") -> bool:  # permite ordenar
        return self.total < otro.total


# --- medidas individuales -------------------------------------------------

def a_gris(imagen: np.ndarray) -> np.ndarray:
    if imagen.ndim == 2:
        return imagen.astype(np.float32)
    # El video llega en BGR (OpenCV); los pesos son los de luminancia.
    b, g, r = imagen[..., 0], imagen[..., 1], imagen[..., 2]
    return (0.114 * b + 0.587 * g + 0.299 * r).astype(np.float32)


def nitidez(gris: np.ndarray) -> float:
    """Varianza del laplaciano: un rostro movido o fuera de foco la baja."""
    if gris.size < 9:
        return 0.0
    centro = gris[1:-1, 1:-1]
    lap = (gris[:-2, 1:-1] + gris[2:, 1:-1] + gris[1:-1, :-2] + gris[1:-1, 2:] - 4 * centro)
    return float(lap.var())


def _normalizar(valor: float, bajo: float, alto: float) -> float:
    if alto <= bajo:
        return 0.0
    return float(min(1.0, max(0.0, (valor - bajo) / (alto - bajo))))


def puntaje_nitidez(gris_rostro: np.ndarray) -> float:
    # Por debajo de 40 la cara se ve movida; arriba de 400 ya no mejora a la vista.
    return _normalizar(nitidez(gris_rostro), 40.0, 400.0)


def puntaje_exposicion(gris_rostro: np.ndarray) -> float:
    """Premia una cara bien iluminada y pareja, sin quemados ni sombras duras."""
    if gris_rostro.size == 0:
        return 0.0
    media = float(gris_rostro.mean())
    desv = float(gris_rostro.std())
    quemado = float((gris_rostro > 250).mean())
    apagado = float((gris_rostro < 5).mean())
    # 125 es el gris medio deseable; nos alejamos de el en cualquier direccion.
    brillo = 1.0 - min(1.0, abs(media - 125.0) / 95.0)
    contraste = _normalizar(desv, 18.0, 55.0)
    castigo = min(1.0, (quemado + apagado) * 6.0)
    return float(max(0.0, (0.6 * brillo + 0.4 * contraste) * (1.0 - castigo)))


def angulos(det: Deteccion) -> tuple[float, float, float]:
    """Devuelve yaw, pitch, roll en grados; los estima de los puntos si el modelo no los da."""
    if det.pose is not None:
        return tuple(float(a) for a in det.pose)  # type: ignore[return-value]
    ojo_i, ojo_d, nariz, boca_i, boca_d = [np.asarray(p, dtype=np.float32) for p in det.puntos[:5]]
    centro_ojos = (ojo_i + ojo_d) / 2
    centro_boca = (boca_i + boca_d) / 2
    dx, dy = (ojo_d - ojo_i)[0], (ojo_d - ojo_i)[1]
    roll = float(np.degrees(np.arctan2(dy, dx)))
    ancho_ojos = float(np.hypot(dx, dy)) or 1.0
    # La nariz se desplaza hacia el lado al que gira la cabeza.
    yaw = float(np.degrees(np.arctan2((nariz[0] - centro_ojos[0]) / ancho_ojos, 1.0)) * 2.2)
    alto_cara = float(abs(centro_boca[1] - centro_ojos[1])) or 1.0
    esperado = 0.62  # proporcion tipica nariz/ojos-boca de frente
    real = float(abs(nariz[1] - centro_ojos[1])) / alto_cara
    pitch = float((real - esperado) * 90.0)
    return yaw, pitch, roll


def puntaje_frontalidad(det: Deteccion) -> float:
    yaw, pitch, roll = angulos(det)
    # Para credencial se pide mirada al frente: castigamos cualquier giro.
    p_yaw = 1.0 - min(1.0, abs(yaw) / 18.0)
    p_pitch = 1.0 - min(1.0, abs(pitch) / 16.0)
    p_roll = 1.0 - min(1.0, abs(roll) / 12.0)
    return float(max(0.0, 0.45 * p_yaw + 0.35 * p_pitch + 0.20 * p_roll))


def puntaje_tamano(det: Deteccion, forma: tuple[int, int]) -> float:
    alto_cuadro = forma[0] or 1
    proporcion = det.alto / alto_cuadro
    # Entre 28% y 55% del alto del cuadro la cara tiene resolucion de sobra.
    if proporcion < 0.28:
        return _normalizar(proporcion, 0.10, 0.28)
    if proporcion > 0.60:
        return max(0.0, 1.0 - (proporcion - 0.60) / 0.25)
    return 1.0


def puntaje_centrado(det: Deteccion, forma: tuple[int, int]) -> float:
    alto, ancho = forma[0] or 1, forma[1] or 1
    cx, cy = det.centro
    dx = abs(cx - ancho / 2) / (ancho / 2)
    dy = abs(cy - alto / 2) / (alto / 2)
    return float(max(0.0, 1.0 - (dx * 0.7 + dy * 0.5)))


def _apertura(puntos: np.ndarray, indices: Sequence[int], referencia: float) -> float:
    ys = puntos[list(indices), 1]
    return float(ys.max() - ys.min()) / (referencia or 1.0)


def puntaje_ojos(det: Deteccion) -> float:
    """Ojos abiertos. Con landmarks finos se mide; si no, se asume neutro alto."""
    if det.finos is None or len(det.finos) < 106:
        return 0.72
    ancho_ojos = float(np.linalg.norm(det.puntos[1] - det.puntos[0])) or 1.0
    # Contornos de ojo del modelo 106 de InsightFace.
    izq = _apertura(det.finos, range(33, 43), ancho_ojos)
    der = _apertura(det.finos, range(87, 97), ancho_ojos)
    promedio = (izq + der) / 2
    return _normalizar(promedio, 0.06, 0.17)


def puntaje_boca(det: Deteccion) -> float:
    """Boca cerrada y gesto neutro: para credencial, ni sonrisa amplia ni boca abierta."""
    ancho_boca = float(np.linalg.norm(det.puntos[4] - det.puntos[3])) or 1.0
    if det.finos is None or len(det.finos) < 106:
        return 0.72
    abertura = _apertura(det.finos, range(52, 72), ancho_boca)
    # Hasta 0.08 se considera cerrada; de 0.20 en adelante esta claramente abierta.
    return float(max(0.0, 1.0 - _normalizar(abertura, 0.08, 0.22)))


def puntuar(imagen: np.ndarray, det: Deteccion) -> Puntaje:
    """Puntaje compuesto de un cuadro para uso como fotografia de credencial."""
    alto, ancho = imagen.shape[0], imagen.shape[1]
    x1, y1, x2, y2 = [int(round(v)) for v in det.bbox]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(ancho, x2), min(alto, y2)
    gris = a_gris(imagen)
    recorte = gris[y1:y2, x1:x2] if x2 > x1 and y2 > y1 else gris
    partes = {
        "nitidez": puntaje_nitidez(recorte),
        "frontalidad": puntaje_frontalidad(det),
        "tamano": puntaje_tamano(det, (alto, ancho)),
        "centrado": puntaje_centrado(det, (alto, ancho)),
        "ojos": puntaje_ojos(det),
        "boca": puntaje_boca(det),
        "exposicion": puntaje_exposicion(recorte),
    }
    total = sum(PESOS[k] * v for k, v in partes.items()) * float(min(1.0, det.confianza + 0.2))
    return Puntaje(total=float(total), partes=partes)


# --- encuadre -------------------------------------------------------------

def caja_credencial(det: Deteccion, cfg: CfgRetrato) -> tuple[int, int, int, int]:
    """Rectangulo (x, y, ancho, alto) con el encuadre estandar de credencial.

    La cabeza completa ocupa `altura_cabeza` del alto y los ojos quedan a
    `ojos_desde_arriba` del borde superior.
    """
    x1, y1, x2, y2 = det.bbox
    alto_caja = y2 - y1
    # El detector encuadra de cejas a menton; la cabeza real sube y baja un poco mas.
    corona = y1 - 0.34 * alto_caja
    menton = y2 + 0.06 * alto_caja
    alto_cabeza = max(1.0, menton - corona)

    alto_retrato = alto_cabeza / max(0.05, cfg.altura_cabeza)
    ancho_retrato = alto_retrato * cfg.proporcion_ancho / cfg.proporcion_alto

    ojos = (np.asarray(det.puntos[0], dtype=np.float32) + np.asarray(det.puntos[1], dtype=np.float32)) / 2
    arriba = ojos[1] - cfg.ojos_desde_arriba * alto_retrato
    izquierda = ojos[0] - ancho_retrato / 2
    return (int(round(izquierda)), int(round(arriba)),
            int(round(ancho_retrato)), int(round(alto_retrato)))


def recortar(imagen: np.ndarray, caja: tuple[int, int, int, int]) -> np.ndarray:
    """Recorta replicando el borde cuando el encuadre se sale del cuadro."""
    x, y, ancho, alto = caja
    ancho, alto = max(1, ancho), max(1, alto)
    filas = np.clip(np.arange(y, y + alto), 0, imagen.shape[0] - 1)
    columnas = np.clip(np.arange(x, x + ancho), 0, imagen.shape[1] - 1)
    return imagen[np.ix_(filas, columnas)] if imagen.ndim == 2 else imagen[np.ix_(filas, columnas, np.arange(imagen.shape[2]))]


def normalizar_color(imagen: np.ndarray) -> np.ndarray:
    """Estira suavemente el contraste y equilibra el blanco (mundo gris)."""
    img = imagen.astype(np.float32)
    if img.ndim == 3:
        medias = img.reshape(-1, img.shape[2]).mean(axis=0)
        objetivo = float(medias.mean()) or 1.0
        img = img * (objetivo / np.maximum(medias, 1e-3))
    bajo, alto = np.percentile(img, 1.0), np.percentile(img, 99.0)
    if alto - bajo > 8:
        img = (img - bajo) * (255.0 / (alto - bajo))
    return np.clip(img, 0, 255).astype(np.uint8)
