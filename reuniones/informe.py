"""Generacion de PDF: minuta de una reunion y expediente completo de una persona."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from . import config, expediente, util

REEMPLAZOS = {"…": "...", "‘": "'", "’": "'", "“": '"',
              "”": '"', "–": "-", "—": "-", " ": " "}


def _limpio(texto: str) -> str:
    """fpdf con fuentes base escribe en latin-1; cambiamos lo que no cabe."""
    for origen, destino in REEMPLAZOS.items():
        texto = texto.replace(origen, destino)
    return texto.encode("latin-1", errors="replace").decode("latin-1")


def _documento(titulo: str):
    from fpdf import FPDF

    class Documento(FPDF):
        def header(self) -> None:  # noqa: N802
            self.set_font("helvetica", "B", 9)
            self.set_text_color(110)
            self.cell(0, 6, _limpio(config.actual().general.titular), align="L")
            self.cell(0, 6, _limpio(titulo), align="R", new_x="LMARGIN", new_y="NEXT")
            self.set_draw_color(200)
            self.line(self.l_margin, self.get_y() + 1, self.w - self.r_margin, self.get_y() + 1)
            self.ln(4)
            self.set_text_color(0)

        def footer(self) -> None:  # noqa: N802
            self.set_y(-14)
            self.set_font("helvetica", "", 8)
            self.set_text_color(130)
            self.cell(0, 8, f"Pagina {self.page_no()} de {{nb}}", align="C")

    pdf = Documento()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_title(_limpio(titulo))
    return pdf


def _titulo(pdf, texto: str, tamano: int = 15) -> None:
    pdf.set_font("helvetica", "B", tamano)
    pdf.multi_cell(0, 7, _limpio(texto), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)


def _dato(pdf, etiqueta: str, valor: str) -> None:
    if not valor:
        return
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(28, 5.5, _limpio(etiqueta))
    pdf.set_font("helvetica", "", 10)
    pdf.multi_cell(0, 5.5, _limpio(valor), new_x="LMARGIN", new_y="NEXT")


def _parrafos(pdf, texto: str) -> None:
    pdf.set_font("helvetica", "", 10.5)
    for linea in texto.splitlines():
        if linea.strip():
            pdf.multi_cell(0, 5.4, _limpio(linea.rstrip()), new_x="LMARGIN", new_y="NEXT")
        else:
            pdf.ln(2.5)


def _acuerdos(pdf, con: sqlite3.Connection, reunion_id: int) -> None:
    filas = expediente.acuerdos_de(con, reunion_id)
    if not filas:
        return
    pdf.ln(3)
    _titulo(pdf, "Acuerdos y compromisos", 12)
    pdf.set_font("helvetica", "", 10.5)
    for fila in filas:
        marca = "[x]" if fila["estado"] == "cerrado" else "[ ]"
        extra = []
        if fila["responsable"]:
            extra.append(f"responsable: {fila['responsable']}")
        if fila["compromiso"]:
            extra.append(f"fecha: {util.fecha_corta(fila['compromiso']) or fila['compromiso']}")
        cola = f"  ({'; '.join(extra)})" if extra else ""
        pdf.multi_cell(0, 5.4, _limpio(f"{marca} {fila['texto']}{cola}"), new_x="LMARGIN", new_y="NEXT")


def minuta_pdf(con: sqlite3.Connection, reunion_id: int, destino: Path | None = None) -> Path:
    """La minuta de una reunion, lista para enviarse por correo."""
    fila = expediente.reunion(con, reunion_id)
    if fila is None:
        raise ValueError("La reunion no existe.")
    minutas = expediente.archivos_de(con, reunion_id, "minuta")
    if not minutas:
        raise ValueError("Esta reunion todavia no tiene minuta.")
    texto = expediente.texto_de(minutas[-1])

    pdf = _documento("Minuta de reunion")
    pdf.add_page()
    _titulo(pdf, fila["asunto"] or "Minuta de reunion")
    _dato(pdf, "Fecha", util.fecha_larga(fila["inicio"]))
    _dato(pdf, "Persona", f"{fila['nombre']} <{fila['email']}>")
    if fila["categoria"]:
        _dato(pdf, "Tipo", fila["categoria"])
    pdf.ln(3)
    _parrafos(pdf, texto)
    _acuerdos(pdf, con, reunion_id)

    cfg = config.actual()
    if destino is None:
        sello = minutas[-1]["sello"] or util.sello(util.a_fecha(fila["inicio"]))
        destino = cfg.temporal / f"{sello}_minuta_{util.apodo(fila['nombre'])}.pdf"
    destino.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(destino))
    return destino


def expediente_pdf(con: sqlite3.Connection, persona_id: int, destino: Path | None = None,
                   incluir_original: bool = False) -> Path:
    """Todo el historial de una persona en un solo documento."""
    cfg = config.actual()
    persona = con.execute("SELECT * FROM personas WHERE id = ?", (persona_id,)).fetchone()
    if persona is None:
        raise ValueError("La persona no existe.")

    pdf = _documento("Expediente")
    pdf.add_page()
    if persona["foto"]:
        foto = cfg.datos / persona["foto"]
        if foto.exists():
            try:
                pdf.image(str(foto), x=pdf.w - pdf.r_margin - 32, y=pdf.get_y(), w=32)
            except Exception:
                pass
    _titulo(pdf, persona["nombre"], 17)
    _dato(pdf, "Correo", persona["email"])
    _dato(pdf, "Adscripcion", persona["adscripcion"] or "")
    _dato(pdf, "Alta", util.fecha_larga(persona["creado"]))

    historial = expediente.reuniones_de(con, persona_id, limite=500)
    _dato(pdf, "Reuniones", str(len(historial)))
    pendientes = expediente.pendientes_de(con, persona_id)
    if pendientes:
        pdf.ln(3)
        _titulo(pdf, "Pendientes abiertos", 12)
        pdf.set_font("helvetica", "", 10.5)
        for fila in pendientes:
            fecha = util.fecha_corta(fila["compromiso"]) if fila["compromiso"] else "sin fecha"
            pdf.multi_cell(0, 5.4, _limpio(f"- {fila['texto']}  ({fecha})"), new_x="LMARGIN", new_y="NEXT")

    for reunion in historial:
        pdf.add_page()
        _titulo(pdf, f"{util.fecha_corta(reunion['inicio'])} · {reunion['asunto'] or 'Sin asunto'}", 13)
        minutas = expediente.archivos_de(con, int(reunion["id"]), "minuta")
        if minutas:
            _parrafos(pdf, expediente.texto_de(minutas[-1]))
        else:
            pdf.set_font("helvetica", "I", 10)
            pdf.multi_cell(0, 5.4, "Sin minuta registrada.", new_x="LMARGIN", new_y="NEXT")
        _acuerdos(pdf, con, int(reunion["id"]))
        if incluir_original:
            originales = expediente.archivos_de(con, int(reunion["id"]), "original")
            if originales:
                pdf.ln(3)
                _titulo(pdf, "Transcripcion original", 11)
                _parrafos(pdf, expediente.texto_de(originales[-1]))

    if destino is None:
        destino = cfg.temporal / f"expediente-{persona_id:04d}-{util.apodo(persona['nombre'])}.pdf"
    destino.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(destino))
    return destino
