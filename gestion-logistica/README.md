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
