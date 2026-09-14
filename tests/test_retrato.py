import numpy as np
import pytest

from reuniones import retrato
from reuniones.config import Retrato
from tests.conftest import cuadro_sintetico, deteccion


def test_cuadro_nitido_gana_al_movido():
    nitido = cuadro_sintetico(True)
    movido = cuadro_sintetico(False)
    det = deteccion()
    assert retrato.puntuar(nitido, det).total > retrato.puntuar(movido, det).total


def test_rostro_de_frente_gana_al_girado():
    imagen = cuadro_sintetico()
    frente = retrato.puntuar(imagen, deteccion(giro=0)).partes["frontalidad"]
    girado = retrato.puntuar(imagen, deteccion(giro=45)).partes["frontalidad"]
    assert frente > girado


def test_rostro_muy_pequeno_pierde_puntos():
    imagen = cuadro_sintetico()
    grande = retrato.puntuar(imagen, deteccion(alto=300)).partes["tamano"]
    chico = retrato.puntuar(imagen, deteccion(alto=70)).partes["tamano"]
    assert grande == pytest.approx(1.0)
    assert chico < 0.5


def test_exposicion_castiga_quemados():
    quemado = np.full((120, 100), 255, dtype=np.float32)
    parejo = (np.random.default_rng(3).random((120, 100)) * 60 + 95).astype(np.float32)
    assert retrato.puntaje_exposicion(parejo) > retrato.puntaje_exposicion(quemado)


def test_encuadre_respeta_proporcion_y_altura_de_ojos():
    cfg = Retrato()
    det = deteccion(centro=(640, 360), alto=260)
    x, y, ancho, alto = retrato.caja_credencial(det, cfg)
    assert ancho / alto == pytest.approx(cfg.proporcion_ancho / cfg.proporcion_alto, abs=0.01)
    ojos_y = (det.puntos[0][1] + det.puntos[1][1]) / 2
    assert (ojos_y - y) / alto == pytest.approx(cfg.ojos_desde_arriba, abs=0.01)


def test_recorte_fuera_del_cuadro_no_falla():
    imagen = cuadro_sintetico(tamano=(400, 400))
    recorte = retrato.recortar(imagen, (-50, -80, 300, 386))
    assert recorte.shape == (386, 300, 3)


def test_normalizar_color_estira_contraste():
    plano = np.full((50, 50, 3), 120, dtype=np.uint8)
    plano[10:20] = 130
    resultado = retrato.normalizar_color(plano)
    assert resultado.max() - resultado.min() > plano.max() - plano.min()
