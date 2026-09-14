package mx.fingenieria.fila

import android.content.Context
import androidx.concurrent.futures.CallbackToFutureAdapter
import androidx.wear.protolayout.ActionBuilders
import androidx.wear.protolayout.ColorBuilders.argb
import androidx.wear.protolayout.DimensionBuilders.expand
import androidx.wear.protolayout.LayoutElementBuilders
import androidx.wear.protolayout.ModifiersBuilders
import androidx.wear.protolayout.ResourceBuilders
import androidx.wear.protolayout.TimelineBuilders
import androidx.wear.protolayout.material.Text
import androidx.wear.protolayout.material.Typography
import androidx.wear.tiles.RequestBuilders
import androidx.wear.tiles.TileBuilders
import androidx.wear.tiles.TileService
import com.google.common.util.concurrent.ListenableFuture
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch

private const val VERSION_RECURSOS = "1"
private const val FRESCURA_MS = 60_000L   // cada cuánto pide el sistema datos nuevos

private const val VERDE = 0xFF7EE0A3.toInt()
private const val ROJO = 0xFFF08A8A.toInt()
private const val AMBAR = 0xFFF0C98A.toInt()
private const val TENUE = 0xFF9FC3E0.toInt()
private const val BLANCO = 0xFFFFFFFF.toInt()

/**
 * La tarjeta que aparece deslizando desde la carátula: a quién atiendes con lo
 * que le falta, quién sigue y cuántos esperan. Al tocarla abre la aplicación.
 */
class FilaTileService : TileService() {

    private val alcance = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    override fun onDestroy() {
        alcance.cancel()
        super.onDestroy()
    }

    override fun onTileRequest(
        requestParams: RequestBuilders.TileRequest,
    ): ListenableFuture<TileBuilders.Tile> =
        CallbackToFutureAdapter.getFuture { terminar ->
            alcance.launch {
                val vista = try {
                    Api.consultar().also { Memoria.guardar(it) }
                } catch (error: ErrorApi) {
                    Memoria.ultima            // sin red se muestra lo último conocido
                }
                terminar.set(armarMosaico(this@FilaTileService, vista))
            }
            "mosaico de la fila"
        }

    override fun onTileResourcesRequest(
        requestParams: RequestBuilders.ResourcesRequest,
    ): ListenableFuture<ResourceBuilders.Resources> =
        CallbackToFutureAdapter.getFuture { terminar ->
            terminar.set(
                ResourceBuilders.Resources.Builder()
                    .setVersion(VERSION_RECURSOS)
                    .build()
            )
            "recursos del mosaico"
        }
}

/** Lo último que se supo, para que el mosaico nunca aparezca en blanco. */
object Memoria {
    @Volatile
    var ultima: Vista? = null
        private set

    fun guardar(vista: Vista) {
        ultima = vista
    }
}

internal fun armarMosaico(contexto: Context, vista: Vista?): TileBuilders.Tile =
    TileBuilders.Tile.Builder()
        .setResourcesVersion(VERSION_RECURSOS)
        .setFreshnessIntervalMillis(FRESCURA_MS)
        .setTileTimeline(
            TimelineBuilders.Timeline.fromLayoutElement(contenido(contexto, vista))
        )
        .build()

private fun contenido(contexto: Context, vista: Vista?): LayoutElementBuilders.LayoutElement {
    val columna = LayoutElementBuilders.Column.Builder()
        .setWidth(expand())
        .setHorizontalAlignment(LayoutElementBuilders.HORIZONTAL_ALIGN_CENTER)
        .setModifiers(alTocarAbrirLaApp(contexto))

    if (vista == null) {
        columna.addContent(texto(contexto, "Sin datos", Typography.TYPOGRAPHY_TITLE3, AMBAR))
        columna.addContent(texto(contexto, "abre la app", Typography.TYPOGRAPHY_CAPTION2, TENUE))
        return columna.build()
    }

    val actual = vista.actual
    if (actual != null) {
        columna.addContent(texto(contexto, actual.nombre, Typography.TYPOGRAPHY_TITLE3, BLANCO))
        columna.addContent(
            texto(
                contexto,
                if (actual.excedido) "${-actual.restan} min de más" else "faltan ${actual.restan} min",
                Typography.TYPOGRAPHY_TITLE1,
                if (actual.excedido) ROJO else VERDE,
            )
        )
    } else {
        columna.addContent(
            texto(
                contexto,
                vista.leyenda.ifBlank { "Sin atención" },
                Typography.TYPOGRAPHY_TITLE3,
                if (vista.atencion == "atendiendo") VERDE else AMBAR,
            )
        )
    }

    val siguiente = vista.siguiente
    val linea = when {
        siguiente == null -> "nadie esperando"
        siguiente.hora != null -> "Sigue ${siguiente.nombre} · ${siguiente.hora}"
        else -> "Sigue ${siguiente.nombre}"
    }
    columna.addContent(texto(contexto, linea, Typography.TYPOGRAPHY_CAPTION1, TENUE))

    if (vista.esperando > 1) {
        columna.addContent(
            texto(contexto, "${vista.esperando} en fila", Typography.TYPOGRAPHY_CAPTION2, TENUE)
        )
    }
    return columna.build()
}

private fun texto(contexto: Context, valor: String, tipografia: Int, color: Int): Text =
    Text.Builder(contexto, valor)
        .setTypography(tipografia)
        .setColor(argb(color))
        .setMaxLines(2)
        .build()

private fun alTocarAbrirLaApp(contexto: Context): ModifiersBuilders.Modifiers =
    ModifiersBuilders.Modifiers.Builder()
        .setClickable(
            ModifiersBuilders.Clickable.Builder()
                .setId("abrir")
                .setOnClick(
                    ActionBuilders.LaunchAction.Builder()
                        .setAndroidActivity(
                            ActionBuilders.AndroidActivity.Builder()
                                .setPackageName(contexto.packageName)
                                .setClassName(MainActivity::class.java.name)
                                .build()
                        )
                        .build()
                )
                .build()
        )
        .build()
