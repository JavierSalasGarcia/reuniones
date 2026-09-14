"""Carga de configuracion: config.toml para lo ajustable, .env para lo secreto."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent


@dataclass
class General:
    carpeta_datos: str = "datos"
    dominio_institucional: str = "uaemex.mx"
    sitio_publico: str = "https://fingenieria.mx/citas/sa"
    titular: str = "Subdireccion Academica"
    puerto_web: int = 8000


@dataclass
class Camara:
    indice: int = 0
    backend: str = "auto"  # auto | dshow | msmf | v4l2
    ancho: int = 1280
    alto: int = 720
    segundos_alta: int = 6
    segundos_identificacion: int = 2
    calentamiento: int = 8  # cuadros descartados mientras la camara ajusta exposicion


@dataclass
class Reconocimiento:
    modelo: str = "buffalo_l"
    umbral_alto: float = 0.55
    umbral_bajo: float = 0.40
    candidatos: int = 3
    rostros_por_alta: int = 5  # cuantos cuadros aportan al vector promedio


@dataclass
class Retrato:
    proporcion_ancho: int = 35   # milimetros, formato credencial
    proporcion_alto: int = 45
    altura_cabeza: float = 0.68  # alto de la cabeza respecto al alto del retrato
    ojos_desde_arriba: float = 0.42
    lado_mayor_px: int = 900
    alternativas: int = 2        # cuadros extra guardados por si el elegido no convence


@dataclass
class Video:
    retencion_dias: int = 7


@dataclass
class Transcripciones:
    ventana_horas_atras: int = 3
    ventana_minutos_adelante: int = 30


@dataclass
class Correo:
    """Salida de correo. Todo sale por el SMTP de fingenieria.mx."""

    servidor: str = "mail.fingenieria.mx"
    puerto: int = 587
    starttls: bool = True
    usuario: str = ""
    remitente: str = ""
    remitente_nombre: str = ""
    responder_a: str = ""       # tu correo institucional, para que te contesten a ti
    copia_oculta: str = ""


@dataclass
class Busqueda:
    modelo_local: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    fragmento_palabras: int = 180
    traslape_palabras: int = 40
    resultados: int = 8
    gemini_modelo: str = "gemini-2.5-flash"


@dataclass
class Nube:
    """Sitio publico donde viven los turnos y las citas."""

    url: str = "https://fingenieria.mx/citas"
    dependencia: str = "sa"
    refresco_segundos: int = 8      # cada cuanto se puede repetir una consulta
    latido_segundos: int = 60       # consulta de fondo mientras el sitio local corre
    espera_segundos: int = 12


@dataclass
class Kiosco:
    """Respaldo en la red local para el monitor de la entrada."""

    habilitado: bool = True
    puerto: int = 8010
    escuchar: str = "0.0.0.0"   # solo se sirve la pantalla de turnos, nada mas


@dataclass
class Privacidad:
    mostrar_nombre_en_pantalla: bool = True
    guardar_video_alta: bool = True


@dataclass
class Config:
    general: General = field(default_factory=General)
    camara: Camara = field(default_factory=Camara)
    reconocimiento: Reconocimiento = field(default_factory=Reconocimiento)
    retrato: Retrato = field(default_factory=Retrato)
    video: Video = field(default_factory=Video)
    transcripciones: Transcripciones = field(default_factory=Transcripciones)
    correo: Correo = field(default_factory=Correo)
    busqueda: Busqueda = field(default_factory=Busqueda)
    nube: Nube = field(default_factory=Nube)
    kiosco: Kiosco = field(default_factory=Kiosco)
    privacidad: Privacidad = field(default_factory=Privacidad)
    ruta_config: Path | None = None

    # --- rutas derivadas -------------------------------------------------
    @property
    def datos(self) -> Path:
        bruto = Path(self.general.carpeta_datos).expanduser()
        if not bruto.is_absolute():
            bruto = RAIZ_PROYECTO / bruto
        return bruto

    @property
    def base_datos(self) -> Path:
        return self.datos / "reuniones.db"

    @property
    def fotos(self) -> Path:
        return self.datos / "fotos"

    @property
    def videos(self) -> Path:
        return self.datos / "videos"

    @property
    def entrada(self) -> Path:
        """Carpeta vigilada donde sueltas los .txt del telefono."""
        return self.datos / "transcripciones"

    @property
    def expedientes(self) -> Path:
        return self.datos / "expedientes"

    @property
    def adjuntos(self) -> Path:
        return self.datos / "adjuntos"

    @property
    def temporal(self) -> Path:
        return self.datos / "temporal"

    def crear_carpetas(self) -> None:
        for ruta in (self.datos, self.fotos, self.videos, self.entrada,
                     self.expedientes, self.adjuntos, self.temporal):
            ruta.mkdir(parents=True, exist_ok=True)

    # --- secretos (nunca en config.toml) ---------------------------------
    @property
    def clave_smtp(self) -> str:
        return os.environ.get("REUNIONES_SMTP_PASSWORD", "")

    @property
    def clave_gemini(self) -> str:
        return os.environ.get("GEMINI_API_KEY", "")

    @property
    def token_nube(self) -> str:
        return os.environ.get("REUNIONES_NUBE_TOKEN", "")


def _aplicar(destino: Any, datos: dict[str, Any]) -> None:
    validos = {f.name: f for f in fields(destino)}
    for clave, valor in datos.items():
        campo = validos.get(clave)
        if campo is None:
            continue
        actual = getattr(destino, clave)
        if is_dataclass(actual) and isinstance(valor, dict):
            _aplicar(actual, valor)
        else:
            setattr(destino, clave, valor)


def _cargar_env(ruta: Path) -> None:
    if not ruta.exists():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:  # sin python-dotenv leemos el archivo a mano
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            clave, _, valor = linea.partition("=")
            os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))
    else:
        load_dotenv(ruta, override=False)


def buscar_config() -> Path | None:
    """config.toml junto al proyecto, o el que indique REUNIONES_CONFIG."""
    desde_env = os.environ.get("REUNIONES_CONFIG")
    if desde_env:
        ruta = Path(desde_env).expanduser()
        return ruta if ruta.exists() else None
    candidata = RAIZ_PROYECTO / "config.toml"
    return candidata if candidata.exists() else None


def cargar(ruta: Path | None = None) -> Config:
    _cargar_env(RAIZ_PROYECTO / ".env")
    config = Config()
    ruta = ruta or buscar_config()
    if ruta and ruta.exists():
        with ruta.open("rb") as archivo:
            _aplicar(config, tomllib.load(archivo))
        config.ruta_config = ruta
    if os.environ.get("REUNIONES_DATOS"):
        config.general.carpeta_datos = os.environ["REUNIONES_DATOS"]
    return config


_cache: Config | None = None


def actual() -> Config:
    global _cache
    if _cache is None:
        _cache = cargar()
    return _cache


def recargar(ruta: Path | None = None) -> Config:
    global _cache
    _cache = cargar(ruta)
    return _cache
