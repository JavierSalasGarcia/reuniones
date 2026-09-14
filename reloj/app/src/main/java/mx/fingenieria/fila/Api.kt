package mx.fingenieria.fila

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.BufferedReader
import java.net.HttpURLConnection
import java.net.URL

/** Lo que el reloj necesita saber, tal como lo entrega el servidor. */
data class Vista(
    val hora: String = "",
    val atencion: String = "",
    val leyenda: String = "",
    val esperando: Int = 0,
    val actual: EnCurso? = null,
    val siguiente: Siguiente? = null,
)

data class EnCurso(
    val folio: Int,
    val nombre: String,
    val minutos: Int,
    val transcurridos: Int,
    val restan: Int,
    val excedido: Boolean,
)

data class Siguiente(
    val folio: Int,
    val nombre: String,
    val asunto: String,
    val hora: String?,
    val espera: Int?,
)

class ErrorApi(mensaje: String) : Exception(mensaje)

/**
 * Consulta la vista del reloj. Usa la llave de solo lectura: con ella no se
 * puede llamar turnos ni cancelar nada, solo mirar.
 */
object Api {

    suspend fun consultar(): Vista = withContext(Dispatchers.IO) {
        if (BuildConfig.TOKEN.isBlank()) {
            throw ErrorApi("Falta la llave en local.properties")
        }
        val direccion = "${BuildConfig.SITIO.trimEnd('/')}/api" +
            "?d=${BuildConfig.DEPENDENCIA}&accion=reloj"

        val conexion = (URL(direccion).openConnection() as HttpURLConnection).apply {
            requestMethod = "GET"
            setRequestProperty("Authorization", "Bearer ${BuildConfig.TOKEN}")
            setRequestProperty("Accept", "application/json")
            connectTimeout = 10_000
            readTimeout = 10_000
        }

        try {
            val codigo = conexion.responseCode
            if (codigo == 401) throw ErrorApi("La llave del reloj no es válida")
            if (codigo >= 400) throw ErrorApi("El servidor respondió $codigo")

            val texto = conexion.inputStream.bufferedReader().use(BufferedReader::readText)
            leer(JSONObject(texto))
        } catch (error: ErrorApi) {
            throw error
        } catch (error: Exception) {
            throw ErrorApi("Sin conexión con el sitio")
        } finally {
            conexion.disconnect()
        }
    }

    internal fun leer(json: JSONObject): Vista {
        val actual = json.optJSONObject("actual")?.let {
            EnCurso(
                folio = it.optInt("folio"),
                nombre = it.optString("nombre"),
                minutos = it.optInt("minutos"),
                transcurridos = it.optInt("transcurridos"),
                restan = it.optInt("restan"),
                excedido = it.optBoolean("excedido"),
            )
        }
        val siguiente = json.optJSONObject("siguiente")?.let {
            Siguiente(
                folio = it.optInt("folio"),
                nombre = it.optString("nombre"),
                asunto = it.optString("asunto"),
                hora = it.optString("hora").ifBlank { null },
                espera = if (it.isNull("espera")) null else it.optInt("espera"),
            )
        }
        return Vista(
            hora = json.optString("ahora"),
            atencion = json.optString("atencion"),
            leyenda = json.optString("leyenda"),
            esperando = json.optInt("esperando"),
            actual = actual,
            siguiente = siguiente,
        )
    }
}
