# Gestión de Riesgo (OLG) — Subir a Azure y probar

> **¿Sin Azure?** La aplicación ya corre **en tu PC, sin nube y sin costo**, con el mismo
> motor de riesgo. Mira **`CORRER_EN_MI_PC.md`** y ejecuta `INICIAR_EN_MI_PC.bat`.
> Esta guía es solo para cuando quieras volver a publicarla en Azure.

Esta carpeta es la aplicación completa: interfaz + servidor + motor de riesgo con
tu matriz (48 riesgos de Contratos Menores y Locadores). Sigue los pasos en orden.

---

## 1. Qué desplegar
Despliega **el contenido de esta carpeta** (que `app.py` quede en la raíz del sitio).
En VS Code: clic derecho sobre esta carpeta → **Deploy to Web App…** → *Gestiónderiesgo*.

Nunca subas un archivo `.env` con llaves: las llaves van en el paso 3.

## 2. Comando de inicio (cámbialo: es distinto al anterior)
Portal de Azure → tu App Service → **Configuration → General settings → Startup Command**:

    gunicorn --bind=0.0.0.0 --timeout 600 --workers 1 --threads 8 app:app

(`--workers 1` es obligatorio: los trabajos en segundo plano viven en ese proceso.)

## 3. Application settings (Configuration → Application settings → New)

| Nombre | Valor |
|---|---|
| `AZURE_DI_ENDPOINT` | `https://gestionderiesgo.cognitiveservices.azure.com/` |
| `AZURE_DI_KEY` | tu KEY 1 de Document Intelligence (**la nueva, después de regenerarla**) |
| `AZURE_DI_MODELO` | `prebuilt-layout` |
| `AZURE_DI_LOCALE` | `es` |
| `AZURE_BLOB_CONN` | la connection string del Storage (**la nueva, después de rotarla**) |
| `AZURE_BLOB_CONTAINER` | `expedientes` |
| `ADMIN_MASTER_CODE` | **la contraseña maestra que tú inventes** (mín. 12 caracteres). Es la que pide el login de administrador. |
| `SECRET_KEY` | un texto largo al azar (40+ caracteres). Firma las sesiones. |
| `SCM_DO_BUILD_DURING_DEPLOYMENT` | `true` |
| `AZURE_DI_FEATURES` | `ocrHighResolution,barcodes` (opcional) — complementos de Azure. `ocrHighResolution` lee mejor la letra chica y los escaneos pobres (**tiene costo adicional por página**, ver el paso 8.bis); `barcodes` lee los QR de las facturas (sin costo extra). Vacío = sin complementos. |
| `OCR_OBJETIVO_PAGINA` | `0.95` (opcional) — una hoja con menos de este % de palabras seguras se vuelve a leer (y, si sigue abajo, se lista para revisarla a mano). Reemplaza a `OCR_MIN_CONF`. |
| `OCR_CONF_SEGURA` | `0.85` (opcional) — confianza desde la que una palabra cuenta como segura |
| `OCR_CONF_SEGURA_VOTADA` | `0.70` (opcional) — confianza mínima de una palabra confirmada por dos lecturas independientes |
| `OCR_RELECTURA` | `1` (opcional) — `0` desactiva la segunda pasada (imagen limpia y sin sellos) |
| `OCR_MAX_RELECTURAS` | `60` (opcional) — tope de páginas a releer por expediente |
| `OCR_HOJAS_POR_LOTE` | `15` (opcional) — hojas por llamada en la segunda pasada |
| `OCR_DPI` | `300` (opcional) — resolución de la imagen limpia que se envía en la segunda pasada |
| `PDF_BUSCABLE` | `1` (opcional) — `0` no genera el PDF con capa de texto (los cortes salen del original) |
| `OCR_PROVIDER` | `azure` (opcional) — `local` obliga a usar el OCR de la máquina. Si no se pone, usa Azure cuando hay endpoint y llave, y si no, el local. |

