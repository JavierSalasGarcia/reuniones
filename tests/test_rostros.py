import numpy as np
import pytest

from reuniones import config, rostros
from tests.conftest import deteccion


def _con_parecido(base, objetivo, generador):
    """Vector con una similitud coseno exacta contra `base`."""
    unitario = rostros.normalizar(base)
    ruido = generador.normal(size=base.size).astype(np.float32)
    perpendicular = rostros.normalizar(ruido - np.dot(ruido, unitario) * unitario)
    return unitario * objetivo + perpendicular * float(np.sqrt(1 - objetivo ** 2))


def _persona(con, nombre, email):
    cursor = con.execute(
        "INSERT INTO personas (nombre, email, creado, actualizado) VALUES (?, ?, '', '')",
        (nombre, email),
    )
    return int(cursor.lastrowid)


def test_identifica_por_encima_del_umbral(con):
    base = np.random.default_rng(11).normal(size=512).astype(np.float32)
    pid = _persona(con, "Ana Ruiz", "ana@uaemex.mx")
    rostros.guardar_vector(con, pid, base)

    parecido = base + np.random.default_rng(12).normal(size=512).astype(np.float32) * 0.15
    resultado = rostros.identificar(con, parecido)
    assert resultado.estado == "identificado"
    assert resultado.persona_id == pid


def test_zona_gris_devuelve_candidatos_sin_decidir(con):
    generador = np.random.default_rng(21)
    base = generador.normal(size=512).astype(np.float32)
    pid = _persona(con, "Luis Mora", "luis@uaemex.mx")
    rostros.guardar_vector(con, pid, base)

    cfg = config.actual().reconocimiento
    objetivo = (cfg.umbral_alto + cfg.umbral_bajo) / 2
    mezcla = _con_parecido(base, objetivo, generador)

    resultado = rostros.identificar(con, mezcla)
    assert rostros.similitud(base, mezcla) == pytest.approx(objetivo, abs=0.01)
    assert resultado.estado == "dudoso"
    assert resultado.persona_id is None
    assert resultado.candidatos[0].nombre == "Luis Mora"


def test_desconocido_cuando_no_se_parece_a_nadie(con):
    generador = np.random.default_rng(31)
    pid = _persona(con, "Sara Diaz", "sara@uaemex.mx")
    rostros.guardar_vector(con, pid, generador.normal(size=512).astype(np.float32))
    resultado = rostros.identificar(con, generador.normal(size=512).astype(np.float32))
    assert resultado.estado == "desconocido"


def test_galeria_vacia_no_truena(con):
    assert rostros.identificar(con, np.ones(512, dtype=np.float32)).estado == "desconocido"


def test_promedio_de_vectores_queda_normalizado():
    generador = np.random.default_rng(41)
    vectores = [generador.normal(size=128).astype(np.float32) for _ in range(4)]
    promedio = rostros.promediar(vectores, [0.9, 0.8, 0.2, 0.1])
    assert np.linalg.norm(promedio) == 1.0


def test_rostro_principal_es_el_grande_y_centrado():
    forma = (720, 1280)
    sentado = deteccion(centro=(640, 360), alto=280)
    al_fondo = deteccion(centro=(1150, 200), alto=110)
    assert rostros.principal([al_fondo, sentado], forma) is sentado
