# Correr la aplicación EN TU PC (sin Azure, sin costo)

Desde ahora la aplicación tiene **dos motores de lectura** y funciona igual con cualquiera:

| Motor | Dónde lee | Cuándo usarlo |
|---|---|---|
| **Azure Document Intelligence** | En la nube | Cuando tengas la cuenta activa y con crédito |
| **OCR local (Tesseract)** | En tu propia PC | Siempre que quieras: no cuesta, no caduca, no depende de nadie |

La aplicación elige sola: si no hay llaves de Azure configuradas, usa el OCR local.
Para forzarlo, se pone la variable `OCR_PROVIDER` en `local` o en `azure`.
En **Administrador → Sistema y respaldo** se ve cuál está activo.

---

## 1. Instalar (una sola vez)

1. **Python** — https://www.python.org/downloads/
   Al instalar, marca **"Add python.exe to PATH"**.
2. **Tesseract** (el lector de PDF escaneados) — https://github.com/UB-Mannheim/tesseract/wiki
   Durante la instalación, en *Additional language data*, **marca "Spanish"**.
   Sin el español la lectura empeora mucho.

## 2. Arrancar

Doble clic en **`INICIAR_EN_MI_PC.bat`**.

La primera vez tarda unos minutos (prepara el entorno e instala los componentes) y te pide
inventar la **contraseña maestra** de administrador. Después abre solo el navegador en
`http://localhost:8080`.

Para apagarla, cierra la ventana negra.

## 3. Entrar

- **Administrador**: usuario y contraseña que tú elijas + la contraseña maestra.
  La primera vez que entras, esa cuenta queda creada.
- **Trabajadores**: los creas desde *Usuarios*; el sistema genera la contraseña de 8 caracteres
  y la muestra **una sola vez**.

## 4. Dónde quedan los datos

Todo vive en la carpeta **`data`**, al lado del programa:

- `usuarios.json` — las cuentas (contraseñas cifradas, no se pueden leer)
- `acumulado.json` — el acumulado de fraccionamiento por objeto y año
- `actividad.jsonl` — la bitácora de quién hizo qué
- `jobs/` — los expedientes procesados (temporales; se borran solos a las 72 h)

**Copia esa carpeta a un USB o a OneDrive de vez en cuando**, o mejor: usa
*Administrador → Sistema y respaldo → **Descargar respaldo***, que arma un ZIP con lo que
no se puede volver a generar. Ese mismo ZIP se sube en **Restaurar respaldo** para levantar
todo en otra PC o en otro servidor. **Eso es lo que evita volver a perder el progreso.**

## 5. Velocidad

El OCR local usa todos los núcleos de la PC que le permitas. Referencia medida sobre tu
expediente de 44 páginas, en una máquina de **2 núcleos**: **4 minutos y medio**.
En una PC de oficina de 4–8 núcleos baja a **1–2 minutos**.

Si quieres ajustarlo, antes de `python app.py` en el `.bat` puedes agregar:

    set OCR_CONCURRENCIA=6      (cuántas páginas lee a la vez; por defecto 4)
    set OCR_DPI=220             (resolución de la primera pasada)
    set OCR_RELECTURA=0         (desactiva la relectura en alta resolución: más rápido, menos exacto)

## 6. Varios expedientes de una vez

Arma un **ZIP con una carpeta por expediente**:

    lote_setiembre.zip
      ├── OS-10559/   (sus PDF adentro, se unen en orden alfabético)
      ├── OS-10560/
      └── OS-10561/

(También vale un ZIP con un PDF suelto por expediente: cada PDF es un expediente.)

Al subirlo aparece la tarjeta **"Varios expedientes de una vez"**: marca
*Tratarlos como expedientes separados* y ejecuta. Se procesan **uno tras otro** y al
terminar tienes:

- una **tabla** con cada expediente, su OS, cuántos riesgos confirmados y cuántos por revisar,
- **Ver detalle** para entrar a cualquiera con sus tarjetas, ubicaciones y medidas de control,
- **Descargar Excel del lote**: una hoja *Resumen* (un renglón por expediente) y una hoja
  *Riesgos* con todos los hallazgos de todos los expedientes, más base legal y deslinde.

## 7. Si algo falla

| Síntoma | Qué hacer |
|---|---|
| "No se encontró Python" | Reinstalar Python marcando *Add python.exe to PATH* |
| "No está instalado Tesseract" | Instalarlo con el idioma Spanish y volver a ejecutar el `.bat` |
| En *Sistema y respaldo* dice "falta el idioma español" | Reinstalar Tesseract marcando *Spanish* |
| El navegador no abre solo | Entrar a mano a `http://localhost:8080` |
| Va muy lento | Subir `OCR_CONCURRENCIA`, o apagar la relectura con `OCR_RELECTURA=0` |

## 8. Lo que no cambia

La exactitud depende del **escaneo**. Tus expedientes vienen a ~96 DPI; escaneando a
**300 DPI en escala de grises** la lectura sube sola, con cualquiera de los dos motores.
Ese sigue siendo el cambio que más rinde.
