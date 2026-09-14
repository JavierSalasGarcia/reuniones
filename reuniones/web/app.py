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
                mantenimiento, nube, personas, turnos, util)

AQUI = Path(__file__).resolve().parent
plantillas = Jinja2Templates(directory=str(AQUI / "plantillas"))
plantillas.env.filters["fecha"] = util.fecha_corta
plantillas.env.filters["fecha_larga"] = util.fecha_larga
plantillas.env.filters["recorte"] = util.recortar_texto

vigilante: ingesta.Vigilante | None = None
latido: nube.Latido | None = None


def _reintentar_envios() -> None:
    """Lo que no salió por falta de conexión se vuelve a intentar solo."""
    with db.sesion() as con:
        correo.reintentar_pendientes(con)


@asynccontextmanager
async def ciclo(app: FastAPI):
    global vigilante, latido
    cfg = config.actual()
    cfg.crear_carpetas()
    with db.sesion() as con:
        ingesta.revisar_carpeta(con)
        mantenimiento.borrar_videos_vencidos(con)
    mantenimiento.limpiar_temporal()
    vigilante = ingesta.Vigilante()
    vigilante.iniciar()
    latido = nube.Latido(al_latir=_reintentar_envios)
    latido.iniciar()
    try:
        yield
    finally:
        if vigilante is not None:
            vigilante.detener()
        if latido is not None:
            latido.detener()


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
    guardado = nube.ultimo_estado()
    return _pagina(request, "inicio.html",
                   recientes=expediente.recientes(con, 8),
                   pendientes=pendientes,
                   compromisos=compromisos,
                   fila=turnos.resumen_fila(guardado) if guardado else None,
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
def formulario_alta(request: Request, nombre: str = "", email: str = "", asunto: str = ""):
    return _pagina(request, "alta.html",
                   datos={"nombre": nombre, "email": email, "tipo": "otro", "adscripcion": ""},
                   asunto=asunto)


@app.post("/alta")
def crear_alta(request: Request, nombre: str = Form(...), email: str = Form(...),
               adscripcion: str = Form(""), tipo: str = Form("otro"),
               consentimiento: str = Form(""), asunto: str = Form(""),
               con: sqlite3.Connection = Depends(base_datos)):
    previos = {"nombre": nombre, "email": email, "adscripcion": adscripcion, "tipo": tipo}
    if not consentimiento:
        return _pagina(request, "alta.html", error="Falta registrar el consentimiento de la persona.",
                       datos=previos, asunto=asunto)
    try:
        resultado = personas.alta_con_camara(con, nombre, email, adscripcion=adscripcion, tipo=tipo)
    except (personas.ErrorAlta, RuntimeError) as error:
        return _pagina(request, "alta.html", error=str(error), datos=previos, asunto=asunto)
    con.commit()
    if asunto.strip():
        reunion_id = expediente.crear_reunion(con, resultado["persona_id"], asunto, origen="turno")
        return RedirectResponse(f"/reunion/{reunion_id}", status_code=303)
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
                   aviso=request.query_params.get("error", ""),
                   enviado=request.query_params.get("enviado", ""),
                   pendiente=request.query_params.get("pendiente", ""),
                   por_servidor=correo.por_servidor(),
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
        resultado = correo.enviar_minuta(con, reunion_id, destinatario or None, mensaje)
    except (correo.ErrorCorreo, ValueError) as error:
        return RedirectResponse(f"/reunion/{reunion_id}?error={error}", status_code=303)
    if resultado.get("estado") == "pendiente":
        return RedirectResponse(f"/reunion/{reunion_id}?pendiente=1", status_code=303)
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


# --- fila publica y agenda ------------------------------------------------

@app.get("/turnos", response_class=HTMLResponse)
def ver_turnos(request: Request, con: sqlite3.Connection = Depends(base_datos)):
    listo, motivo = nube.configurada()
    datos, error = nube.estado_seguro() if listo else ({}, motivo)
    return _pagina(request, "turnos.html",
                   listo=listo,
                   error=error,
                   fila=turnos.resumen_fila(datos),
                   datos=datos,
                   url_publica=nube.url_publica() if listo else "",
                   url_pantalla=nube.url_publica("pantalla") if listo else "")


@app.post("/turnos/disponible")
def cambiar_disponible(disponible: str = Form(""), mensaje: str = Form("")):
    try:
        nube.disponibilidad(bool(disponible), mensaje)
    except nube.ErrorNube as error:
        return RedirectResponse(f"/turnos?error={error}", status_code=303)
    return RedirectResponse("/turnos", status_code=303)


@app.post("/turnos/{turno_id}/llamar")
def llamar_turno(turno_id: int, con: sqlite3.Connection = Depends(base_datos)):
    datos = nube.ultimo_estado()
    turno = next((t for t in datos.get("turnos", []) if int(t["id"]) == turno_id), None)
    if turno is None:
        raise HTTPException(404, "Ese turno ya no está en la fila.")
    try:
        enlace = turnos.llamar(con, turno)
    except nube.ErrorNube as error:
        return RedirectResponse(f"/turnos?error={error}", status_code=303)
    if enlace["reunion_id"]:
        return RedirectResponse(f"/reunion/{enlace['reunion_id']}", status_code=303)
    # Es su primera vez: pasamos directo al alta con sus datos ya escritos.
    from urllib.parse import urlencode
    consulta = urlencode({"nombre": turno.get("nombre", ""), "email": turno.get("email", ""),
                          "asunto": turno.get("asunto", "")})
    return RedirectResponse(f"/alta?{consulta}", status_code=303)


@app.post("/turnos/{turno_id}/cerrar")
def cerrar_turno(turno_id: int, accion: str = Form("atendido")):
    if accion not in ("atendido", "ausente", "cancelar"):
        raise HTTPException(400, "Acción desconocida.")
    try:
        turnos.cerrar(turno_id, accion)
    except nube.ErrorNube as error:
        return RedirectResponse(f"/turnos?error={error}", status_code=303)
    return RedirectResponse("/turnos", status_code=303)


@app.post("/cita/{cita_id}/resolver")
def resolver_cita(cita_id: int, accion: str = Form("aprobar"), inicio: str = Form(""),
                  motivo: str = Form(""), con: sqlite3.Connection = Depends(base_datos)):
    datos = nube.ultimo_estado()
    cita = next((c for c in datos.get("citas", []) if int(c["id"]) == cita_id), None)
    if cita is None:
        raise HTTPException(404, "Esa solicitud ya no está pendiente.")
    try:
        if accion == "aprobar":
            turnos.aprobar_cita(con, cita, inicio or None, motivo)
        else:
            turnos.rechazar_cita(cita, motivo)
    except nube.ErrorNube as error:
        return RedirectResponse(f"/turnos?error={error}", status_code=303)
    con.commit()
    return RedirectResponse("/turnos", status_code=303)


@app.get("/agenda", response_class=HTMLResponse)
def ver_agenda(request: Request):
    listo, motivo = nube.configurada()
    datos, error = nube.estado_seguro() if listo else ({}, motivo)
    semana = {dia: [] for dia in range(1, 8)}
    for tramo in datos.get("horarios", []):
        semana[int(tramo["dia"])].append(tramo)
    return _pagina(request, "agenda.html",
                   listo=listo, error=error, datos=datos, semana=semana,
                   bloqueos=datos.get("bloqueos", []),
                   url_publica=nube.url_publica() if listo else "")


@app.post("/agenda/horarios")
def guardar_horarios(request: Request, inicio: list[str] = Form([]), fin: list[str] = Form([]),
                     dia: list[str] = Form([])):
    horarios = []
    for numero, desde, hasta in zip(dia, inicio, fin):
        if desde and hasta and hasta > desde:
            horarios.append({"dia": int(numero), "inicio": desde, "fin": hasta})
    try:
        nube.publicar_horarios(horarios)
    except nube.ErrorNube as error:
        return RedirectResponse(f"/agenda?error={error}", status_code=303)
    return RedirectResponse("/agenda", status_code=303)


@app.post("/agenda/bloqueo")
def nuevo_bloqueo(fecha: str = Form(...), hora: str = Form(...), minutos: int = Form(30),
                  motivo: str = Form("Reunión")):
    inicio = util.a_fecha(f"{fecha} {hora}")
    if inicio is None:
        return RedirectResponse("/agenda?error=Fecha u hora inválida", status_code=303)
    try:
        turnos.bloquear_reunion(inicio, minutos, motivo)
    except nube.ErrorNube as error:
        return RedirectResponse(f"/agenda?error={error}", status_code=303)
    return RedirectResponse("/agenda", status_code=303)


@app.post("/agenda/bloqueo/{bloqueo_id}/borrar")
def borrar_bloqueo(bloqueo_id: int):
    try:
        nube.borrar_bloqueo(bloqueo_id)
    except nube.ErrorNube as error:
        return RedirectResponse(f"/agenda?error={error}", status_code=303)
    return RedirectResponse("/agenda", status_code=303)


@app.get("/qr.png")
def codigo_qr():
    try:
        ruta = nube.generar_qr()
    except nube.ErrorNube as error:
        raise HTTPException(503, str(error))
    return FileResponse(ruta, media_type="image/png", filename=ruta.name)


# --- minutas guardadas en el servidor ------------------------------------

@app.get("/persona/{persona_id}/servidor", response_class=HTMLResponse)
def minutas_en_servidor(request: Request, persona_id: int,
                        con: sqlite3.Connection = Depends(base_datos)):
    """Lo que hay en fingenieria.mx de esta persona, para reenviar o borrar."""
    fila = _persona(con, persona_id)
    try:
        guardadas = nube.minutas(fila["email"])
        error = ""
    except nube.ErrorNube as fallo:
        guardadas, error = [], str(fallo)
    return _pagina(request, "servidor.html", persona=fila, minutas=guardadas, error=error,
                   aviso=request.query_params.get("aviso", ""))


@app.post("/servidor/minuta/{minuta_id}/reenviar")
def reenviar_minuta(minuta_id: int, persona_id: int = Form(...), destinatario: str = Form(...),
                    mensaje: str = Form("")):
    try:
        nube.enviar_minuta(minuta_id, destinatario, mensaje)
    except nube.ErrorNube as error:
        return RedirectResponse(f"/persona/{persona_id}/servidor?aviso={error}", status_code=303)
    return RedirectResponse(f"/persona/{persona_id}/servidor?aviso=Minuta reenviada.",
                            status_code=303)


@app.post("/servidor/minuta/{minuta_id}/borrar")
def borrar_minuta_servidor(minuta_id: int, persona_id: int = Form(...)):
    try:
        nube.borrar_minuta(minuta_id)
    except nube.ErrorNube as error:
        return RedirectResponse(f"/persona/{persona_id}/servidor?aviso={error}", status_code=303)
    return RedirectResponse(f"/persona/{persona_id}/servidor?aviso=Se borró del servidor; "
                            f"la copia de tu laptop sigue intacta.", status_code=303)
