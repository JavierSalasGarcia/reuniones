# Expedientes de reuniones

Sistema local para la subdirección académica: reconoce a la persona que entra a la oficina,
abre su expediente con el historial de asuntos y minutas, asocia solo las transcripciones que
sueltas desde el teléfono y permite enviar la minuta por correo como precedente de la
siguiente reunión.

Todo corre en la laptop. Las fotografías, los vectores faciales, las transcripciones y las
minutas nunca salen del equipo; lo único que sale es el correo que tú decides enviar y, si
activas esa opción, los fragmentos que Gemini necesita para redactar una respuesta de búsqueda.

Esta es la primera de las tres etapas del proyecto. Faltan la parte pública en el hosting
(turnos, citas y disponibilidad con código QR) y el kiosco de la Raspberry Pi.

## Instalación en Windows

Necesitas Python 3.11 o más reciente. Desde la carpeta del proyecto:

```
powershell -ExecutionPolicy Bypass -File scripts\instalar.ps1
```

El script crea el entorno virtual, instala las dependencias y copia `config.example.toml`
a `config.toml` y `.env.example` a `.env`. Después edita esos dos archivos: en `config.toml`
la carpeta de datos, la cámara y el servidor de correo; en `.env` la contraseña SMTP y, si la
vas a usar, la llave de Gemini.

La primera identificación descarga los modelos de InsightFace (unos 300 MB, una sola vez),
así que conviene hacerla con internet disponible.

## Uso diario

`scripts\servidor.cmd` levanta el sitio en `http://localhost:8000` y deja vigilada la carpeta
de transcripciones. Conviene ponerlo en el arranque de Windows.

`scripts\reunion.cmd` identifica a quien acaba de entrar: dos segundos de cámara, sin guardar
ninguna imagen, y abre su expediente en el navegador. Si la persona es nueva:

```
scripts\reunion.cmd nueva "Nombre Apellido" correo@uaemex.mx
```

Eso graba seis segundos de video, extrae de ahí la mejor fotografía tipo credencial y crea el
expediente. El video se borra solo a los siete días; mientras tanto puedes cambiar la foto por
alguna de las alternativas desde la ficha de la persona.

Durante la reunión, en la ficha escribes el asunto y pulsas «Iniciar reunión». Al terminar,
sueltas en la carpeta `transcripciones` los dos archivos que produce el teléfono:

```
20260914_1035_original.txt
20260914_1035_minuta.txt
```

El sistema los liga solos a la reunión más cercana en tiempo. Si hay dos reuniones a esa hora
o ninguna, el archivo aparece en la bandeja para que lo asignes con un clic.

Desde la reunión puedes registrar acuerdos con responsable y fecha, ver la minuta en PDF y
enviarla por correo. La transcripción original nunca se adjunta.

## Otros comandos

```
reunion buscar "revalidaciones"     busca en todas las minutas y transcripciones
reunion buscar "..." --redactar     además redacta la respuesta con Gemini
reunion revisar                     procesa lo que ya está en la carpeta
reunion indexar                     reconstruye el índice de búsqueda
reunion limpiar                     borra los videos cuya retención venció
reunion estado                      resumen de la base y la configuración
reunion probar-correo               verifica el acceso al SMTP institucional
```

## Cómo elige la fotografía

De cada cuadro del video se mide la nitidez, el tamaño y el centrado del rostro, la frontalidad
calculada con los puntos faciales, la apertura de los ojos, el cierre de la boca y la
uniformidad de la exposición. El cuadro con mejor puntaje compuesto se recorta en proporción
35×45 milímetros, con la cabeza ocupando el 68 % del alto y los ojos al 42 % desde el borde
superior, y se le equilibra el color. Los umbrales y proporciones se ajustan en `config.toml`.

## Reconocimiento

Cada persona guarda un vector facial promedio y hasta ocho vectores adicionales que el sistema
va aprendiendo de sus visitas. Por arriba de 0.55 de similitud identifica directo; entre 0.40 y
0.55 muestra los tres candidatos más parecidos para que confirmes; por debajo lo declara
desconocido. La búsqueda por nombre siempre está disponible como respaldo.

## Privacidad

Las fotografías y los vectores faciales son datos personales. El alta exige registrar el
consentimiento de la persona, el video crudo se borra automáticamente, cada expediente puede
marcarse como reservado para no exponer el nombre en pantallas públicas, y conviene tener la
carpeta de datos en un disco cifrado con BitLocker.

## Pruebas

```
python -m pytest
```

Las pruebas no necesitan cámara: simulan los rostros y los vectores.
