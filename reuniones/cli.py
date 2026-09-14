"""Comandos cortos para usar el sistema sin soltar la conversacion.

    reunion                      identifica a quien acaba de entrar
    reunion nueva "Nombre" correo    da de alta a alguien por primera vez
    reunion servidor             levanta el sitio local
"""

from __future__ import annotations

import sys
import webbrowser

import typer

from . import busqueda, config, correo, db, expediente, ingesta, mantenimiento, personas, util

app = typer.Typer(add_completion=False, help="Expedientes de reuniones de la subdireccion.")


def _url(ruta: str = "") -> str:
    return f"http://localhost:{config.actual().general.puerto_web}{ruta}"


def _abrir(ruta: str) -> None:
    try:
        webbrowser.open(_url(ruta))
    except Exception:
        typer.echo(f"Abre en tu navegador: {_url(ruta)}")


@app.callback(invoke_without_command=True)
def principal(ctx: typer.Context) -> None:
    """Sin argumentos, identifica a la persona frente a la camara."""
    if ctx.invoked_subcommand is None:
        identificar()


@app.command()
def identificar() -> None:
    """Dos segundos de camara; no se guarda ninguna imagen."""
    config.actual().crear_carpetas()
    with db.sesion() as con:
        try:
            lectura = personas.identificar_con_camara(con)
        except RuntimeError as error:
            typer.secho(str(error), fg=typer.colors.RED)
            raise typer.Exit(1)

        if lectura.resultado.estado == "identificado":
            candidato = lectura.resultado.candidatos[0]
            typer.secho(f"{candidato.nombre}  ({candidato.similitud:.0%})", fg=typer.colors.GREEN, bold=True)
            for linea in expediente.resumen_en_lineas(expediente.briefing(con, candidato.persona_id)):
                typer.echo(f"  {linea}")
            if lectura.vector is not None and lectura.calidad > 0.6:
                personas.reforzar(con, candidato.persona_id, lectura.vector, lectura.calidad)
            _abrir(f"/persona/{candidato.persona_id}")
        elif lectura.resultado.candidatos:
            typer.secho("No estoy seguro. Candidatos:", fg=typer.colors.YELLOW)
            for candidato in lectura.resultado.candidatos:
                typer.echo(f"  {candidato.similitud:.0%}  {candidato.nombre} <{candidato.email}>")
            _abrir("/")
        else:
            typer.secho("No reconozco a esta persona.", fg=typer.colors.YELLOW)
            typer.echo("  Dala de alta con:  reunion nueva \"Nombre Apellido\" correo@" +
                       config.actual().general.dominio_institucional)


@app.command()
def nueva(nombre: str, email: str,
          adscripcion: str = typer.Option("", "--adscripcion", "-a"),
          tipo: str = typer.Option("otro", "--tipo", "-t"),
          asunto: str = typer.Option("", "--asunto", help="Crea la reunion de hoy con este asunto.")) -> None:
    """Alta de una persona: graba el video breve y extrae la fotografia."""
    cfg = config.actual()
    cfg.crear_carpetas()
    if not personas.es_institucional(email):
        typer.secho(f"Aviso: el correo no es del dominio {cfg.general.dominio_institucional}.",
                    fg=typer.colors.YELLOW)
    typer.echo(f"Grabando {cfg.camara.segundos_alta} segundos. Pide gesto neutro y mirada al frente…")
    with db.sesion() as con:
        try:
            resultado = personas.alta_con_camara(con, nombre, email, adscripcion=adscripcion, tipo=tipo)
        except (personas.ErrorAlta, RuntimeError) as error:
            typer.secho(str(error), fg=typer.colors.RED)
            raise typer.Exit(1)
        typer.secho(f"Expediente {resultado['persona_id']} creado.", fg=typer.colors.GREEN, bold=True)
        typer.echo(f"  Foto: {resultado['foto']}  (calidad {resultado['puntaje']:.2f})")
        typer.echo("  " + ", ".join(f"{k} {v}" for k, v in resultado["partes"].items()))
        if resultado["video_expira"]:
            typer.echo(f"  El video del alta se borra solo el {resultado['video_expira']}.")
        if asunto:
            reunion_id = expediente.crear_reunion(con, resultado["persona_id"], asunto)
            _abrir(f"/reunion/{reunion_id}")
        else:
            _abrir(f"/persona/{resultado['persona_id']}?nuevo=1")


