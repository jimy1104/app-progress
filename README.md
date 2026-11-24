# EnglishPro

Web estática para practicar **shadowing** con películas, series y vídeos: subtítulos duales, diccionario al pasar el ratón (español / árabe), análisis gramatical de cada frase, grabación de voz con puntuación, ejercicio de traducción y dos perfiles (2 personas).

No necesita servidor ni compilación: son archivos HTML/CSS/JS que se publican tal cual en **Azure Static Web Apps**.

## Qué hace

| Función | Detalle |
|---|---|
| Fuentes de vídeo | Archivo local (mp4, webm, mkv, mp3… se reproduce en tu navegador, **no se sube**: sirve para películas completas), YouTube, enlace directo `.mp4/.webm/.m3u8` (por ejemplo Azure Blob Storage) o *solo texto* con voz sintética. |
| Subtítulos | `.srt`, `.vtt` (incluidos los automáticos de YouTube), `.ass/.ssa`, `.sbv`, `json3` o texto plano. Segundo archivo opcional en tu idioma; si no, se traducen automáticamente. Ajuste de sincronía ±0,1 s. |
| Shadowing | Pausa al final de cada frase, continuar sola tras una pausa proporcional a la frase, repetir frase N veces (o infinito), **botón retroceder que se puede activar o quitar**, frase anterior/siguiente, velocidad 0,5×–1,25×, ocultar texto, karaoke, mapa de acento. |
| Modos (rutina) | Ver con subtítulos → Mumbling → Overlapping → Shadowing frase a frase → Shadowing continuo → Grabar y comparar → Traducir cada frase. Pestaña *Rutina* con los pasos y errores frecuentes. |
| Diccionario | Pasa el ratón por cualquier palabra (frase actual o lista): traducción al idioma nativo, alternativas por categoría, IPA, audio, definición, **ejemplos sencillos en inglés traducidos**, la frase del vídeo, phrasal verb al que pertenece, contracciones/reducciones. Guardar palabra. |
| Gramática | Motor propio (sin internet) que detecta ~40 estructuras: tiempos verbales, pasiva, modales, condicionales 0-1-2-3, wish, preguntas y *question tags*, estilo indirecto, gerundio/infinitivo, phrasal verbs, used to, causativo, comparativos… Explica la regla en español o árabe, la estructura, ejemplos traducidos y consejos. Además: habla conectada (gonna, enlaces, T americana, formas débiles) y entonación. **Gramática de todo el vídeo**: pulsa una estructura y verás todas las frases que la usan. |
| IA (opcional) | Con una clave de la API de Claude: explicación profunda de la frase (traducción natural y literal, gramática, vocabulario, pronunciación, uso) y preguntas libres. |
| Grabación | Graba tu voz (manual, automática en la pausa, o encima del audio con auriculares), forma de onda, duración vs original, «original y después mi voz», y en Chrome/Edge puntuación de palabras reconocidas. |
| Traducción | Escribe tu traducción de cada frase y compárala con la de referencia (porcentaje de similitud). |
| 🎧 Escucha y completa | Segunda app (selector arriba). Juego de escucha: desaparecen palabras de los subtítulos y las escribes mientras suena. Si la frase termina con huecos, el vídeo se pausa y corre un reloj. **Básico**: 1 palabra por frase (5 vidas) · **Medio**: 50 % (4 vidas) · **Difícil**: 90 % (3 vidas). Puntos por velocidad, combos (×1,5 … ×3), pistas, repetir frase, récord por clip y nivel, y al final puedes guardar las palabras que fallaste. Teclas: `Enter` repetir, `↓` pista, `Esc` saltar. |
| 2 personas | Dos perfiles con su idioma nativo (p. ej. español y árabe; la interfaz cambia de idioma), ajustes, palabras guardadas, repaso tipo flashcards, exportación a Anki (CSV) y estadísticas (racha, minutos, frases, grabaciones). |

Atajos: `Espacio` reproducir/pausa · `A`/`←` anterior · `S` repetir · `D`/`→` siguiente · `R` grabar · `P` escuchar mi grabación · `C` comparar · `H` ver texto oculto · `T` traducción · `L` bucle · `Q` pausa automática · `F` pantalla completa.

## Publicar en Azure Static Web Apps

