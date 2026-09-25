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
| `OCR_MIN_CONF` | `0.90` (opcional) — por debajo de esto la página se vuelve a leer |
| `OCR_RELECTURA` | `1` (opcional) — `0` desactiva la relectura en alta resolución |
| `OCR_MAX_RELECTURAS` | `60` (opcional) — tope de páginas a releer por expediente |
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

## 8.bis  Calidad de lectura (OCR) — lo más importante para la exactitud

El OCR ahora trabaja en **dos pasadas**: primero lee el PDF completo y después
**vuelve a leer, una por una y en alta resolución (300 y 400 DPI), las páginas
que quedaron por debajo del 90%**, quedándose con la mejor lectura. Por eso
tarda más a propósito.

**El límite real está en el escaneo, no en el programa.** Tus expedientes vienen
a **~96 DPI** (793×1122 píxeles por hoja A4), la mitad de lo recomendado. Medido
sobre el expediente 10559, una orden con sellos pasó de **47% a 77%** al releerla
en alta resolución, pero no se puede recuperar el detalle que el escáner nunca
capturó. **Si configuran el escáner a 300 DPI en blanco y negro o escala de
grises, la lectura sube sola y de forma pareja**; ese cambio vale más que
cualquier ajuste del programa. Con 96 DPI, el 98% no es alcanzable en las hojas
con sellos y firmas; con 300 DPI es un objetivo razonable.

La pantalla de resultados y el Excel indican cuántas páginas se releyeron y
**cuáles siguen por debajo del umbral**, para revisarlas a mano.

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
