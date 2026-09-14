"""Sitio local: expedientes, identificacion, minutas y busqueda."""

from __future__ import annotations

import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .. import (busqueda, config, correo, db, expediente, informe, ingesta,
                mantenimiento, personas, util)

AQUI = Path(__file__).resolve().parent
plantillas = Jinja2Templates(directory=str(AQUI / "plantillas"))
plantillas.env.filters["fecha"] = util.fecha_corta
plantillas.env.filters["fecha_larga"] = util.fecha_larga
plantillas.env.filters["recorte"] = util.recortar_texto

vigilante: ingesta.Vigilante | None = None


@asynccontextmanager
async def ciclo(app: FastAPI):
    global vigilante
    cfg = config.actual()
    cfg.crear_carpetas()
    with db.sesion() as con:
        ingesta.revisar_carpeta(con)
        mantenimiento.borrar_videos_vencidos(con)
    mantenimiento.limpiar_temporal()
    vigilante = ingesta.Vigilante()
    vigilante.iniciar()
    try:
        yield
    finally:
        if vigilante is not None:
            vigilante.detener()


app = FastAPI(title="Expedientes de reuniones", lifespan=ciclo)
app.mount("/estaticos", StaticFiles(directory=str(AQUI / "estaticos")), name="estaticos")


def base_datos():
    con = db.preparar()
    try:
        yield con
        con.commit()
    finally:
        con.close()


def _pagina(request: Request, plantilla: str, **datos: Any) -> HTMLResponse:
    datos.setdefault("cfg", config.actual())
    datos.setdefault("ahora", datetime.now())
    return plantillas.TemplateResponse(request, plantilla, datos)


def _persona(con: sqlite3.Connection, persona_id: int) -> sqlite3.Row:
    fila = con.execute("SELECT * FROM personas WHERE id = ?", (persona_id,)).fetchone()
    if fila is None:
        raise HTTPException(404, "No existe esa persona.")
    return fila


# --- inicio ---------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def inicio(request: Request, con: sqlite3.Connection = Depends(base_datos)):
    pendientes = con.execute(
        "SELECT COUNT(*) AS n FROM bandeja WHERE resuelto IS NULL"
    ).fetchone()["n"]
    compromisos = con.execute(
        "SELECT c.*, r.persona_id, p.nombre FROM acuerdos c "
        "JOIN reuniones r ON r.id = c.reunion_id JOIN personas p ON p.id = r.persona_id "
        "WHERE c.estado = 'abierto' ORDER BY c.compromiso IS NULL, c.compromiso LIMIT 8"
    ).fetchall()
    return _pagina(request, "inicio.html",
                   recientes=expediente.recientes(con, 8),
                   pendientes=pendientes,
                   compromisos=compromisos,
                   resumen=mantenimiento.resumen(con))


@app.post("/identificar")
def identificar(con: sqlite3.Connection = Depends(base_datos)):
    """Abre la camara dos segundos. No se guarda ninguna imagen."""
    try:
        lectura = personas.identificar_con_camara(con)
    except RuntimeError as error:
        return JSONResponse({"estado": "error", "mensaje": str(error)}, status_code=503)
    cfg = config.actual()
    salida = {
        "estado": lectura.resultado.estado,
        "calidad": lectura.calidad,
        "cuadros": lectura.cuadros_con_rostro,
        "candidatos": [
            {"id": c.persona_id, "nombre": c.nombre, "email": c.email,
             "foto": f"/archivo/{c.foto}" if c.foto else None,
             "similitud": c.similitud,
             "porcentaje": int(round(c.similitud * 100))}
            for c in lectura.resultado.candidatos
        ],
        "umbral_alto": cfg.reconocimiento.umbral_alto,
    }
    if lectura.resultado.estado == "identificado" and lectura.vector is not None:
        persona_id = lectura.resultado.persona_id
        if persona_id and lectura.calidad > 0.6:
            personas.reforzar(con, persona_id, lectura.vector, lectura.calidad)
        salida["ir_a"] = f"/persona/{persona_id}"
    return JSONResponse(salida)


# --- personas -------------------------------------------------------------

