# Gestión de Logística — nuevo diseño «Cine»

Capa visual nueva para la app de la Oficina de Logística. **No cambia ninguna
función**: mismos textos, mismos botones, mismos IDs y el mismo `app.js` /
`empleado.js`. Solo cambia cómo se ve y agrega opciones para personalizarla.

> Este repositorio es público: aquí solo están los archivos de la interfaz.
> El backend, la semilla de datos y el directorio de funcionarios **no** se
> suben.

## Qué cambió

| Archivo | Cambio |
|---|---|
| `static/nuevo.css` | **Nuevo.** Colores, letras, vidrio líquido y animaciones. Se carga después de `styles.css`; si se quita, la app vuelve a verse como antes. |
| `static/ui.js` | **Nuevo.** Panel «Personalizar», video de fondo, títulos animados y luz que sigue al puntero. |
| `templates/*.html` | Cargan las letras nuevas (Instrument Serif + Manrope), `nuevo.css` y `ui.js`. En `login.html` y `setup.html` la tarjeta pasa a usar la clase `login-card`. |

## Cómo se ve

- **Oscuro de cine por defecto**, con luz de aurora detrás de superficies de
  vidrio líquido. El tema claro sigue disponible (🌓 Tema o «Personalizar»).
- **Títulos** en Instrument Serif; la última palabra en cursiva con degradado
  («Gestión de *Logística*»). Texto en Manrope; números en IBM Plex Mono.
- **Ingreso**: video en bucle a pantalla completa con fundido suave, franjas de
  cine que se abren y tarjeta de vidrio.
- **Movimiento**: tarjetas que aparecen en cascada, filas de tabla que entran
  suavemente, luz que sigue al puntero, botones con destello.
- **Colores con significado intactos**: rojo = riesgo, ámbar = alerta,
  verde = conforme. El acento elegible solo usa tonos tranquilos.

## «Personalizar» (botón abajo a la derecha)

Color (Aurora, Glaciar, Jade, Índigo) · Tema oscuro/claro · Tamaño de letra
(A, A+, A++) · Tablas cómodas o compactas · Animaciones · Alto contraste ·
Video de fondo. Todo se recuerda en cada computadora.

## Instalar sobre la app

Copiar `static/nuevo.css`, `static/ui.js` y los cuatro `templates/*.html` en
las mismas carpetas de la app (reemplazando las plantillas) y reiniciar.
Sin internet (app de escritorio) el video y las letras nuevas no cargan: la
app usa letras del sistema y la luz de aurora, y funciona igual.
