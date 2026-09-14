"""Comandos cortos para usar el sistema sin soltar la conversacion.

    reunion                      identifica a quien acaba de entrar
    reunion nueva "Nombre" correo    da de alta a alguien por primera vez
    reunion servidor             levanta el sitio local
"""

from __future__ import annotations

import sys
import webbrowser
from pathlib import Path

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

    from .web import kiosco

    cfg = config.actual()
    cfg.crear_carpetas()
    puerto = puerto or cfg.general.puerto_web
    kiosco.servir_en_hilo()
    if cfg.kiosco.habilitado:
        typer.echo(f"Respaldo de la pantalla en la red local: puerto {cfg.kiosco.puerto}")
    if abrir:
        webbrowser.open(f"http://localhost:{puerto}/")
    uvicorn.run("reuniones.web.app:app", host="127.0.0.1", port=puerto, log_level="warning")


@app.command()
def abrir(cierre: str = typer.Option("", "--cierre", "-c", help="Hora en que terminas hoy, 15:00."),
          tope: str = typer.Option("", "--tope", "-t", help="Última hora para formarse en la cola."),
          mensaje: str = typer.Option("", "--mensaje", "-m")) -> None:
    """Llegaste a la oficina: abre la atención de hoy."""
    from . import nube

    try:
        jornada = nube.abrir(cierre, tope, mensaje=mensaje)["jornada"]
    except nube.ErrorNube as error:
        typer.secho(str(error), fg=typer.colors.RED)
        raise typer.Exit(1)
    typer.secho(f"Atención abierta {jornada['apertura']}–{jornada['cierre']}.",
                fg=typer.colors.GREEN, bold=True)
    if jornada.get("tope"):
        typer.echo(f"  La gente puede formarse hasta las {jornada['tope']}.")
    else:
        typer.echo("  La cola se cierra sola cuando un turno más ya no alcanza antes del cierre.")


@app.command()
def cerrar(nota: str = typer.Option("", "--nota", "-n",
                                    help="Lo que verá la gente en la pantalla.")) -> None:
    """Termina la atención de hoy. Quien siga formado ya no será atendido."""
    from . import nube

    try:
        estado = nube.estado(forzar=True)
    except nube.ErrorNube as error:
        typer.secho(str(error), fg=typer.colors.RED)
        raise typer.Exit(1)
    esperando = [t for t in estado.get("turnos", []) if t.get("estado") == "espera"]
    if esperando:
        typer.secho(f"Hay {len(esperando)} persona(s) formada(s).", fg=typer.colors.YELLOW)
        typer.echo("  Si ya no las vas a atender, usa:  reunion cancelar-cola")
        if not typer.confirm("¿Cerrar de todos modos?", default=False):
            raise typer.Exit()
    try:
        nube.cerrar(nota)
    except nube.ErrorNube as error:
        typer.secho(str(error), fg=typer.colors.RED)
        raise typer.Exit(1)
    typer.secho("Atención cerrada.", fg=typer.colors.GREEN)


@app.command()
def pausar(hasta: str = typer.Option("", "--hasta", "-h", help="Hora en que vuelves, 13:00."),
           minutos: int = typer.Option(0, "--minutos", "-m"),
           motivo: str = typer.Option("No disponible", "--motivo")) -> None:
    """Un rato sin atender: clase, videoconferencia, comida o trabajo concentrado."""
    from datetime import datetime

    from . import nube

    if not hasta and not minutos:
        typer.secho("Indica --hasta 13:00 o --minutos 45.", fg=typer.colors.RED)
        raise typer.Exit(1)
    if hasta and len(hasta) == 5:
        hasta = f"{datetime.now():%Y-%m-%d} {hasta}:00"
    try:
        resultado = nube.pausar(hasta, minutos, motivo)
    except nube.ErrorNube as error:
        typer.secho(str(error), fg=typer.colors.RED)
        raise typer.Exit(1)
    regreso = str(resultado.get("hasta", ""))[11:16]
    typer.secho(f"No disponible hasta {regreso}. {motivo}", fg=typer.colors.GREEN)
    typer.echo("  Los turnos que caían en ese rato se recorrieron solos.")


