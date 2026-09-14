package mx.fingenieria.fila

import android.app.Application
import android.content.Context
import android.os.Build
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

/** Lo que pinta la pantalla en cada momento. */
data class Estado(
    val vista: Vista? = null,
    val error: String = "",
    val cargando: Boolean = true,
)

private const val ESPERA_NORMAL_MS = 20_000L
private const val ESPERA_TRAS_ERROR_MS = 60_000L

class FilaViewModel(app: Application) : AndroidViewModel(app) {

    private val _estado = MutableStateFlow(Estado())
    val estado: StateFlow<Estado> = _estado.asStateFlow()

    private var ciclo: Job? = null
    private var esperandoPrevio: Int? = null
    private var yaAvisoDelExceso = false

    /** Consulta cada tanto mientras la pantalla esta a la vista. */
    fun observar() {
        if (ciclo?.isActive == true) return
        ciclo = viewModelScope.launch {
            while (isActive) {
                val espera = if (actualizar()) ESPERA_NORMAL_MS else ESPERA_TRAS_ERROR_MS
                delay(espera)
            }
        }
    }

    fun detener() {
        ciclo?.cancel()
        ciclo = null
    }

    /** Devuelve true si la consulta salio bien. */
    suspend fun actualizar(): Boolean = try {
        val vista = Api.consultar()
        avisarSiCambio(vista)
        _estado.value = Estado(vista = vista, error = "", cargando = false)
        true
    } catch (error: ErrorApi) {
        _estado.value = _estado.value.copy(
            error = error.message ?: "No se pudo consultar",
            cargando = false,
        )
        false
    }

    private fun avisarSiCambio(vista: Vista) {
        val previo = esperandoPrevio
        if (previo != null && vista.esperando > previo) {
            vibrar(longArrayOf(0, 120, 90, 120))     // alguien se formó
        }
        esperandoPrevio = vista.esperando

        val excedido = vista.actual?.excedido == true
        if (excedido && !yaAvisoDelExceso) {
            vibrar(longArrayOf(0, 300))              // la reunión se pasó de tiempo
        }
        yaAvisoDelExceso = excedido
    }

    private fun vibrar(patron: LongArray) {
        val contexto = getApplication<Application>()
        val vibrador = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            val gestor = contexto.getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as? VibratorManager
            gestor?.defaultVibrator
        } else {
            @Suppress("DEPRECATION")
            contexto.getSystemService(Context.VIBRATOR_SERVICE) as? Vibrator
        }
        vibrador?.vibrate(VibrationEffect.createWaveform(patron, -1))
    }
}