1. En el portal de Azure: **Crear recurso → Static Web App**.
2. Plan *Free*. Origen: **GitHub**, repositorio `app-progress`, la rama que quieras publicar.
3. *Build details*: preset **Custom**, `App location: /`, `Api location:` vacío, `Output location:` vacío.
4. Azure añade solo un workflow de GitHub Actions con su token y publica en cada push.

`staticwebapp.config.json` ya permite el micrófono y la pantalla completa.

### Sobre los vídeos (y los 2 GB)

- Lo más sencillo: **archivo local**. La película se reproduce desde el ordenador de cada persona; no ocupa espacio en Azure.
- Para compartir vídeos entre las dos personas: súbelos a **Azure Blob Storage** (no a la Static Web App, cuyo plan gratuito tiene un límite de tamaño de app mucho menor) y pega el enlace directo del archivo. En la cuenta de almacenamiento activa **CORS** para el dominio de tu web (método `GET`) y usa un contenedor con acceso de lectura o un enlace SAS.
- **Bilibili, Netflix, Disney+…** no dejan que otra web controle su reproductor (pausar en cada frase, repetir…), así que esos enlaces no funcionan. Descarga el vídeo (si tienes derecho a hacerlo) y cárgalo como archivo o súbelo al Blob.

### Subtítulos

- Película `.mkv` con subtítulos dentro: `ffmpeg -i pelicula.mkv -map 0:s:0 subs.srt`
- YouTube: `yt-dlp --write-subs --write-auto-subs --sub-langs en --skip-download URL`

## Servicios externos que usa el navegador

- Traducción: `translate.googleapis.com` (con `api.mymemory.translated.net` como respaldo). Se guarda en caché local.
- Diccionario: `api.dictionaryapi.dev` (definiciones, IPA, audio y ejemplos).
- YouTube IFrame API, `hls.js` (solo para enlaces `.m3u8`).
- IA opcional: `api.anthropic.com`, con la clave que pongas en Ajustes. La clave se guarda solo en ese navegador.

Todos los datos (perfiles, palabras, progreso) se guardan en el `localStorage` del navegador. Para pasar datos a otro dispositivo: Ajustes → Exportar / Importar copia.

## Desarrollo local

```bash
python3 -m http.server 8080
```

Abre `http://localhost:8080` (hace falta un servidor: los módulos JS no funcionan abriendo el archivo con doble clic).

## Publicar en Azure App Service (con el archivo de publicación)

El workflow `.github/workflows/azure-webapp.yml` publica la web en cada push a `main`.

1. En GitHub → **Settings → Secrets and variables → Actions**:
   - Pestaña **Secrets** → *New repository secret*: nombre `AZURE_WEBAPP_PUBLISH_PROFILE`, valor = todo el contenido del archivo `.PublishSettings`.
   - Pestaña **Variables** → *New repository variable*: nombre `AZURE_WEBAPP_NAME`, valor = el nombre de tu Web App.
2. En Azure → tu Web App → **Configuración → Configuración general**: activa *SCM Basic Auth Publishing Credentials* (necesario para el publish profile).
3. GitHub → **Actions → Deploy to Azure Web App → Run workflow**.

En Linux con Node, App Service ejecuta `npm start` (`server.js`, sin dependencias). En Windows, IIS sirve los archivos con `web.config`.

## Extensión del navegador (Chrome / Brave / Edge)

Funciona encima del vídeo de **cualquier web** (incluidos los reproductores dentro de iframes): modo **Shadowing** (pausa en cada frase, repetir, anterior/siguiente, traducción) y **Listen & type** (el juego de completar con niveles, reloj, vidas y combos), con significados al pasar el ratón, gramática de cada frase y palabras guardadas.

Instalar:
1. Descarga `englishpro-extension.zip` (botón *Get the browser extension* en la web) y descomprímelo.
2. Abre `chrome://extensions` (o `brave://extensions`, `edge://extensions`) y activa **Modo desarrollador**.
3. **Cargar descomprimida** → elige la carpeta `extension`.

Usar: abre la película, dale a play, pulsa el icono **EP** (o `Alt+E`), carga el `.srt` en inglés en *Setup* y, si los subtítulos van desfasados, pausa en una frase, elígela y pulsa **It starts now**.

Los motores (`subtitles`, `grammar`, `game`, `translate`, `dictionary`, `i18n`) se comparten con la web: tras cambiarlos ejecuta `node tools/build-extension.mjs` y vuelve a crear el zip.
