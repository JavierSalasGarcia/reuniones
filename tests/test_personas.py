from datetime import date, timedelta

import numpy as np
import pytest

from reuniones import camara, mantenimiento, personas, rostros
from tests.conftest import cuadro_sintetico, detector_falso


def _video(cuantos=12, nitido=True):
    return [cuadro_sintetico(nitido) for _ in range(cuantos)]


def test_alta_produce_fotografia_de_credencial(con, entorno):
    vector = np.random.default_rng(5).normal(size=512).astype(np.float32)
    resultado = personas.alta(con, "Ana Ruiz Lopez", "ana.ruiz@uaemex.mx",
                              _video(), detector=detector_falso({0: vector}))

    foto = entorno.datos / resultado["foto"]
    assert foto.exists()
    imagen = camara._cv2().imread(str(foto))
    alto, ancho = imagen.shape[:2]
    assert ancho / alto == pytest.approx(35 / 45, abs=0.02)
    assert max(alto, ancho) <= entorno.retrato.lado_mayor_px
    assert len(resultado["alternativas"]) == entorno.retrato.alternativas


def test_alta_guarda_vectores_y_luego_reconoce(con):
    vector = np.random.default_rng(6).normal(size=512).astype(np.float32)
    resultado = personas.alta(con, "Luis Mora", "luis.mora@uaemex.mx",
                              _video(), detector=detector_falso({0: vector}))

    guardados = con.execute("SELECT COUNT(*) FROM rostros WHERE persona_id = ?",
                            (resultado["persona_id"],)).fetchone()[0]
    assert guardados >= 1

    lectura = personas.identificar(con, _video(6), detector=detector_falso({0: vector}))
    assert lectura.resultado.estado == "identificado"
    assert lectura.resultado.persona_id == resultado["persona_id"]


def test_no_se_repite_el_correo(con):
    vector = np.random.default_rng(7).normal(size=512).astype(np.float32)
    personas.alta(con, "Ana Ruiz", "ana@uaemex.mx", _video(), detector=detector_falso({0: vector}))
    with pytest.raises(personas.ErrorAlta):
        personas.alta(con, "Ana R.", "ANA@uaemex.mx", _video(), detector=detector_falso({0: vector}))


def test_sin_rostro_avisa_con_claridad(con):
    with pytest.raises(personas.ErrorAlta, match="rostro"):
        personas.alta(con, "Nadie", "nadie@uaemex.mx", _video(), detector=lambda imagen: [])


def test_identificacion_sin_rostro_no_truena(con):
    lectura = personas.identificar(con, _video(4), detector=lambda imagen: [])
    assert lectura.resultado.estado == "desconocido"
    assert lectura.cuadros_con_rostro == 0


def test_correo_institucional(entorno):
    assert personas.es_institucional("alguien@uaemex.mx")
    assert personas.es_institucional("alguien@alumno.uaemex.mx")
    assert not personas.es_institucional("alguien@gmail.com")


def test_refuerzo_tiene_tope(con):
    generador = np.random.default_rng(8)
    vector = generador.normal(size=512).astype(np.float32)
    resultado = personas.alta(con, "Sara Diaz", "sara@uaemex.mx", _video(),
                              detector=detector_falso({0: vector}))
    pid = resultado["persona_id"]
    for _ in range(12):
        personas.reforzar(con, pid, generador.normal(size=512).astype(np.float32))
    total = con.execute("SELECT COUNT(*) FROM rostros WHERE persona_id = ?", (pid,)).fetchone()[0]
    assert total == personas.MAX_VECTORES


def test_video_del_alta_se_borra_al_vencer(con, entorno):
    vector = np.random.default_rng(9).normal(size=512).astype(np.float32)
    video = entorno.videos / "prueba.mp4"
    video.write_bytes(b"contenido")
    resultado = personas.alta(con, "Ana Ruiz", "ana@uaemex.mx", _video(),
                              video=video, detector=detector_falso({0: vector}))
    assert resultado["video_expira"] == (date.today() + timedelta(days=entorno.video.retencion_dias)).isoformat()
    assert mantenimiento.borrar_videos_vencidos(con) == []

    con.execute("UPDATE personas SET video_expira = ?", ((date.today() - timedelta(days=1)).isoformat(),))
    assert mantenimiento.borrar_videos_vencidos(con) == ["videos/prueba.mp4"]
    assert not video.exists()
    assert con.execute("SELECT video FROM personas").fetchone()[0] is None


def test_mejores_cuadros_no_son_instantes_contiguos(con):
    cuadros = _video(20)
    evaluados = personas.evaluar(cuadros, detector_falso({0: np.ones(512, dtype=np.float32)}))
    elegidos = personas.diversos(evaluados, 3, separacion=4)
    indices = sorted(c.indice for c in elegidos)
    assert all(b - a >= 4 for a, b in zip(indices, indices[1:]))