@app.get("/personas", response_class=HTMLResponse)
def lista_personas(request: Request, q: str = "", con: sqlite3.Connection = Depends(base_datos)):
    return _pagina(request, "personas.html", filas=personas.buscar(con, q), q=q)


@app.get("/alta", response_class=HTMLResponse)
def formulario_alta(request: Request):
    return _pagina(request, "alta.html")


@app.post("/alta")
def crear_alta(request: Request, nombre: str = Form(...), email: str = Form(...),
               adscripcion: str = Form(""), tipo: str = Form("otro"),
               consentimiento: str = Form(""),
               con: sqlite3.Connection = Depends(base_datos)):
    if not consentimiento:
        return _pagina(request, "alta.html", error="Falta registrar el consentimiento de la persona.",
                       datos={"nombre": nombre, "email": email, "adscripcion": adscripcion, "tipo": tipo})
    try:
        resultado = personas.alta_con_camara(con, nombre, email, adscripcion=adscripcion, tipo=tipo)
    except (personas.ErrorAlta, RuntimeError) as error:
        return _pagina(request, "alta.html", error=str(error),
                       datos={"nombre": nombre, "email": email, "adscripcion": adscripcion, "tipo": tipo})
    con.commit()
    return RedirectResponse(f"/persona/{resultado['persona_id']}?nuevo=1", status_code=303)


@app.get("/persona/{persona_id}", response_class=HTMLResponse)
def ver_persona(request: Request, persona_id: int, nuevo: int = 0,
                con: sqlite3.Connection = Depends(base_datos)):
    fila = _persona(con, persona_id)
    datos = expediente.briefing(con, persona_id)
    return _pagina(request, "persona.html",
                   persona=fila,
                   nuevo=bool(nuevo),
                   briefing=datos,
                   lineas=expediente.resumen_en_lineas(datos),
                   historial=expediente.reuniones_de(con, persona_id),
                   alternativas=[r for r in (fila["alternativas"] or "").split("|") if r])


@app.post("/persona/{persona_id}/editar")
def editar_persona(persona_id: int, nombre: str = Form(...), email: str = Form(...),
                   adscripcion: str = Form(""), tipo: str = Form("otro"),
                   notas: str = Form(""), reservado: str = Form(""),
                   con: sqlite3.Connection = Depends(base_datos)):
    _persona(con, persona_id)
    con.execute(
        "UPDATE personas SET nombre = ?, email = ?, adscripcion = ?, tipo = ?, notas = ?, "
        "reservado = ?, actualizado = ? WHERE id = ?",
        (" ".join(nombre.split()), personas.limpiar_email(email), adscripcion, tipo, notas,
         1 if reservado else 0, db.ahora(), persona_id),
    )
    return RedirectResponse(f"/persona/{persona_id}", status_code=303)


@app.post("/persona/{persona_id}/foto")
def cambiar_foto(persona_id: int, posicion: int = Form(1),
                 con: sqlite3.Connection = Depends(base_datos)):
    try:
        personas.reprocesar_foto(con, persona_id, posicion)
    except (personas.ErrorAlta, RuntimeError) as error:
        raise HTTPException(400, str(error))
    return RedirectResponse(f"/persona/{persona_id}", status_code=303)


@app.get("/persona/{persona_id}/expediente.pdf")
def pdf_expediente(persona_id: int, original: int = 0,
                   con: sqlite3.Connection = Depends(base_datos)):
    ruta = informe.expediente_pdf(con, persona_id, incluir_original=bool(original))
    return FileResponse(ruta, media_type="application/pdf", filename=ruta.name)


# --- reuniones ------------------------------------------------------------

@app.post("/persona/{persona_id}/reunion")
def nueva_reunion(persona_id: int, asunto: str = Form(""), categoria: str = Form(""),
                  con: sqlite3.Connection = Depends(base_datos)):
    _persona(con, persona_id)
    reunion_id = expediente.crear_reunion(con, persona_id, asunto, categoria=categoria)
    return RedirectResponse(f"/reunion/{reunion_id}", status_code=303)