**Save** → la app se reinicia. No agregues `OCR_FAKE_CACHE` (es solo para pruebas locales).

## 4. Comprobar que está arriba
- `https://<tu-app>.azurewebsites.net/health` → `ok`
- `https://<tu-app>.azurewebsites.net/api/config` → todos los `*_set` en `true`

## 5. Primer ingreso (administrador)
1. Abre `https://<tu-app>.azurewebsites.net/`, pestaña **Administrador**.
2. Escribe el **usuario y contraseña que quieras** + la **contraseña maestra** (`ADMIN_MASTER_CODE`).
   La primera vez, esa cuenta de administrador se crea en ese momento; después, se valida.
3. **Usuarios → Crear usuario**: nombre de la persona + subproceso. La contraseña de 8
   caracteres la genera el sistema y **se muestra una sola vez** (se guarda cifrada; si se
   pierde, usa el botón de regenerar).

## 6. Probar con tus órdenes
- Como administrador: **Procesar expediente** (puede usar CM y Locadores).
- Como trabajador: pestaña **Trabajador**, nombre + contraseña. Solo ve el subproceso de su cuenta.
- Sube el **PDF** o un **ZIP** con los PDF del expediente (se unen en orden alfabético).
- **Detectar riesgo** o **Cortar y detectar**. Un expediente de ~50 páginas tarda 1–3 minutos;
  la página muestra el avance. Puedes esperar ahí mismo.
- En resultados: datos leídos de la orden, documentos identificados y cortados, riesgos en
  rojo/amarillo, **Ubicar** (muestra la página con el renglón resaltado), **Tomar medidas de
  control**, **Descargar en Excel** y **Limpiar** (borra todo lo de esa consulta).

## 7. Borrado automático a los 30 días (Blob)
Cada consulta deja una copia en el contenedor `expedientes/consultas/…`. Para que se borre sola:
Portal → tu **Storage account** → **Data management → Lifecycle management** → **Add a rule**:
- Nombre: `borrar-consultas-30-dias` · Tipo: Block blobs
- Filtro de prefijo: `expedientes/consultas/`
- Condición: *Last modified* más de **30** días → **Delete the blob**.

En el servidor, las copias locales se borran solas a las 72 h (y el admin puede limpiar las de
más de 24 h con un botón).

## 8. Seguridad (hazlo antes de usarlo con expedientes reales)
- Las llaves que pegaste en el chat quedaron expuestas: **regenera la KEY 1** de Document
  Intelligence y **rota la key** del Storage, y pon las nuevas en el paso 3.
- La contraseña maestra y `SECRET_KEY` solo viven en Application settings.

## 8.bis  Calidad de lectura (OCR) y cortes — cómo funciona desde la v5

**Lectura (Azure Document Intelligence, `prebuilt-layout`):**
1. **1ª pasada**: el PDF completo en UNA llamada, con `ocrHighResolution` y `barcodes`.
   Azure devuelve además el **rol** de cada párrafo (título, encabezado, pie) y marca lo
   **manuscrito** (firmas, vistos buenos); el segmentador usa ambos.
2. En paralelo, cada hoja se revisa a 150 DPI: si no tiene **tinta real** es un reverso en
   blanco (aunque se transparente el texto del otro lado) y lo que Azure «leyó» ahí se
   descarta. Las hojas **digitales** (texto nativo real, no la capa de Nitro) se toman tal cual.
3. **2ª pasada**, solo para hojas con palabras dudosas: se envían en lotes (no una llamada por
   hoja) como imagen de **300 DPI limpia** (fondo aplanado, sin el reverso transparentado) y,
   si tienen sellos de color, también **sin sellos**.
4. **Fusión palabra por palabra**: donde dos lecturas independientes coinciden, la palabra
   queda confirmada; donde discrepan, su confianza baja y la hoja se señala.
