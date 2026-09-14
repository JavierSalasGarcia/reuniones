import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

// La direccion del sitio y la llave del reloj viven en local.properties, fuera
// del repositorio, y entran a la aplicacion al compilar.
val ajustes = Properties().apply {
    val archivo = rootProject.file("local.properties")
    if (archivo.exists()) archivo.inputStream().use { load(it) }
}

fun ajuste(clave: String, porOmision: String): String =
    (ajustes.getProperty(clave) ?: porOmision).trim()

android {
    namespace = "mx.fingenieria.fila"
    compileSdk = 35

    defaultConfig {
        applicationId = "mx.fingenieria.fila"
        minSdk = 30
        targetSdk = 34
        versionCode = 1
        versionName = "1.0"

        buildConfigField("String", "SITIO", "\"${ajuste("fila.sitio", "https://fingenieria.mx/citas")}\"")
        buildConfigField("String", "DEPENDENCIA", "\"${ajuste("fila.dependencia", "sa")}\"")
        buildConfigField("String", "TOKEN", "\"${ajuste("fila.token", "")}\"")
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.7")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.7")
    implementation("androidx.compose.ui:ui:1.7.6")
    implementation("androidx.compose.ui:ui-tooling-preview:1.7.6")
    implementation("androidx.wear.compose:compose-material:1.4.0")
    implementation("androidx.wear.compose:compose-foundation:1.4.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.9.0")
    debugImplementation("androidx.compose.ui:ui-tooling:1.7.6")
}
