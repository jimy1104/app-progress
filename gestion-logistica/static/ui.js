/* =====================================================================
   GESTIÓN DE LOGÍSTICA — CAPA VISUAL
   Solo presentación: el panel «Personalizar», el video de fondo, la luz
   que sigue al puntero y las animaciones de los títulos. No toca ninguna
   función de la app (app.js / empleado.js siguen igual).
   ===================================================================== */
(function () {
  'use strict';

  var root = document.documentElement;
  var PREFS_KEY = 'gl_ui';
  var THEME_KEY = 'ecl_theme'; // la misma llave que ya usa el botón «🌓 Tema»
  var TIP_KEY = 'gl_tip_visto';
  var VIDEO_SRC = 'https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260328_115001_bcdaa3b4-03de-47e7-ad63-ae3e392c32d4.mp4';

  var DEFAULTS = { accent: 'aurora', text: 'normal', density: 'comoda', motion: true, contrast: false, video: true };

  function sistemaSinMovimiento() {
    return !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  }

  function leer() {
    var p = {};
    try { p = JSON.parse(localStorage.getItem(PREFS_KEY) || '{}') || {}; } catch (e) {}
    var out = {};
    for (var k in DEFAULTS) out[k] = (k in p) ? p[k] : DEFAULTS[k];
    if (!('motion' in p) && sistemaSinMovimiento()) out.motion = false;
    return out;
  }
  function guardar(p) {
    try { localStorage.setItem(PREFS_KEY, JSON.stringify(p)); } catch (e) {}
  }

  var prefs = leer();

  function aplicar() {
    root.setAttribute('data-accent', prefs.accent);
    root.setAttribute('data-text', prefs.text);
    root.setAttribute('data-density', prefs.density);
    root.setAttribute('data-motion', prefs.motion ? 'on' : 'off');
    root.setAttribute('data-contrast', prefs.contrast ? 'alto' : 'normal');
    if (!root.getAttribute('data-theme')) {
      var t = null;
      try { t = localStorage.getItem(THEME_KEY); } catch (e) {}
      root.setAttribute('data-theme', t || 'dark');
    }
    videos.forEach(function (v) { v.sync(); });
  }

  /* ------------------------------------------------------------------
     VIDEO EN BUCLE con fundido hecho a mano (sin transiciones CSS):
     aparece en 500 ms al cargar, se desvanece 0,55 s antes de terminar,
     y al acabar vuelve al inicio y aparece de nuevo.
     ------------------------------------------------------------------ */
  var videos = [];
  function crearVideo(className, parent, before) {
    var v = document.createElement('video');
    v.className = className;
    v.muted = true;
    v.defaultMuted = true;
    v.playsInline = true;
    v.setAttribute('playsinline', '');
    v.setAttribute('aria-hidden', 'true');
    v.preload = 'auto';
    v.style.opacity = '0';

    var frame = null;
    var fadingOut = false;
    var restart = null;

    function cancelar() { if (frame !== null) { cancelAnimationFrame(frame); frame = null; } }
    function fundir(destino) {
      cancelar();
      var desde = parseFloat(v.style.opacity || '0');
      var inicio = performance.now();
      function paso(ahora) {
        var t = Math.min((ahora - inicio) / 500, 1);
        v.style.opacity = String(desde + (destino - desde) * t);
        frame = t < 1 ? requestAnimationFrame(paso) : null;
      }
      frame = requestAnimationFrame(paso);
    }

    v.addEventListener('loadeddata', function () { fadingOut = false; fundir(1); });
    v.addEventListener('timeupdate', function () {
      if (!v.duration || fadingOut) return;
      if (v.duration - v.currentTime <= 0.55) { fadingOut = true; fundir(0); }
    });
    v.addEventListener('ended', function () {
      cancelar();
      v.style.opacity = '0';
      restart = setTimeout(function () {
        v.currentTime = 0;
        var pr = v.play(); if (pr && pr.catch) pr.catch(function () {});
        fadingOut = false;
        fundir(1);
      }, 100);
    });
    // Sin internet (app de escritorio): se queda la luz de aurora y listo.
    v.addEventListener('error', function () { v.style.display = 'none'; });

    var montado = false;
    var item = {
      sync: function () {
        if (prefs.video) {
          if (!montado) {
            montado = true;
            v.src = VIDEO_SRC;
            if (before) parent.insertBefore(v, before); else parent.appendChild(v);
          }
          var pr = v.play(); if (pr && pr.catch) pr.catch(function () {});
        } else if (montado) {
          v.pause();
          cancelar();
          clearTimeout(restart);
          fadingOut = false;
          fundir(0);
        }
      }
    };
    videos.push(item);
    return item;
  }

  /* ------------------------------------------------------------------
     TÍTULO: letras que aparecen una por una; la última palabra en
     cursiva con degradado («Gestión de Logística», «Ingresar»…)
     ------------------------------------------------------------------ */
  function animarTitulo(h1, conCursiva) {
    if (!h1 || h1.children.length) return;
    var texto = h1.textContent.trim();
    if (!texto) return;
    var palabras = texto.split(' ');
    var ultima = conCursiva ? palabras.pop() : null;
    h1.setAttribute('aria-label', texto);
    h1.textContent = '';
    var i = 0;
    // Cada palabra va en su propia caja para que la línea nunca se corte
    // a mitad de palabra en pantallas angostas.
    function letras(dest, str) {
      str.split(' ').forEach(function (palabra, n) {
        if (n) dest.appendChild(document.createTextNode(' '));
        if (!palabra) return;
        var caja = document.createElement('span');
        caja.style.whiteSpace = 'nowrap';
        caja.style.display = 'inline-block';
        for (var c = 0; c < palabra.length; c++) {
          var s = document.createElement('span');
          s.className = 'gl-letter';
          s.setAttribute('aria-hidden', 'true');
          s.style.animationDelay = (120 + i * 38) + 'ms';
          s.textContent = palabra[c];
          caja.appendChild(s);
          i++;
        }
        dest.appendChild(caja);
      });
    }
    letras(h1, palabras.join(' ') + (ultima && palabras.length ? ' ' : ''));
    if (ultima) {
      var em = document.createElement('em');
      em.setAttribute('aria-hidden', 'true');
      var wrap = document.createElement('span');
      wrap.className = 'gl-letter';
      wrap.style.animationDelay = (120 + i * 38) + 'ms';
      wrap.textContent = ultima;
      em.appendChild(wrap);
      h1.appendChild(em);
    }
  }

  /* ------------------------------------------------------------------
     LUZ QUE SIGUE AL PUNTERO (tarjetas, consola, pantalla completa)
     ------------------------------------------------------------------ */
  function luz() {
    var ambient = document.createElement('div');
    ambient.className = 'gl-ambient';
    ambient.setAttribute('aria-hidden', 'true');
    document.body.appendChild(ambient);

    var pendiente = false, x = 0, y = 0, objetivo = null;
    function pintar() {
      pendiente = false;
      ambient.style.setProperty('--px', x + 'px');
      ambient.style.setProperty('--py', y + 'px');
      if (objetivo) {
        var r = objetivo.getBoundingClientRect();
        objetivo.style.setProperty('--mx', (x - r.left) + 'px');
        objetivo.style.setProperty('--my', (y - r.top) + 'px');
      }
    }
    window.addEventListener('pointermove', function (e) {
      x = e.clientX; y = e.clientY;
      objetivo = e.target && e.target.closest ? e.target.closest('.proc-card, .console, .area-card') : null;
      if (!pendiente) { pendiente = true; requestAnimationFrame(pintar); }
    }, { passive: true });
  }

  /* ------------------------------------------------------------------
     PANEL «PERSONALIZAR»
     ------------------------------------------------------------------ */
  var ACENTOS = [
    { id: 'aurora', nombre: 'Aurora', c: ['#5EEAD4', '#A78BFA'] },
    { id: 'glaciar', nombre: 'Glaciar', c: ['#7DD3FC', '#818CF8'] },
    { id: 'jade', nombre: 'Jade', c: ['#34D399', '#A3E635'] },
    { id: 'indigo', nombre: 'Índigo', c: ['#A5B4FC', '#F0ABFC'] }
  ];

  function el(tag, attrs, hijos) {
    var n = document.createElement(tag);
    for (var k in (attrs || {})) {
      if (k === 'text') n.textContent = attrs[k];
      else if (k === 'on') { for (var ev in attrs.on) n.addEventListener(ev, attrs.on[ev]); }
      else n.setAttribute(k, attrs[k]);
    }
    (hijos || []).forEach(function (h) { if (h) n.appendChild(h); });
    return n;
  }

  function titulo(nombre, ayuda, control) {
    return el('div', { 'class': 'gl-sec-title' }, [
      el('div', {}, [el('span', { text: nombre }), el('small', { text: ayuda })]),
      control
    ]);
  }

  function segmentado(etiqueta, opciones, valor, alElegir) {
    var g = el('div', { 'class': 'gl-seg', role: 'radiogroup', 'aria-label': etiqueta });
    opciones.forEach(function (o) {
      g.appendChild(el('button', {
        type: 'button', role: 'radio', 'aria-checked': String(o[0] === valor),
        'aria-label': o[2] || o[1], text: o[1],
        on: { click: function () { alElegir(o[0]); } }
      }));
    });
    return g;
  }

  function interruptor(etiqueta, valor, alCambiar) {
    return el('button', {
      type: 'button', 'class': 'gl-switch', role: 'switch', 'aria-checked': String(!!valor), 'aria-label': etiqueta,
      on: { click: function () { alCambiar(!valor); } }
    });
  }

  function panel() {
    var abierto = false;
    var fab = el('button', { type: 'button', 'class': 'gl-fab', 'aria-expanded': 'false', 'aria-label': 'Personalizar' }, [
      el('span', { 'class': 'gl-fab-dot', 'aria-hidden': 'true', text: '✦' }),
      el('span', { 'class': 'gl-fab-label', text: 'Personalizar' })
    ]);
    var caja = el('div', { 'class': 'gl-panel', role: 'dialog', 'aria-label': 'Personalizar', hidden: '' });
    document.body.appendChild(caja);
    document.body.appendChild(fab);

    function cambiar(k, v) { prefs[k] = v; guardar(prefs); aplicar(); pintar(); }

    function pintar() {
      caja.textContent = '';
      var tema = root.getAttribute('data-theme') || 'dark';

      caja.appendChild(el('div', { 'class': 'gl-panel-head' }, [
        el('strong', { text: 'Hazlo a tu gusto' }),
        el('button', { type: 'button', text: '↺ Restablecer', on: { click: function () {
          prefs = JSON.parse(JSON.stringify(DEFAULTS));
          if (sistemaSinMovimiento()) prefs.motion = false;
          guardar(prefs); aplicar(); pintar();
        } } })
      ]));

      var sw = el('div', { 'class': 'gl-swatches' });
      ACENTOS.forEach(function (a) {
        sw.appendChild(el('button', {
          type: 'button', 'class': 'gl-swatch', 'aria-pressed': String(prefs.accent === a.id),
          on: { click: function () { cambiar('accent', a.id); } }
        }, [
          el('i', { style: 'background: conic-gradient(from 200deg, ' + a.c[0] + ', ' + a.c[1] + ', ' + a.c[0] + ')' }),
          document.createTextNode(a.nombre)
        ]));
      });
      caja.appendChild(el('div', { 'class': 'gl-sec' }, [titulo('Color', 'Rojo, ámbar y verde siguen marcando riesgo, alerta y conforme', null), sw]));

      caja.appendChild(el('div', { 'class': 'gl-sec' }, [titulo('Tema', 'Oscuro de cine o claro de día',
        segmentado('Tema', [['dark', 'Oscuro'], ['light', 'Claro']], tema, function (v) {
          root.setAttribute('data-theme', v);
          try { localStorage.setItem(THEME_KEY, v); } catch (e) {}
          pintar();
        }))]));

      caja.appendChild(el('div', { 'class': 'gl-sec' }, [titulo('Tamaño de letra', 'Todo crece junto, nada se descuadra',
        segmentado('Tamaño de letra', [['normal', 'A', 'Normal'], ['grande', 'A+', 'Grande'], ['muy-grande', 'A++', 'Muy grande']], prefs.text, function (v) { cambiar('text', v); }))]));

      caja.appendChild(el('div', { 'class': 'gl-sec' }, [titulo('Tablas', 'Compacta muestra más filas a la vez',
        segmentado('Densidad de tablas', [['comoda', 'Cómoda'], ['compacta', 'Compacta']], prefs.density, function (v) { cambiar('density', v); }))]));

      caja.appendChild(el('div', { 'class': 'gl-sec' }, [titulo('Animaciones', 'Movimientos y efectos de luz',
        interruptor('Animaciones', prefs.motion, function (v) { cambiar('motion', v); }))]));

      caja.appendChild(el('div', { 'class': 'gl-sec' }, [titulo('Alto contraste', 'Letras y bordes más marcados',
        interruptor('Alto contraste', prefs.contrast, function (v) { cambiar('contrast', v); }))]));

      caja.appendChild(el('div', { 'class': 'gl-sec' }, [titulo('Video de fondo', 'Apágalo si la conexión es lenta',
        interruptor('Video de fondo', prefs.video, function (v) { cambiar('video', v); }))]));
    }

    function abrir(si) {
      abierto = si;
      if (si) { pintar(); caja.removeAttribute('hidden'); cerrarTip(true); }
      else caja.setAttribute('hidden', '');
      fab.setAttribute('aria-expanded', String(si));
      fab.querySelector('.gl-fab-dot').textContent = si ? '✕' : '✦';
      fab.querySelector('.gl-fab-label').textContent = si ? 'Cerrar' : 'Personalizar';
    }
    fab.addEventListener('click', function () { abrir(!abierto); });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && abierto) { abrir(false); fab.focus(); }
    });
    document.addEventListener('mousedown', function (e) {
      if (abierto && !caja.contains(e.target) && !fab.contains(e.target)) abrir(false);
    });
    // El botón «🌓 Tema» de la cabecera también cambia el tema: el panel lo refleja.
    new MutationObserver(function () { if (abierto) pintar(); })
      .observe(root, { attributes: true, attributeFilter: ['data-theme'] });

    // Primera visita: un aviso corto que señala el botón.
    var tip = null;
    function cerrarTip(recordar) {
      if (tip) { tip.remove(); tip = null; fab.classList.remove('pulsa'); }
      if (recordar) { try { localStorage.setItem(TIP_KEY, '1'); } catch (e) {} }
    }
    var visto = false;
    try { visto = !!localStorage.getItem(TIP_KEY); } catch (e) {}
    if (!visto) {
      setTimeout(function () {
        if (abierto) return;
        tip = el('div', { 'class': 'gl-tip', role: 'note' }, [
          el('b', { text: 'Nuevo: ' }),
          document.createTextNode('elige colores, tamaño de letra, tema y más desde aquí.'),
          el('button', { type: 'button', 'aria-label': 'Cerrar aviso', text: '×', on: { click: function () { cerrarTip(true); } } })
        ]);
        document.body.appendChild(tip);
        fab.classList.add('pulsa');
        setTimeout(function () { cerrarTip(true); }, 14000);
      }, 2600);
    }
  }

  /* ------------------------------------------------------------------
     ARRANQUE
     ------------------------------------------------------------------ */
  aplicar();

  function iniciar() {
    var body = document.body;
    var esIngreso = body.classList.contains('gl-login');

    if (esIngreso) {
      // Franjas de cine que se abren
      if (prefs.motion) {
        body.appendChild(el('div', { 'class': 'gl-letterbox top', 'aria-hidden': 'true' }));
        body.appendChild(el('div', { 'class': 'gl-letterbox bottom', 'aria-hidden': 'true' }));
      }
      var veil = el('div', { 'class': 'gl-login-veil', 'aria-hidden': 'true' });
      body.insertBefore(veil, body.firstChild);
      crearVideo('gl-login-video', body, veil);
      animarTitulo(document.querySelector('.login-card h1'), true);
    } else {
      var cab = document.querySelector('.masthead');
      if (cab) {
        var velo = el('div', { 'class': 'gl-video-veil', 'aria-hidden': 'true' });
        cab.insertBefore(velo, cab.firstChild);
        crearVideo('gl-video', cab, velo);
        animarTitulo(cab.querySelector('h1'), true);
      }
    }
    luz();
    panel();
    videos.forEach(function (v) { v.sync(); });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', iniciar);
  else iniciar();
})();