@app.command()
def servidor(puerto: int = typer.Option(0, "--puerto", "-p"),
             abrir: bool = typer.Option(True, "--abrir/--sin-abrir")) -> None:
    """Levanta el sitio local y vigila la carpeta de transcripciones."""
    import uvicorn

    cfg = config.actual()
    cfg.crear_carpetas()
    puerto = puerto or cfg.general.puerto_web
    if abrir:
        webbrowser.open(f"http://localhost:{puerto}/")
    uvicorn.run("reuniones.web.app:app", host="127.0.0.1", port=puerto, log_level="warning")


@app.command()
def revisar() -> None:
    """Procesa los archivos que ya estan en la carpeta de transcripciones."""
    with db.sesion() as con:
        resultados = ingesta.revisar_carpeta(con)
    if not resultados:
        typer.echo("No habia archivos nuevos.")
        return
    for nombre, desenlace in resultados:
        color = {"asociado": typer.colors.GREEN, "bandeja": typer.colors.YELLOW,
                 "duplicado": typer.colors.BLUE}.get(desenlace.estado, typer.colors.RED)
        detalle = f" -> reunion {desenlace.reunion_id}" if desenlace.reunion_id else f" ({desenlace.motivo})"
        typer.secho(f"{desenlace.estado:10} {nombre}{detalle}", fg=color)


@app.command()
def buscar(consulta: str, redactar: bool = typer.Option(False, "--redactar",
                                                        help="Redacta la respuesta con Gemini.")) -> None:
    """Busca en minutas y transcripciones."""
    with db.sesion() as con:
        hallazgos = busqueda.buscar(con, consulta)
        if not hallazgos:
            typer.echo("Sin resultados.")
            raise typer.Exit()
        for hallazgo in hallazgos:
            typer.secho(f"{hallazgo.persona} · {util.fecha_corta(hallazgo.inicio)} · "
                        f"{hallazgo.asunto or 'sin asunto'}", bold=True)
            typer.echo(f"  {util.recortar_texto(hallazgo.texto, 220)}")
            typer.echo(f"  {_url('/reunion/' + str(hallazgo.reunion_id))}")
        if redactar:
            try:
                typer.secho("\n" + busqueda.responder(con, consulta, hallazgos), fg=typer.colors.CYAN)
            except RuntimeError as error:
                typer.secho(str(error), fg=typer.colors.RED)


@app.command()
def indexar() -> None:
    """Reconstruye el indice de busqueda."""
    with db.sesion() as con:
        total = busqueda.reindexar(con)
    modo = "con significado" if busqueda.modelo_local() else "solo por palabras clave"
    typer.echo(f"{total} fragmentos indexados ({modo}).")


@app.command()
def limpiar() -> None:
    """Borra los videos del alta cuya retencion vencio."""
    with db.sesion() as con:
        borrados = mantenimiento.borrar_videos_vencidos(con)
    typer.echo(f"{len(borrados)} video(s) borrados. {mantenimiento.limpiar_temporal()} temporal(es) eliminados.")


@app.command()
def estado() -> None:
    """Resumen de lo que hay en la base y de la configuracion."""
    with db.sesion() as con:
        datos = mantenimiento.resumen(con)
    for clave, valor in datos.items():
        typer.echo(f"{clave.replace('_', ' ').capitalize():24} {valor}")
    listo, motivo = correo.configurado()
    typer.echo(f"{'Correo':24} {'configurado' if listo else motivo}")


@app.command("probar-correo")
def probar_correo() -> None:
    """Verifica el acceso al servidor SMTP institucional."""
    try:
        typer.secho(correo.probar(), fg=typer.colors.GREEN)
    except correo.ErrorCorreo as error:
        typer.secho(str(error), fg=typer.colors.RED)
        raise typer.Exit(1)


def main() -> None:
    try:
        app()
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