5. **Hojas de costado o de cabeza** se llevan al marco derecho del texto (Azure informa el
   ángulo); «Ubicar» dibuja la hoja derecha.

**Qué significa «lectura OCR X%»:** el % de palabras de TEXTO que quedaron **seguras** (alta
confianza o confirmadas por dos lecturas). Ya no cuenta manchas de reversos, firmas ni
esquinas de sellos, que no son texto. Las hojas que no llegan al objetivo se listan para
mirarlas: el sistema no esconde una duda.

**Datos clave con validación cruzada:** el monto de la orden se da por bueno solo si coinciden
dos fuentes (TOTAL, valor venta + IGV, monto en letras, conformidad); el RUC se verifica con su
dígito verificador (SUNAT) y se contrasta con la conformidad y la factura; el N° de orden se
contrasta con el que cita la conformidad. Un monto en conflicto no alimenta el acumulado.

**Cortes:** una decisión global sobre todas las hojas (programación dinámica) con la evidencia de
cada una: títulos con sus señales propias, «Página k de N», «VIENEN/VAN» del SIGA, el N° del
documento, el membrete que se repite o que desaparece. Los documentos fuera del catálogo salen
como «Otro documento: <título>» en vez de engordar el corte vecino. Cada documento indica sus
reversos en blanco y se marca «revisar corte» si la frontera tuvo poca evidencia.

**Descargas nuevas:** expediente **buscable** (PDF con capa de texto; los cortes también salen
buscables) y **todo el texto** leído hoja por hoja (.txt).

**Costo:** `ocrHighResolution` se cobra aparte por página; la 2ª pasada suma 1–2 páginas por
cada hoja dudosa (tope `OCR_MAX_RELECTURAS`). Para abaratar: `AZURE_DI_FEATURES=barcodes` o
`OCR_RELECTURA=0` (se pierde exactitud).

**El límite sigue estando en el escaneo:** los expedientes llegan en JPEG a **96 DPI**. Escanear
a **300 DPI en escala de grises** sube la lectura en todas las hojas, con cualquier motor.

**Medir:** `python benchmark.py carpeta/` compara lectura y cortes contra una verdad de campo
(`<expediente>.verdad.json`, ver el encabezado de `benchmark.py`). Los expedientes reales de
prueba se guardan en `tests/muestras/` (está en `.gitignore`: nunca van al repositorio).

## 9. Qué esperar del resultado (léelo antes de juzgarlo)
- **Rojo** = confirmado: se revisó dos veces con lectura clara (p. ej. un documento que no
  aparece ni como título ni en el texto, o el acumulado del mismo objeto que supera 8 UIT).
- **Amarillo** = por revisar: la lectura fue dudosa o el riesgo requiere criterio humano
  (fechas a contrastar, subordinación en el TDR, etc.). Cada tarjeta dice cómo verificarlo.
- **Verificados sin observación** = controles que se revisaron y cumplen, con dónde se halló.
- **Dónde está el riesgo**: cada hallazgo trae sus ubicaciones reales (puede tener
  varias páginas) y resalta el renglón exacto. Cuando el hallazgo es por AUSENCIA
  (el documento no aparece), no se señala ninguna hoja: se dice expresamente que
  no hay renglón que mostrar.
- El **acumulado de fraccionamiento** crece con cada orden procesada (se guarda solo N° de
  orden, RUC, monto y objeto — nunca el PDF). Al inicio tendrá pocos datos.
- Solo están activos **Contratos Menores** y **Locadores** (tu matriz). El resto se agrega
  cuando exista su matriz.

## 10. Si algo falla
- Portal → App Service → **Log stream**: muestra el error exacto.
- `/api/config` dice qué configuración falta.
- "Azure rechazó la llave…" → revisa `AZURE_DI_KEY` y `AZURE_DI_ENDPOINT`.
- El nombre con tilde (*Gestiónderiesgo*) suele funcionar; si da problemas raros, crea la
  Web App sin tilde (`gestionderiesgo`).
