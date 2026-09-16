"""Respaldo del monitor de la entrada, servido en la red local.

Cuando se cae el internet, la Raspberry no alcanza el sitio publico y se
quedaria en blanco. Este servidor, que corre en la misma laptop pero en otro
puerto, muestra la ultima fila conocida. Solo expone la pantalla de turnos:
los expedientes siguen atados a localhost.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from .. import config, nube, turnos, util

AQUI = Path(__file__).resolve().parent
plantillas = Jinja2Templates(directory=str(AQUI / "plantillas"))

app = FastAPI(title="Pantalla de turnos")
app.mount("/estatico", StaticFiles(directory=str(AQUI / "estaticos")), name="estatico")


def _instantanea() -> dict:
    """Lo ultimo que se supo de la fila, con aviso si la nube no responde."""
    datos, error = nube.estado_seguro()
    fila = turnos.resumen_fila(datos) if datos else {"actual": None, "espera": [],
                                                     "abierta": False, "citas": [],
                                                     "bloqueos": [], "disponible": False,
                                                     "atendidos": 0, "proximo_hueco": None}
    momento = util.a_fecha(datos.get("ahora")) if datos else None
    return {
        "fila": fila,
        "nombres": _nombres_visibles(datos) if datos else True,
        "error": error,
        "mensaje": (datos.get("dependencia") or {}).get("mensaje", "") if datos else "",
        "momento": momento or datetime.now(),
        "sin_datos": not bool(datos),
    }


def _nombres_visibles(datos: dict) -> bool:
    """El monitor respeta lo que el titular eligió en el panel del sitio."""
    return bool((datos.get("dependencia") or {}).get("mostrar_nombres", True))


def _publico(turno: dict, con_nombres: bool = True) -> str:
    if not con_nombres:
        return f"Turno {turno.get('folio', '')}".strip()
    nombre = (turno.get("nombre_publico") or turno.get("nombre") or "").strip()
    return " ".join(nombre.split()[:2])


@app.get("/", response_class=HTMLResponse)
def pantalla(request: Request):
    foto = _instantanea()
    return plantillas.TemplateResponse(request, "pantalla.html", {
        "fila": foto["fila"],
        "nombres": foto["nombres"],
        "error": foto["error"],
        "mensaje": foto["mensaje"],
        "hora": f"{foto['momento']:%H:%M}",
        "url_publica": nube.url_publica() if nube.configurada()[0] else "",
        "titular": config.actual().general.titular,
    })


@app.get("/estado.json")
def estado_json():
    """Mismo formato que el del sitio publico, para que el guion no cambie."""
    foto = _instantanea()
    fila = foto["fila"]
    nombres = foto["nombres"]
    return JSONResponse({
        "ahora": f"{foto['momento']:%H:%M}",
        "disponible": bool(fila.get("disponible")),
        "abierta": bool(fila.get("abierta")),
        "mensaje": foto["mensaje"] or ("Sin conexión con el sitio; se muestra lo último conocido."
                                       if foto["error"] else ""),
        "local": True,
        "desfasado": bool(foto["error"]),
        "nombres": nombres,
        "actual": {
            "folio": fila["actual"]["folio"],
            "nombre": _publico(fila["actual"]) if nombres else "Pasa por favor",
        } if fila.get("actual") else None,
        "siguientes": [{"folio": t["folio"], "nombre": _publico(t) if nombres else "",
                        "hora": (t.get("estimado") or "")[11:16] or None}
                       for t in fila.get("espera", [])[:6]],
    })


@app.get("/qr.png")
def codigo_qr():
    try:
        ruta = nube.generar_qr()
    except nube.ErrorNube:
        return JSONResponse({"error": "sin código QR"}, status_code=503)
    return FileResponse(ruta, media_type="image/png")


def servir_en_hilo() -> None:
    """Levanta el respaldo en su propio hilo, junto al sitio local."""
    import threading

    import uvicorn

    cfg = config.actual().kiosco
    if not cfg.habilitado:
        return
    servidor = uvicorn.Server(uvicorn.Config(app, host=cfg.escuchar, port=cfg.puerto,
                                             log_level="warning"))
    threading.Thread(target=servidor.run, name="pantalla-respaldo", daemon=True).start()