@app.get("/reunion/{reunion_id}", response_class=HTMLResponse)
def ver_reunion(request: Request, reunion_id: int, con: sqlite3.Connection = Depends(base_datos)):
    fila = expediente.reunion(con, reunion_id)
    if fila is None:
        raise HTTPException(404, "No existe esa reunion.")
    minutas = expediente.archivos_de(con, reunion_id, "minuta")
    originales = expediente.archivos_de(con, reunion_id, "original")
    listo_correo, motivo_correo = correo.configurado()
    return _pagina(request, "reunion.html",
                   reunion=fila,
                   minuta=expediente.texto_de(minutas[-1]) if minutas else "",
                   original=expediente.texto_de(originales[-1]) if originales else "",
                   archivos=expediente.archivos_de(con, reunion_id),
                   acuerdos=expediente.acuerdos_de(con, reunion_id),
                   envios=correo.envios_de(con, reunion_id),
                   correo_listo=listo_correo,
                   correo_motivo=motivo_correo)


@app.post("/reunion/{reunion_id}/editar")
def editar_reunion(reunion_id: int, asunto: str = Form(""), categoria: str = Form(""),
                   notas: str = Form(""), con: sqlite3.Connection = Depends(base_datos)):
    expediente.actualizar(con, reunion_id, asunto=asunto, categoria=categoria, notas=notas)
    return RedirectResponse(f"/reunion/{reunion_id}", status_code=303)


@app.post("/reunion/{reunion_id}/acuerdo")
def nuevo_acuerdo(reunion_id: int, texto: str = Form(...), responsable: str = Form(""),
                  compromiso: str = Form(""), con: sqlite3.Connection = Depends(base_datos)):
    if texto.strip():
        expediente.agregar_acuerdo(con, reunion_id, texto, responsable, compromiso or None)
    return RedirectResponse(f"/reunion/{reunion_id}", status_code=303)


@app.post("/acuerdo/{acuerdo_id}/estado")
def cambiar_acuerdo(acuerdo_id: int, reunion_id: int = Form(...), cerrar: str = Form(""),
                    con: sqlite3.Connection = Depends(base_datos)):
    expediente.cerrar_acuerdo(con, acuerdo_id, bool(cerrar))
    return RedirectResponse(f"/reunion/{reunion_id}", status_code=303)


@app.post("/reunion/{reunion_id}/adjunto")
async def subir_adjunto(reunion_id: int, archivo: UploadFile,
                        clase: str = Form("adjunto"),
                        con: sqlite3.Connection = Depends(base_datos)):
    fila = expediente.reunion(con, reunion_id)
    if fila is None:
        raise HTTPException(404, "No existe esa reunion.")
    cfg = config.actual()
    cfg.crear_carpetas()
    temporal = util.ruta_unica(cfg.temporal / (archivo.filename or "archivo.txt"))
    temporal.write_bytes(await archivo.read())
    analisis = ingesta.analizar_nombre(temporal.name)
    sello = analisis.sello if analisis else None
    expediente.adjuntar(con, reunion_id, temporal, clase if clase in expediente.CLASES else "adjunto", sello)
    con.commit()
    return RedirectResponse(f"/reunion/{reunion_id}", status_code=303)


@app.get("/reunion/{reunion_id}/minuta.pdf")
def pdf_minuta(reunion_id: int, con: sqlite3.Connection = Depends(base_datos)):
    try:
        ruta = informe.minuta_pdf(con, reunion_id)
    except ValueError as error:
        raise HTTPException(400, str(error))
    return FileResponse(ruta, media_type="application/pdf", filename=ruta.name)


@app.post("/reunion/{reunion_id}/enviar")
def enviar(reunion_id: int, destinatario: str = Form(""), mensaje: str = Form(""),
           con: sqlite3.Connection = Depends(base_datos)):
    try:
        correo.enviar_minuta(con, reunion_id, destinatario or None, mensaje)
    except (correo.ErrorCorreo, ValueError) as error:
        return RedirectResponse(f"/reunion/{reunion_id}?error={error}", status_code=303)
    return RedirectResponse(f"/reunion/{reunion_id}?enviado=1", status_code=303)


# --- bandeja --------------------------------------------------------------

