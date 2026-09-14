"""Utilerias compartidas: nombres de archivo, fechas y texto."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import datetime
from pathlib import Path

FORMATO_SELLO = "%Y%m%d_%H%M"
MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre")


def sin_acentos(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


def apodo(texto: str, largo: int = 40) -> str:
    """Nombre seguro para carpetas y archivos."""
    limpio = re.sub(r"[^a-zA-Z0-9]+", "-", sin_acentos(texto)).strip("-").lower()
    return (limpio[:largo].strip("-") or "sin-nombre")


def sello(momento: datetime) -> str:
    return momento.strftime(FORMATO_SELLO)


def de_sello(texto: str) -> datetime | None:
    try:
        return datetime.strptime(texto, FORMATO_SELLO)
    except ValueError:
        return None


def a_fecha(valor: str | datetime | None) -> datetime | None:
    if valor is None or isinstance(valor, datetime):
        return valor
    texto = valor.strip().replace("T", " ")
    for formato in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(texto, formato)
        except ValueError:
            continue
    return None


def fecha_larga(valor: str | datetime | None) -> str:
    momento = a_fecha(valor)
    if momento is None:
        return ""
    return f"{momento.day} de {MESES[momento.month - 1]} de {momento.year}, {momento:%H:%M}"


def fecha_corta(valor: str | datetime | None) -> str:
    momento = a_fecha(valor)
    return f"{momento:%d/%m/%Y %H:%M}" if momento else ""


def huella(ruta: Path) -> str:
    resumen = hashlib.sha256()
    with ruta.open("rb") as archivo:
        for bloque in iter(lambda: archivo.read(65536), b""):
            resumen.update(bloque)
    return resumen.hexdigest()


def ruta_unica(destino: Path) -> Path:
    """Evita sobrescribir: agrega -2, -3, ... si el nombre ya existe."""
    if not destino.exists():
        return destino
    contador = 2
    while True:
        candidata = destino.with_name(f"{destino.stem}-{contador}{destino.suffix}")
        if not candidata.exists():
            return candidata
        contador += 1


def recortar_texto(texto: str, largo: int = 160) -> str:
    limpio = " ".join(texto.split())
    return limpio if len(limpio) <= largo else limpio[: largo - 1].rstrip() + "…"


def leer_texto(ruta: Path) -> str:
    """Los .txt del telefono pueden venir en UTF-8 o en la pagina de codigos de Windows."""
    datos = ruta.read_bytes()
    for codificacion in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return datos.decode(codificacion)
        except UnicodeDecodeError:
            continue
    return datos.decode("utf-8", errors="replace")
