"""Cliente de la parte publica: la laptop habla con el sitio en el hosting.

La laptop siempre inicia la conexion hacia afuera, asi que no hay que abrir
puertos ni exponer este equipo. Por aqui solo viajan turnos, citas y
disponibilidad; los expedientes y las minutas se quedan en casa.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from . import config, util


class ErrorNube(Exception):
    """Falla de configuracion o de comunicacion con el sitio publico."""


class ErrorEnvio(ErrorNube):
    """El servidor recibio la minuta pero el correo no salio."""


@dataclass
class Cache:
    """Ultimo estado conocido, para no golpear el hosting en cada clic."""

    datos: dict[str, Any] = field(default_factory=dict)
    momento: float = 0.0
    error: str = ""


_cache = Cache()
_candado = threading.Lock()


def configurada() -> tuple[bool, str]:
    cfg = config.actual()
    if not cfg.nube.url:
        return False, "Falta la dirección del sitio público en config.toml ([nube] url)."
    if not cfg.nube.dependencia:
        return False, "Falta la clave de la dependencia en config.toml ([nube] dependencia)."
    if not cfg.token_nube:
        return False, "Falta REUNIONES_NUBE_TOKEN en el archivo .env."
    return True, ""


def _cliente():
    try:
        import httpx
    except ImportError as exc:  # pragma: no cover - depende del equipo
        raise ErrorNube("Falta el paquete httpx: pip install httpx") from exc
    cfg = config.actual()
    return httpx.Client(
        base_url=cfg.nube.url.rstrip("/"),
        headers={"Authorization": f"Bearer {cfg.token_nube}"},
        timeout=cfg.nube.espera_segundos,
    )


def _llamar(accion: str, datos: dict | None = None, metodo: str = "GET") -> dict:
    listo, motivo = configurada()
    if not listo:
        raise ErrorNube(motivo)
    cfg = config.actual()
    parametros = {"d": cfg.nube.dependencia, "accion": accion}
    try:
        with _cliente() as cliente:
            if metodo == "GET":
                respuesta = cliente.get("/api", params=parametros)
            else:
                respuesta = cliente.post("/api", params=parametros, json=datos or {})
    except Exception as error:
        raise ErrorNube(f"No se pudo hablar con el sitio público: {error}") from error

    if respuesta.status_code == 401:
        raise ErrorNube("El sitio rechazó el token. Regenéralo en el panel de administración.")
    if respuesta.status_code >= 400:
        raise ErrorNube(f"El sitio respondió {respuesta.status_code}: {respuesta.text[:200]}")
    try:
        return respuesta.json()
    except ValueError as error:
        raise ErrorNube("El sitio no devolvió datos legibles.") from error


# --- lectura --------------------------------------------------------------

def estado(forzar: bool = False) -> dict:
    """Turnos, citas y bloqueos del dia, con las horas ya calculadas."""
    cfg = config.actual()
    with _candado:
        fresco = (time.monotonic() - _cache.momento) < cfg.nube.refresco_segundos
        if fresco and not forzar and _cache.datos:
            return _cache.datos
    datos = _llamar("estado")
    with _candado:
        _cache.datos = datos
        _cache.momento = time.monotonic()
        _cache.error = ""
    return datos


def ultimo_estado() -> dict:
    """Lo ultimo que se supo, sin salir a la red."""
    with _candado:
        return dict(_cache.datos)


def estado_seguro() -> tuple[dict, str]:
    """Estado y, si fallo, el motivo; para que la interfaz no se caiga."""
    try:
        return estado(), ""
    except ErrorNube as error:
        with _candado:
            _cache.error = str(error)
            previo = dict(_cache.datos)
        return previo, str(error)


# --- escritura ------------------------------------------------------------

def _tras_escribir(resultado: dict) -> dict:
    with _candado:
        _cache.momento = 0.0     # la proxima lectura trae datos frescos
    return resultado


def disponibilidad(disponible: bool, mensaje: str = "") -> dict:
    return _tras_escribir(_llamar("disponible", {"disponible": disponible, "mensaje": mensaje}, "POST"))


def publicar_horarios(horarios: list[dict], excepciones: list[dict] | None = None) -> dict:
    carga: dict[str, Any] = {"horarios": horarios}
    if excepciones is not None:
        carga["excepciones"] = excepciones
    return _tras_escribir(_llamar("horarios", carga, "POST"))


def crear_bloqueo(inicio: datetime, fin: datetime, motivo: str = "Reunión") -> dict:
    return _tras_escribir(_llamar("bloqueo", {
        "inicio": inicio.strftime("%Y-%m-%d %H:%M:%S"),
        "fin": fin.strftime("%Y-%m-%d %H:%M:%S"),
        "motivo": motivo,
    }, "POST"))


def borrar_bloqueo(bloqueo_id: int) -> dict:
    return _tras_escribir(_llamar("bloqueo", {"eliminar": bloqueo_id}, "POST"))


def turno(turno_id: int, accion: str, nombre_publico: str | None = None) -> dict:
    carga: dict[str, Any] = {"id": turno_id, "accion": accion}
    if nombre_publico is not None:
        carga["nombre_publico"] = nombre_publico
    return _tras_escribir(_llamar("turno", carga, "POST"))


def cita(cita_id: int, accion: str, inicio: str | None = None, motivo: str = "") -> dict:
    carga: dict[str, Any] = {"id": cita_id, "accion": accion, "motivo": motivo}
    if inicio:
        carga["inicio"] = inicio
    return _tras_escribir(_llamar("cita", carga, "POST"))


def descargar_adjunto(adjunto_id: int, destino: Path) -> Path:
    listo, motivo = configurada()
    if not listo:
        raise ErrorNube(motivo)
    cfg = config.actual()
    try:
        with _cliente() as cliente:
            respuesta = cliente.get("/api", params={
                "d": cfg.nube.dependencia, "accion": "adjunto", "id": adjunto_id})
            respuesta.raise_for_status()
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_bytes(respuesta.content)
    except Exception as error:
        raise ErrorNube(f"No se pudo descargar el archivo: {error}") from error
    return destino


# --- direcciones publicas -------------------------------------------------

def url_publica(seccion: str = "") -> str:
    cfg = config.actual()
    base = f"{cfg.nube.url.rstrip('/')}/{cfg.nube.dependencia}"
    return f"{base}/{seccion.lstrip('/')}" if seccion else base


def generar_qr(destino: Path | None = None) -> Path:
    """Codigo QR de la pagina publica, para imprimirlo y pegarlo en la puerta."""
    try:
        import qrcode
    except ImportError as exc:
        raise ErrorNube("Falta el paquete qrcode: pip install qrcode[pil]") from exc
    cfg = config.actual()
    destino = destino or (cfg.datos / f"qr-{cfg.nube.dependencia or 'citas'}.png")
    destino.parent.mkdir(parents=True, exist_ok=True)
    imagen = qrcode.make(url_publica())
    imagen.save(destino)
    return destino


# --- sincronizacion de fondo ---------------------------------------------

class Latido:
    """Consulta el sitio cada tanto para que los avisos por correo salgan solos.

    `al_latir` permite colgar tareas que dependen de tener conexion, como
    reintentar los envios de minuta que quedaron pendientes.
    """

    def __init__(self, segundos: int | None = None,
                 al_latir: Callable[[], None] | None = None) -> None:
        self.segundos = segundos or config.actual().nube.latido_segundos
        self.al_latir = al_latir
        self._parar = threading.Event()
        self._hilo: threading.Thread | None = None

    def iniciar(self) -> None:
        listo, _ = configurada()
        if not listo or self._hilo is not None:
            return

        def girar() -> None:
            while not self._parar.wait(self.segundos):
                try:
                    estado(forzar=True)
                except ErrorNube:
                    continue   # sin internet, el panel sigue con lo ultimo conocido
                if self.al_latir is not None:
                    try:
                        self.al_latir()
                    except Exception:
                        pass   # una tarea colgada no debe matar el latido

        self._hilo = threading.Thread(target=girar, name="latido-nube", daemon=True)
        self._hilo.start()

    def detener(self) -> None:
        self._parar.set()
        if self._hilo is not None:
            self._hilo.join(timeout=3)
            self._hilo = None


# --- ayudas de presentacion ----------------------------------------------

def hora(texto: str | None) -> str:
    momento = util.a_fecha(texto)
    return f"{momento:%H:%M}" if momento else ""


def turnos_por_estado(datos: dict, estado_buscado: str) -> list[dict]:
    return [t for t in datos.get("turnos", []) if t.get("estado") == estado_buscado]


# --- minutas en el servidor ----------------------------------------------
#
# El correo institucional rechaza lo que sale de la laptop, asi que la minuta
# en PDF sube al servidor y desde alli se envia. Solo sube la minuta: la
# transcripcion original nunca sale de este equipo.

def subir_minuta(pdf: Path, persona: str, email: str, asunto: str = "",
                 fecha: datetime | str | None = None, reunion_local: int | None = None) -> dict:
    listo, motivo = configurada()
    if not listo:
        raise ErrorNube(motivo)
    if not pdf.is_file():
        raise ErrorNube(f"No encuentro el archivo {pdf}.")
    cfg = config.actual()
    if isinstance(fecha, datetime):
        fecha = fecha.strftime("%Y-%m-%d %H:%M:%S")

    datos = {"persona": persona, "email": email, "asunto": asunto,
             "fecha": fecha or "", "reunion_local": str(reunion_local or "")}
    try:
        with _cliente() as cliente:
            respuesta = cliente.post(
                "/api",
                params={"d": cfg.nube.dependencia, "accion": "minuta"},
                data=datos,
                files={"archivo": (pdf.name, pdf.read_bytes(), "application/pdf")},
            )
    except Exception as error:
        raise ErrorNube(f"No se pudo subir la minuta: {error}") from error

    if respuesta.status_code == 401:
        raise ErrorNube("El sitio rechazó el token. Regenéralo en el panel de administración.")
    if respuesta.status_code >= 400:
        raise ErrorNube(f"El servidor no aceptó la minuta: {respuesta.text[:200]}")
    return respuesta.json().get("minuta", {})


def enviar_minuta(minuta_id: int, destinatario: str, mensaje: str = "") -> dict:
    """Pide al servidor que mande la minuta que ya tiene guardada.

    Distingue dos fracasos distintos: no alcanzar el servidor, que se puede
    reintentar, y que el servidor de correo rechace el mensaje, que no.
    """
    listo, motivo = configurada()
    if not listo:
        raise ErrorNube(motivo)
    cfg = config.actual()
    try:
        with _cliente() as cliente:
            respuesta = cliente.post(
                "/api",
                params={"d": cfg.nube.dependencia, "accion": "minuta_enviar"},
                json={"id": minuta_id, "destinatario": destinatario, "mensaje": mensaje},
            )
    except Exception as error:
        raise ErrorNube(f"No se pudo hablar con el servidor: {error}") from error

    if respuesta.status_code == 502:
        detalle = ""
        try:
            detalle = respuesta.json().get("error", "")
        except ValueError:
            pass
        raise ErrorEnvio(detalle or "El servidor de correo no aceptó el mensaje.")
    if respuesta.status_code == 401:
        raise ErrorNube("El sitio rechazó el token. Regenéralo en el panel de administración.")
    if respuesta.status_code >= 400:
        raise ErrorNube(f"El servidor respondió {respuesta.status_code}: {respuesta.text[:200]}")
    _tras_escribir({})
    return respuesta.json()


def minutas(email: str = "") -> list[dict]:
    listo, motivo = configurada()
    if not listo:
        raise ErrorNube(motivo)
    cfg = config.actual()
    parametros = {"d": cfg.nube.dependencia, "accion": "minutas"}
    if email:
        parametros["email"] = email
    try:
        with _cliente() as cliente:
            respuesta = cliente.get("/api", params=parametros)
            respuesta.raise_for_status()
    except Exception as error:
        raise ErrorNube(f"No se pudo consultar el expediente del servidor: {error}") from error
    return respuesta.json().get("minutas", [])


def borrar_minuta(minuta_id: int) -> dict:
    return _llamar("minuta_borrar", {"id": minuta_id}, "POST")
