# Gestión de Logística — interfaz «Estado»

Rediseño de la app de la Oficina de Logística con la estructura de un portal
del Estado y marca propia. **No cambia ninguna función existente**: mismos
botones, textos, IDs y el mismo `app.js` / `empleado.js`.

> Repositorio público: aquí solo va la interfaz y el parche del ingreso. El
> resto del backend, la semilla de datos y el directorio de funcionarios no se
> suben.

## Ingreso (landing animada)

Tarjeta partida con curvas rojas animadas, círculo con la ruta de logística y
el sello propio (`static/marca.svg`) como avatar y marca de agua. Pasos:

1. **¿A qué municipalidad perteneces?** — buscador sobre la base de
   municipalidades de la app; recuerda la última elegida («Continuar con …»).
2. **¿A qué área perteneces?** — los mismos 3 botones de antes.
3. **Cargo** — Jefe de Logística / Encargado(a), igual que antes.
4. **Usuario y contraseña**.

La entrada escondida de administrador (doble clic en el sello o el candado)
sigue igual. La municipalidad es informativa, como el cargo: se guarda en la
sesión, se muestra en la franja superior y queda en la bitácora; **no cambia
permisos**.

## Inicio (administradores y jefes)

- Franja superior con la municipalidad, atajos y la cuenta.
- Barra con menús **Subprocesos · Control · Administración** (Control suma los
  avisos de Riesgos, Verificación posterior y Bandeja).
- **Carrusel principal** con números y anillo de progreso: Resumen, ⚠ Riesgos,
  Verificación posterior, Bandeja y Ejecutar información (según el rol).
- **Resumen de un vistazo**: números que cuentan y gráfico de órdenes por año.
- Subprocesos como tarjetas con íconos de línea y flechas, banners de
  «Información ya cargada» y «Guía rápida», pie de página completo y ayuda
  flotante.

## Archivos

| Archivo | Cambio |
|---|---|
| `static/estado.css`, `static/estado.js`, `static/marca.svg` | Nuevos |
| `templates/*.html` | Nueva estructura, mismos IDs y funciones |
| `app/server_login.patch` | Ruta `/login`: lista de municipalidades y registro de la elegida |

## Ficha de cada documento del expediente (OCR enfocado)

Al pasar el puntero por una hoja del **Mapa del expediente** se ve el título
completo tal como está impreso («INFORME N° 132-2026-MPC/GPS/SGPVL»,
«MEMORANDO N° 2809-2026-MPC-OGAF-OLG»…), el asunto, quién lo envía y a quién
(nombre y cargo), la fecha, las firmas y los sellos. Debajo del mapa, una
tarjeta por documento muestra lo mismo con el detalle de cada lectura.

- `app/riesgo/ficha.py` (nuevo): relee a 300 ppp la cabecera y el pie de cada
  documento con Tesseract, corrige las siglas con las que enseña el propio
  expediente (membretes y citas), completa números escritos a mano con las
  citas de otros documentos, lee A / DE / ASUNTO / REFERENCIA / FECHA aunque
  un sello tape la etiqueta, reconoce firmas (sello de firma o pie de firma,
  con DNI si lo hay) y sellos (recepción, proveído, folio, visto bueno) con
  oficina, fecha y hora.
- `patches/servicio.patch`: `analizar_expediente` guarda `documentos` (con su
  ficha) y `mapa` en el registro del análisis.
- `patches/app_js.patch`, `patches/styles_css.patch`: mapa de hojas con ficha
  flotante y tarjetas de documentos.

Requiere `tesseract-ocr` y `tesseract-ocr-spa` en el servidor, más
`pytesseract` y `numpy` (ya en `requirements.txt`). Sin Tesseract se usa solo
el texto del escáner y la ficha sale menos completa.
