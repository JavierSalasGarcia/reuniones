package mx.fingenieria.fila

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.compose.LifecycleResumeEffect
import androidx.wear.compose.material.CircularProgressIndicator
import androidx.wear.compose.material.MaterialTheme
import androidx.wear.compose.material.Scaffold
import androidx.wear.compose.material.Text
import androidx.wear.compose.material.TimeText

private val VERDE = Color(0xFF7EE0A3)
private val AMBAR = Color(0xFFF0C98A)
private val ROJO = Color(0xFFF08A8A)
private val TENUE = Color(0xFF9FC3E0)

@Composable
fun Pantalla(modelo: FilaViewModel) {
    val estado by modelo.estado.collectAsStateWithLifecycle()

    // Consulta solo mientras la pantalla esta a la vista, para no gastar bateria.
    LifecycleResumeEffect(Unit) {
        modelo.observar()
        onPauseOrDispose { modelo.detener() }
    }

    MaterialTheme {
        Scaffold(timeText = { TimeText() }) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .verticalScroll(rememberScrollState())
                    .padding(horizontal = 14.dp, vertical = 28.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center,
            ) {
                val vista = estado.vista
                when {
                    vista != null -> Contenido(vista, estado.error)
                    estado.cargando -> CircularProgressIndicator()
                    else -> Aviso(estado.error.ifBlank { "Sin datos" })
                }
            }
        }
    }
}

@Composable
private fun Contenido(vista: Vista, error: String) {
    val actual = vista.actual
    if (actual != null) {
        Text(
            text = actual.nombre,
            fontSize = 18.sp,
            fontWeight = FontWeight.Bold,
            textAlign = TextAlign.Center,
        )
        Text(
            text = if (actual.excedido) "${-actual.restan} min de más" else "faltan ${actual.restan} min",
            fontSize = 26.sp,
            fontWeight = FontWeight.Bold,
            color = if (actual.excedido) ROJO else VERDE,
            modifier = Modifier.padding(top = 2.dp),
        )
        Text(
            text = "llevan ${actual.transcurridos} de ${actual.minutos}",
            fontSize = 12.sp,
            color = TENUE,
        )
    } else {
        Text(
            text = vista.leyenda.ifBlank { "Sin atención" },
            fontSize = 16.sp,
            fontWeight = FontWeight.Bold,
            color = if (vista.atencion == "atendiendo") VERDE else AMBAR,
            textAlign = TextAlign.Center,
        )
    }

    Text(
        text = "— sigue —",
        fontSize = 11.sp,
        color = TENUE,
        modifier = Modifier.padding(top = 12.dp, bottom = 2.dp),
    )

    val siguiente = vista.siguiente
    if (siguiente == null) {
        Text(text = "nadie esperando", fontSize = 14.sp, color = TENUE)
    } else {
        Text(
            text = "${siguiente.folio} · ${siguiente.nombre}",
            fontSize = 16.sp,
            fontWeight = FontWeight.Bold,
            textAlign = TextAlign.Center,
        )
        if (siguiente.asunto.isNotBlank()) {
            Text(
                text = siguiente.asunto,
                fontSize = 12.sp,
                color = TENUE,
                textAlign = TextAlign.Center,
            )
        }
        val cola = if (vista.esperando > 1) " · ${vista.esperando} en fila" else ""
        Text(
            text = (siguiente.hora?.let { "a las $it" } ?: "sin hora") + cola,
            fontSize = 12.sp,
            color = TENUE,
        )
    }

    if (error.isNotBlank()) {
        Text(
            text = error,
            fontSize = 11.sp,
            color = AMBAR,
            textAlign = TextAlign.Center,
            modifier = Modifier.padding(top = 10.dp),
        )
    }
}

@Composable
private fun Aviso(texto: String) {
    Text(
        text = texto,
        fontSize = 15.sp,
        color = AMBAR,
        textAlign = TextAlign.Center,
    )
}