@app.command("cancelar-cola")
def cancelar_cola(motivo: str = typer.Option("", "--motivo", "-m",
                                             help="Se lo verá cada persona en su correo."),
                  cerrar_dia: bool = typer.Option(True, "--cerrar/--seguir-abierto"),
                  confirmar: bool = typer.Option(False, "--si", help="No preguntar.")) -> None:
    """Emergencia: cancela a todos los formados y les avisa por correo."""
    from . import nube

    try:
        estado = nube.estado(forzar=True)
    except nube.ErrorNube as error:
        typer.secho(str(error), fg=typer.colors.RED)
        raise typer.Exit(1)
    esperando = [t for t in estado.get("turnos", []) if t.get("estado") in ("espera", "llamado")]
    if not esperando:
        typer.echo("No hay nadie formado.")
        if cerrar_dia:
            nube.cerrar(motivo)
            typer.echo("Atención cerrada.")
        raise typer.Exit()

    for turno in esperando:
        typer.echo(f"  {turno['folio']}  {turno['nombre']} <{turno['email']}>")
    if not confirmar and not typer.confirm(
            f"¿Cancelar {len(esperando)} turno(s) y avisarles por correo?", default=False):
        raise typer.Exit()

    try:
        resultado = nube.cancelar_cola(motivo, cerrar_dia)
    except nube.ErrorNube as error:
        typer.secho(str(error), fg=typer.colors.RED)
        raise typer.Exit(1)
    typer.secho(f"{resultado['cancelados']} turno(s) cancelados y avisados.",
                fg=typer.colors.GREEN, bold=True)


@app.command()
def jornada(fecha: str = typer.Argument("", help="aaaa-mm-dd; vacío es hoy."),
            apertura: str = typer.Option("", "--apertura", "-a"),
            cierre: str = typer.Option("", "--cierre", "-c"),
            tope: str = typer.Option("", "--tope", "-t"),
            cancelar: bool = typer.Option(False, "--cancelar", help="Ese día no habrá atención."),
            nota: str = typer.Option("", "--nota", "-n")) -> None:
    """Consulta o deja lista la jornada de un día, hoy o cualquiera por venir."""
    from datetime import datetime

    from . import nube

    fecha = fecha or f"{datetime.now():%Y-%m-%d}"
    try:
        if apertura or cierre or tope or cancelar or nota:
            datos = nube.configurar_jornada(fecha, apertura, cierre,
                                            tope if tope else None,
                                            "cancelada" if cancelar else "", nota)["jornada"]
        else:
            datos = nube.jornada(fecha)
    except nube.ErrorNube as error:
        typer.secho(str(error), fg=typer.colors.RED)
        raise typer.Exit(1)
    if not datos:
        typer.echo(f"{fecha}: sin atención programada.")
        raise typer.Exit()
    typer.echo(f"{fecha}  {datos['apertura']}–{datos['cierre']}  ({datos['estado']})")
    typer.echo(f"  Registro en la cola hasta: {datos['tope'] or 'mientras alcance el horario'}")
    if datos.get("nota"):
        typer.echo(f"  Nota: {datos['nota']}")


@app.command()
def qr(destino: str = typer.Option("", "--destino", "-d")) -> None:
    """Genera el codigo QR de tu pagina publica para imprimirlo."""
    from . import nube

    try:
        ruta = nube.generar_qr(Path(destino) if destino else None)
    except nube.ErrorNube as error:
        typer.secho(str(error), fg=typer.colors.RED)
        raise typer.Exit(1)
    typer.echo(f"{ruta}\n{nube.url_publica()}")


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
    """Verifica el acceso al servidor de correo de fingenieria.mx."""
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
