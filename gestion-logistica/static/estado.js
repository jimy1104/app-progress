/* =====================================================================
   GESTIÓN DE LOGÍSTICA — interfaz "Estado"
   Solo presentación: carrusel, resumen animado, menús, íconos y ayuda.
   Lee los mismos datos que ya usa la app (GET /api/...) y llama a las
   funciones que ya existen (openRiesgosTablero, openCrearExcel, …).
   No cambia nada de app.js ni de lo que se guarda.
   ===================================================================== */
(function () {
  'use strict';

  var sinMovimiento = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function $(sel, ctx) { return (ctx || document).querySelector(sel); }
  function $$(sel, ctx) { return Array.prototype.slice.call((ctx || document).querySelectorAll(sel)); }
  function fmtInt(n) { return Number(n || 0).toLocaleString('es-PE'); }
  function fmtSoles(n) {
    n = Number(n || 0);
    if (n >= 1e6) return 'S/ ' + (n / 1e6).toLocaleString('es-PE', { maximumFractionDigits: 1 }) + ' millones';
    return 'S/ ' + n.toLocaleString('es-PE', { maximumFractionDigits: 0 });
  }
  async function traer(url) {
    try { var r = await fetch(url, { credentials: 'same-origin' }); return r.ok ? await r.json() : null; }
    catch (e) { return null; }
  }
  function plural(n, uno, varios) { return fmtInt(n) + ' ' + (Number(n) === 1 ? uno : varios); }

  /* ---------------- Íconos de línea (reemplazan los emojis de las tarjetas) ---------------- */
  var ICONOS = [
    [/selecci[oó]n|bases/i, '<path d="M14 6h20l8 8v28a3 3 0 0 1-3 3H14a3 3 0 0 1-3-3V9a3 3 0 0 1 3-3z"/><path d="M34 6v8h8M18 24h16M18 31h16M18 38h10"/>'],
    [/contratos menores|jur[ií]dica|empresa/i, '<path d="M8 42V14l14-6v34M22 42V18h18v24M4 42h40"/><path d="M13 18h4M13 25h4M13 32h4M27 24h6M27 31h6"/>'],
    [/ejecuci[oó]n|bienes$|servicios$/i, '<path d="M10 10h28v32H10z"/><path d="M16 20l4 4 8-8M16 33h16"/>'],
    [/locador|natural/i, '<circle cx="24" cy="16" r="7"/><path d="M10 42c0-8 6-13 14-13s14 5 14 13"/><path d="M33 8l4 4-4 4"/>'],
    [/almac[eé]n/i, '<path d="M6 18L24 8l18 10v24H6z"/><path d="M14 42V26h20v16M14 32h20M14 37h20"/>'],
    [/obra|consultor/i, '<path d="M6 42h36M10 42V22h10v20M26 42V14h12v28"/><path d="M4 22L15 12l11 10M30 18h4M30 24h4M30 30h4"/>']
  ];
  function iconoPara(texto) {
    for (var i = 0; i < ICONOS.length; i++) if (ICONOS[i][0].test(texto)) return ICONOS[i][1];
    return '<rect x="8" y="8" width="32" height="32" rx="6"/><path d="M16 24h16M24 16v16"/>';
  }
  function vestirTarjetas(grid) {
    $$('.proc-card', grid).forEach(function (card) {
      if (card.dataset.est) return;
      card.dataset.est = '1';
      var icono = $('.proc-icon', card);
      var titulo = ($('.proc-title', card) || {}).textContent || '';
      if (icono) {
        icono.setAttribute('aria-hidden', 'true');
        icono.innerHTML = '<svg viewBox="0 0 48 48">' + iconoPara(titulo) + '</svg>';
      }
    });
  }

  /* ---------------- Menús desplegables y menú de celular ---------------- */
  function menus() {
    var abiertos = [];
    function cerrarTodos(excepto) {
      $$('.est-desplegable.abierto').forEach(function (d) {
        if (d === excepto) return;
        d.classList.remove('abierto');
        $('.est-menu-btn', d).setAttribute('aria-expanded', 'false');
      });
    }
    $$('.est-desplegable').forEach(function (d) {
      var btn = $('.est-menu-btn', d);
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        var abrir = !d.classList.contains('abierto');
        cerrarTodos(d);
        d.classList.toggle('abierto', abrir);
        btn.setAttribute('aria-expanded', String(abrir));
      });
      // Al elegir una opción, el menú se cierra solo.
      $('.est-panel', d).addEventListener('click', function (e) {
        if (e.target.closest('button, a')) { cerrarTodos(); cerrarHamburguesa(); }
      });
    });
    document.addEventListener('click', function (e) { if (!e.target.closest('.est-desplegable')) cerrarTodos(); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') { cerrarTodos(); cerrarHamburguesa(); } });

    var hamb = $('.est-hamburguesa');
    function cerrarHamburguesa() {
      if (!hamb) return;
      document.body.classList.remove('est-menu-abierto');
      hamb.setAttribute('aria-expanded', 'false');
    }
    if (hamb) hamb.addEventListener('click', function () {
      var abrir = !document.body.classList.contains('est-menu-abierto');
      document.body.classList.toggle('est-menu-abierto', abrir);
      hamb.setAttribute('aria-expanded', String(abrir));
    });
  }

  /* ---------------- Atajos: data-ir (secciones) y data-abre (guías) ---------------- */
  function irA(destino) {
    var enInicio = $('#view-home') && $('#view-home').classList.contains('active');
    if (!enInicio && typeof window.goHome === 'function') window.goHome();
    var mapa = { inicio: null, subprocesos: '#estSubprocesos', ejecutar: '#estEjecutar', resumen: '#estResumen' };
    var sel = mapa[destino];
    setTimeout(function () {
      if (!sel) { window.scrollTo({ top: 0, behavior: sinMovimiento ? 'auto' : 'smooth' }); return; }
      var el = $(sel);
      if (el) el.scrollIntoView({ behavior: sinMovimiento ? 'auto' : 'smooth', block: 'start' });
    }, enInicio ? 0 : 60);
    $$('.est-tab').forEach(function (t) { t.classList.toggle('activa', t.dataset.ir === destino || (destino === 'resumen' && t.dataset.ir === 'inicio')); });
  }
  function abrirGuia(id) {
    var d = document.getElementById(id);
    if (!d) return;
    var enInicio = $('#view-home') && $('#view-home').classList.contains('active');
    if (!enInicio && typeof window.goHome === 'function') window.goHome();
    d.open = true;
    setTimeout(function () { d.scrollIntoView({ behavior: sinMovimiento ? 'auto' : 'smooth', block: 'start' }); }, 60);
  }
  function atajos() {
    document.addEventListener('click', function (e) {
      var ir = e.target.closest('[data-ir]');
      if (ir) { e.preventDefault(); irA(ir.dataset.ir); return; }
      var abre = e.target.closest('[data-abre]');
      if (abre) { e.preventDefault(); abrirGuia(abre.dataset.abre); }
    });
  }

  /* ---------------- Carrusel principal ---------------- */
  var carrusel = null;
  function iniciarCarrusel() {
    var hero = $('#estHero');
    if (!hero) return;
    var slides = $$('.est-slide', hero);
    var puntos = $('.est-puntos', hero);
    var actual = 0, timer = null, pausa = false;
    var DURACION = 7000;

    slides.forEach(function (s, i) {
      s.setAttribute('role', 'group');
      s.setAttribute('aria-roledescription', 'diapositiva');
      s.setAttribute('aria-label', (i + 1) + ' de ' + slides.length);
      var p = document.createElement('button');
      p.type = 'button';
      p.className = 'est-punto';
      p.setAttribute('role', 'tab');
      p.setAttribute('aria-label', 'Ir a: ' + (($('.est-kicker', s) || {}).textContent || (i + 1)));
      p.innerHTML = '<svg viewBox="0 0 36 36" aria-hidden="true"><circle cx="18" cy="18" r="16"/></svg><span>' + (i + 1) + '</span>';
      p.addEventListener('click', function () { mostrar(i, true); });
      puntos.appendChild(p);
    });

    function mostrar(i, manual) {
      actual = (i + slides.length) % slides.length;
      slides.forEach(function (s, k) {
        s.classList.toggle('activa', k === actual);
        s.setAttribute('aria-hidden', String(k !== actual));
        $$('button', s).forEach(function (b) { b.tabIndex = k === actual ? 0 : -1; });
      });
      $$('.est-punto', puntos).forEach(function (p, k) {
        p.classList.remove('corriendo');
        p.classList.toggle('activo', k === actual);
        p.setAttribute('aria-selected', String(k === actual));
      });
      programar();
    }
    function programar() {
      clearTimeout(timer);
      var p = $$('.est-punto', puntos)[actual];
      if (sinMovimiento || document.documentElement.dataset.motion === 'off') return;
      if (p) { void p.offsetWidth; p.classList.toggle('corriendo', !pausa); }
      if (!pausa) timer = setTimeout(function () { mostrar(actual + 1); }, DURACION);
    }
    function pausar(si) { pausa = si; hero.classList.toggle('en-pausa', si); programar(); }

    $('.est-hero-flecha.prev', hero).addEventListener('click', function () { mostrar(actual - 1, true); });
    $('.est-hero-flecha.next', hero).addEventListener('click', function () { mostrar(actual + 1, true); });
    hero.addEventListener('mouseenter', function () { pausar(true); });
    hero.addEventListener('mouseleave', function () { pausar(false); });
    hero.addEventListener('focusin', function () { pausar(true); });
    hero.addEventListener('focusout', function () { pausar(false); });
    hero.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowLeft') mostrar(actual - 1, true);
      if (e.key === 'ArrowRight') mostrar(actual + 1, true);
    });
    var x0 = null;
    hero.addEventListener('touchstart', function (e) { x0 = e.touches[0].clientX; }, { passive: true });
    hero.addEventListener('touchend', function (e) {
      if (x0 === null) return;
      var dx = e.changedTouches[0].clientX - x0;
      if (Math.abs(dx) > 40) mostrar(actual + (dx < 0 ? 1 : -1), true);
      x0 = null;
    });
    document.addEventListener('visibilitychange', function () { pausar(document.hidden); });

    mostrar(0);
    carrusel = { mostrar: mostrar, slides: slides, ir: function (tema) {
      var i = slides.findIndex(function (s) { return s.dataset.tema === tema; });
      if (i >= 0) mostrar(i, true);
    } };
  }

  /* ---------------- Números que cuentan ---------------- */
  function contar(el, valor, formato) {
    valor = Number(valor || 0);
    var pintar = function (v) { el.textContent = formato === 'soles' ? fmtSoles(v) : fmtInt(Math.round(v)); };
    if (sinMovimiento || document.documentElement.dataset.motion === 'off') { pintar(valor); return; }
    var t0 = performance.now(), dur = 1400;
    (function paso(t) {
      var k = Math.min((t - t0) / dur, 1);
      var e = 1 - Math.pow(1 - k, 3);
      pintar(valor * e);
      if (k < 1) requestAnimationFrame(paso);
    })(t0);
  }
  function alVerse(el, fn) {
    if (!('IntersectionObserver' in window)) { fn(); return; }
    var io = new IntersectionObserver(function (ents) {
      if (ents.some(function (x) { return x.isIntersecting; })) { io.disconnect(); fn(); }
    }, { threshold: 0.25 });
    io.observe(el);
  }

  /* ---------------- Gráfico: órdenes por año (barras apiladas) ---------------- */
  function grafico(porAnio) {
    var fig = $('#estGrafico');
    if (!fig) return;
    var caja = $('.est-barras', fig), tip = $('.est-tooltip', fig);
    var anios = Object.keys(porAnio || {}).sort();
    if (!anios.length) { fig.hidden = true; return; }
    var max = Math.max.apply(null, anios.map(function (a) { return (porAnio[a].empresas || 0) + (porAnio[a].locadores || 0); })) || 1;
    caja.innerHTML = '';
    anios.forEach(function (a, i) {
      var emp = porAnio[a].empresas || 0, loc = porAnio[a].locadores || 0, tot = emp + loc;
      var col = document.createElement('div');
      col.className = 'est-col';
      col.style.setProperty('--i', i);
      col.tabIndex = 0;
      col.setAttribute('aria-label', a + ': ' + fmtInt(tot) + ' órdenes (' + fmtInt(emp) + ' empresas, ' + fmtInt(loc) + ' locadores)');
      col.innerHTML =
        '<span class="est-col-total">' + fmtInt(tot) + '</span>' +
        '<span class="est-col-pila" style="--h:' + (tot / max * 100).toFixed(2) + '%">' +
          '<i class="c-loc" style="flex-grow:' + loc + '"></i>' +
          '<i class="c-emp" style="flex-grow:' + emp + '"></i>' +
        '</span>' +
        '<span class="est-col-anio">' + a + '</span>';
      function ver() {
        tip.hidden = false;
        tip.innerHTML = '<strong>' + a + '</strong><span><i class="c-emp"></i>Empresas <b>' + fmtInt(emp) + '</b></span>' +
          '<span><i class="c-loc"></i>Locadores <b>' + fmtInt(loc) + '</b></span><span>Total <b>' + fmtInt(tot) + '</b></span>';
        var r = col.getBoundingClientRect(), f = fig.getBoundingClientRect();
        tip.style.left = Math.min(Math.max(r.left - f.left + r.width / 2, 90), f.width - 90) + 'px';
        tip.style.top = (r.top - f.top) + 'px';
      }
      col.addEventListener('mouseenter', ver);
      col.addEventListener('focus', ver);
      col.addEventListener('mouseleave', function () { tip.hidden = true; });
      col.addEventListener('blur', function () { tip.hidden = true; });
      caja.appendChild(col);
    });
    alVerse(fig, function () { fig.classList.add('visible'); });
    var ver = document.createElement('button');
    ver.type = 'button';
    ver.className = 'est-ver-tabla';
    ver.dataset.abre = 'datosCargadosBox';
    ver.textContent = 'Ver en tabla →';
    $('figcaption', fig).appendChild(ver);
  }

  /* ---------------- Datos del resumen y del carrusel ---------------- */
  function poner(k, texto) { $$('[data-k="' + k + '"]').forEach(function (el) { el.textContent = texto; }); }
  function mostrarEl(k, si) { $$('[data-k="' + k + '"]').forEach(function (el) { el.hidden = !si; }); }

  async function cargarResumen() {
    if (!$('#estResumen') && !$('#estHero')) return;
    var resumen = await traer('/api/summary') || {};
    var obras = await traer('/api/obras/resumen') || {};
    var anios = (resumen.anios || []).slice().sort();
    poner('ordenes', fmtInt(resumen.total));
    poner('procesos', fmtInt(obras.total));
    poner('rango', anios.length ? ' (' + anios[0] + (anios.length > 1 ? '–' + anios[anios.length - 1] : '') + ')' : '');

    var valores = {
      ordenes: resumen.total,
      monto: (resumen.monto_empresas || 0) + (resumen.monto_locadores || 0),
      procesos: obras.total
    };

    if ($('[data-tema="riesgos"]') || $('[data-cuenta="riesgos"]')) {
      var rz = await traer('/api/riesgos/resumen') || {};
      var abiertos = rz.abiertos_riesgo || 0, revisar = rz.abiertos_revisar || 0;
      valores.riesgos = abiertos;
      if (abiertos > 0) {
        poner('riesgosTitulo', '¡Atención! ' + plural(abiertos, 'riesgo abierto', 'riesgos abiertos'));
        poner('riesgosTexto', 'Detectados en ' + plural(rz.expedientes, 'expediente cortado', 'expedientes cortados') +
          (revisar ? ', y ' + plural(revisar, 'punto más por revisar', 'puntos más por revisar') : '') + '. Revísalos y registra la medida de control.');
      } else {
        poner('riesgosTitulo', 'Sin riesgos abiertos');
        poner('riesgosTexto', rz.expedientes
          ? 'Los ' + plural(rz.expedientes, 'expediente cortado', 'expedientes cortados') + ' no tienen riesgos pendientes' + (revisar ? ', pero hay ' + plural(revisar, 'punto por revisar', 'puntos por revisar') : '') + '.'
          : 'Cuando se corten expedientes de Contratos Menores, Locadores o Selección, aquí verás sus riesgos.');
      }
      mostrarEl('riesgosAlerta', abiertos > 0);
      $$('[data-tema="riesgos"]').forEach(function (s) { s.classList.toggle('alerta', abiertos > 0); });
    }

    if ($('[data-tema="verificacion"]') || $('[data-cuenta="verificar"]')) {
      var vp = await traer('/api/verificacion/resumen') || {};
      valores.verificar = vp.alertas || 0;
      if (vp.alertas) {
        poner('vpTitulo', plural(vp.alertas, 'expediente necesita', 'expedientes necesitan') + ' atención');
        poner('vpTexto', fmtInt(vp.vencidos) + ' vencidos y ' + fmtInt(vp.por_vencer) + ' por vencer, de ' + plural(vp.pendientes, 'pendiente', 'pendientes') +
          '. El plazo es de ' + (vp.plazo_dias || 10) + ' días hábiles.');
      } else {
        poner('vpTitulo', 'Plazos al día');
        poner('vpTexto', (vp.pendientes ? plural(vp.pendientes, 'expediente pendiente', 'expedientes pendientes') + ', ninguno por vencer.' : 'No hay expedientes pendientes de verificación.') +
          ' El plazo es de ' + (vp.plazo_dias || 10) + ' días hábiles.');
      }
      mostrarEl('vpAlerta', (vp.alertas || 0) > 0);
      $$('[data-tema="verificacion"]').forEach(function (s) { s.classList.toggle('alerta', (vp.vencidos || 0) > 0); });
    }

    if ($('[data-tema="bandeja"]')) {
      var bj = await traer('/api/bandeja') || {};
      var pend = (bj.resumen && bj.resumen.pendientes) || 0;
      poner('bandejaTitulo', pend ? plural(pend, 'escaneo espera', 'escaneos esperan') + ' su corte' : 'Bandeja al día');
      poner('bandejaTexto', pend
        ? 'Los trabajadores dejaron expedientes escaneados. Córtalos para engancharlos a su orden.'
        : 'No hay escaneos pendientes. Cuando un trabajador entregue uno, aparecerá aquí.');
    }

    $$('[data-cuenta]').forEach(function (el) {
      var k = el.dataset.cuenta;
      if (!(k in valores)) return;
      alVerse(el, function () { contar(el, valores[k], el.dataset.formato); });
    });
    grafico(resumen.por_anio);
  }

  /* ---------------- Carrusel de tarjetas de subprocesos ---------------- */
  function carruselTarjetas() {
    var envol = $('.est-carrusel');
    if (!envol) return;
    var grid = $('#cardGrid', envol);
    function paso() { return Math.max(grid.clientWidth * 0.8, 240); }
    $('.est-carrusel-flecha.prev', envol).addEventListener('click', function () { grid.scrollBy({ left: -paso(), behavior: 'smooth' }); });
    $('.est-carrusel-flecha.next', envol).addEventListener('click', function () { grid.scrollBy({ left: paso(), behavior: 'smooth' }); });
    function flechas() {
      var hay = grid.scrollWidth > grid.clientWidth + 4;
      envol.classList.toggle('con-flechas', hay);
      $('.est-carrusel-flecha.prev', envol).disabled = grid.scrollLeft < 4;
      $('.est-carrusel-flecha.next', envol).disabled = grid.scrollLeft + grid.clientWidth > grid.scrollWidth - 4;
    }
    grid.addEventListener('scroll', flechas, { passive: true });
    window.addEventListener('resize', flechas);
    return flechas;
  }

  /* Menú «Subprocesos» y pie de página: se arman con las mismas tarjetas */
  function listasDeSubprocesos() {
    var grid = $('#cardGrid');
    var menu = $('#estMenuSubprocesos'), pie = $('#estPieSubprocesos');
    if (!grid) return;
    var cards = $$('.proc-card', grid);
    if (!cards.length) return;
    if (menu) menu.innerHTML = '';
    if (pie) pie.innerHTML = '';
    cards.forEach(function (card) {
      var titulo = ($('.proc-title', card) || {}).textContent || '';
      var sub = ($('.proc-sub', card) || {}).textContent || '';
      if (menu) {
        var b = document.createElement('button');
        b.type = 'button';
        b.className = 'back-btn est-item est-item-sp';
        b.innerHTML = '<span class="est-item-ico"><svg viewBox="0 0 48 48">' + iconoPara(titulo) + '</svg></span><span><strong></strong><small></small></span>';
        $('strong', b).textContent = titulo;
        $('small', b).textContent = sub;
        b.addEventListener('click', function () { card.click(); window.scrollTo({ top: 0 }); });
        menu.appendChild(b);
      }
      if (pie) {
        var li = document.createElement('li');
        var a = document.createElement('button');
        a.type = 'button';
        a.textContent = titulo;
        a.addEventListener('click', function () { card.click(); window.scrollTo({ top: 0 }); });
        li.appendChild(a);
        pie.appendChild(li);
      }
    });
  }

  /* ---------------- Aviso sumado en el menú «Control» ---------------- */
  function sumaControl() {
    var total = $('#estControlBadge');
    if (!total) return;
    var ids = ['riesgosBadge', 'vpBadge', 'bandejaBadge'];
    function sumar() {
      var n = 0;
      ids.forEach(function (id) {
        var b = document.getElementById(id);
        if (b && b.style.display !== 'none') n += parseInt(b.textContent, 10) || 0;
      });
      total.textContent = n;
      total.hidden = !n;
    }
    ids.forEach(function (id) {
      var b = document.getElementById(id);
      if (b) new MutationObserver(sumar).observe(b, { attributes: true, childList: true, characterData: true, subtree: true });
    });
    sumar();
  }

  /* ---------------- Ayuda flotante ---------------- */
  function ayuda() {
    if (document.body.classList.contains('ingreso')) return;
    var esInicio = !!$('#view-home');
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'est-ayuda';
    btn.setAttribute('aria-label', 'Ayuda');
    btn.setAttribute('aria-expanded', 'false');
    btn.innerHTML = '<svg viewBox="0 0 48 48" aria-hidden="true"><circle cx="24" cy="24" r="22"/><path d="M18 19a6 6 0 1 1 8.5 5.4c-1.6.8-2.5 2-2.5 3.6v1.5"/><circle cx="24" cy="35" r="1.8"/></svg>';
    var burbuja = document.createElement('span');
    burbuja.className = 'est-ayuda-burbuja';
    burbuja.textContent = '¿Te ayudo?';
    var panel = document.createElement('div');
    panel.className = 'est-ayuda-panel';
    panel.hidden = true;
    var opciones = [];
    if (esInicio) {
      opciones.push(['🧭', 'Cómo funciona (guía rápida)', function () { abrirGuia('guiaRapidaBox'); }]);
      opciones.push(['📊', 'Ver el resumen', function () { irA('resumen'); }]);
      if (typeof window.openCrearExcel === 'function') opciones.push(['📤', 'Subir un Excel', function () { window.openCrearExcel(); }]);
      if ($('#riesgosBtn')) opciones.push(['⚠️', 'Ver los riesgos', function () { window.openRiesgosTablero(); }]);
    }
    opciones.push(['🌓', 'Cambiar a tema claro u oscuro', function () { var t = $('#themeToggle'); if (t) t.click(); }]);
    panel.innerHTML = '<strong>¿Qué necesitas hacer?</strong>';
    opciones.forEach(function (o) {
      var b = document.createElement('button');
      b.type = 'button';
      b.innerHTML = '<span aria-hidden="true">' + o[0] + '</span>';
      b.appendChild(document.createTextNode(o[1]));
      b.addEventListener('click', function () { cerrar(); o[2](); });
      panel.appendChild(b);
    });
    function cerrar() { panel.hidden = true; btn.setAttribute('aria-expanded', 'false'); }
    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      panel.hidden = !panel.hidden;
      btn.setAttribute('aria-expanded', String(!panel.hidden));
      burbuja.remove();
    });
    document.addEventListener('click', function (e) { if (!panel.hidden && !panel.contains(e.target)) cerrar(); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') cerrar(); });
    document.body.appendChild(panel);
    document.body.appendChild(btn);
    document.body.appendChild(burbuja);
    setTimeout(function () { burbuja.remove(); }, 9000);
  }

  /* ---------------- Aparición al bajar ---------------- */
  function apariciones() {
    var els = $$('.est-titulo, .est-kpi, .est-banner, .est-pie-cols > div, .console');
    els.forEach(function (el) { el.classList.add('est-aparece'); });
    if (!('IntersectionObserver' in window) || sinMovimiento) { els.forEach(function (el) { el.classList.add('visible'); }); return; }
    var io = new IntersectionObserver(function (ents) {
      ents.forEach(function (x) { if (x.isIntersecting) { x.target.classList.add('visible'); io.unobserve(x.target); } });
    }, { threshold: 0.12 });
    els.forEach(function (el) { io.observe(el); });
  }

  /* ---------------- Arranque ---------------- */
  function iniciar() {
    menus();
    atajos();
    iniciarCarrusel();
    var flechas = carruselTarjetas();
    ['cardGrid', 'subcardsGrid'].forEach(function (id) {
      var g = document.getElementById(id);
      if (!g) return;
      new MutationObserver(function () {
        vestirTarjetas(g);
        if (id === 'cardGrid') { listasDeSubprocesos(); if (flechas) flechas(); }
      }).observe(g, { childList: true });
      vestirTarjetas(g);
    });
    sumaControl();
    cargarResumen();
    ayuda();
    apariciones();
    // Volver al inicio con «← Volver al inicio»: la pestaña «Inicio» queda marcada.
    var back = $('#backBtn');
    if (back) new MutationObserver(function () {
      document.body.classList.toggle('est-en-detalle', back.style.display !== 'none');
    }).observe(back, { attributes: true, attributeFilter: ['style'] });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', iniciar);
  else iniciar();
})();