@app.get("/bandeja", response_class=HTMLResponse)
def ver_bandeja(request: Request, con: sqlite3.Connection = Depends(base_datos)):
    filas = con.execute(
        "SELECT * FROM bandeja WHERE resuelto IS NULL ORDER BY detectado DESC"
    ).fetchall()
    opciones = []
    for fila in filas:
        momento = util.de_sello(fila["sello"]) if fila["sello"] else None
        opciones.append({
            "pendiente": fila,
            "vista": util.recortar_texto(util.leer_texto(Path(fila["ruta"])), 300)
            if Path(fila["ruta"]).exists() else "(el archivo ya no esta en la carpeta)",
            "candidatas": ingesta.candidatas(con, momento) if momento else [],
        })
    return _pagina(request, "bandeja.html", pendientes=opciones,
                   carpeta=str(config.actual().entrada))


@app.post("/bandeja/{bandeja_id}/asignar")
def asignar_bandeja(bandeja_id: int, reunion_id: int = Form(...),
                    con: sqlite3.Connection = Depends(base_datos)):
    ingesta.asignar_manual(con, bandeja_id, reunion_id)
    con.commit()
    return RedirectResponse("/bandeja", status_code=303)


@app.post("/bandeja/{bandeja_id}/descartar")
def descartar_bandeja(bandeja_id: int, con: sqlite3.Connection = Depends(base_datos)):
    con.execute("UPDATE bandeja SET resuelto = ? WHERE id = ?", (db.ahora(), bandeja_id))
    return RedirectResponse("/bandeja", status_code=303)


@app.post("/bandeja/revisar")
def revisar_bandeja(con: sqlite3.Connection = Depends(base_datos)):
    ingesta.revisar_carpeta(con)
    return RedirectResponse("/bandeja", status_code=303)


# --- busqueda -------------------------------------------------------------

@app.get("/buscar", response_class=HTMLResponse)
def buscar_texto(request: Request, q: str = Query(""), redactar: int = 0,
                 con: sqlite3.Connection = Depends(base_datos)):
    hallazgos = busqueda.buscar(con, q) if q else []
    respuesta = ""
    aviso = ""
    if q and redactar:
        try:
            respuesta = busqueda.responder(con, q, hallazgos)
        except RuntimeError as error:
            aviso = str(error)
    return _pagina(request, "buscar.html", q=q, hallazgos=hallazgos,
                   respuesta=respuesta, aviso=aviso, hay_gemini=busqueda.hay_gemini())


# --- archivos y ajustes ---------------------------------------------------

@app.get("/archivo/{ruta:path}")
def servir_archivo(ruta: str):
    cfg = config.actual()
    destino = (cfg.datos / ruta).resolve()
    if not str(destino).startswith(str(cfg.datos.resolve())) or not destino.is_file():
        raise HTTPException(404, "Archivo no encontrado.")
    return FileResponse(destino)


@app.get("/ajustes", response_class=HTMLResponse)
def ajustes(request: Request, con: sqlite3.Connection = Depends(base_datos)):
    listo, motivo = correo.configurado()
    return _pagina(request, "ajustes.html", resumen=mantenimiento.resumen(con),
                   correo_listo=listo, correo_motivo=motivo,
                   hay_gemini=busqueda.hay_gemini(),
                   bitacora=con.execute(
                       "SELECT * FROM bitacora ORDER BY id DESC LIMIT 30").fetchall())


@app.post("/ajustes/probar-correo")
def probar_correo():
    try:
        mensaje = correo.probar()
    except correo.ErrorCorreo as error:
        return JSONResponse({"ok": False, "mensaje": str(error)})
    return JSONResponse({"ok": True, "mensaje": mensaje})


@app.post("/ajustes/reindexar")
def reindexar(con: sqlite3.Connection = Depends(base_datos)):
    total = busqueda.reindexar(con)
    return JSONResponse({"ok": True, "fragmentos": total})


@app.post("/ajustes/limpiar-videos")
def limpiar_videos(con: sqlite3.Connection = Depends(base_datos)):
    borrados = mantenimiento.borrar_videos_vencidos(con)
    return JSONResponse({"ok": True, "borrados": len(borrados)})
