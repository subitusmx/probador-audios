# Probador de Audios

Compara audios generados con voz artificial (ElevenLabs u otra) contra el texto original del guion
y avisa si se saltaron palabras, se cambiaron o se agregaron. Funciona en tu computadora: los audios
no se suben a ningún servidor.

## Descargar

| Sistema | Descarga |
|---|---|
| **Mac** (macOS 11 o más reciente, Apple Silicon o Intel) | [ProbadorAudios-Mac.dmg](https://github.com/subitusmx/probador-audios/releases/latest/download/ProbadorAudios-Mac.dmg) |
| **Windows** 10 / 11 (64 bits) | [ProbadorAudios-Windows-Setup.exe](https://github.com/subitusmx/probador-audios/releases/latest/download/ProbadorAudios-Windows-Setup.exe) |

### Instalar en Mac
1. Abre el archivo `.dmg` descargado.
2. Arrastra **Probador de Audios** a la carpeta **Aplicaciones**.
3. Ábrela desde Aplicaciones. La primera vez la Mac pregunta si quieres abrirla: pulsa **Abrir**.

### Instalar en Windows
1. Abre el archivo `ProbadorAudios-Windows-Setup.exe` descargado y sigue los pasos.
2. Abre **Probador de Audios** desde el menú Inicio o el Escritorio.

La primera vez la app descarga sus componentes y el modelo de voz (unos 3 GB); tarda unos minutos.
Después funciona sin internet.

## Cómo se usa
1. Arrastra tus audios a la página (se ordenan por nombre de archivo).
2. Pega el texto de cada audio en su casilla y elige el idioma.
3. Pulsa **Verificar todos**.
4. Revisa las palabras marcadas: haz clic en cualquiera para escuchar ese momento del audio.

## Desinstalar
- **Mac:** abre la app y elige en el menú **Probador de Audios > Desinstalar Probador de Audios…**
- **Windows:** Configuración > Aplicaciones > Probador de Audios > Desinstalar.

Así se borran también el modelo de voz y los componentes descargados.

## Dónde se guardan los datos
- **Mac:** `~/Library/Application Support/ProbadorAudios`
- **Windows:** `%LOCALAPPDATA%\ProbadorAudios`

---

Para desarrolladores: cada versión se arma, se prueba con voz sintética, se firma y se publica
automáticamente con GitHub Actions (`.github/workflows/construir.yml`). Para publicar una versión
nueva, crea una etiqueta `vX.Y.Z`.
