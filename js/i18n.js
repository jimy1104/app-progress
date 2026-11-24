// Interface strings. The UI follows the native language of the active profile.
const S = {
  es: {
    load: 'Cargar vídeo', settings: 'Ajustes', help: 'Ayuda',
    emptyTitle: 'Practica shadowing con cualquier película',
    emptyText: 'Carga un vídeo (archivo, YouTube o enlace directo) y sus subtítulos. Luego escucha, repite, grábate, traduce y analiza la gramática de cada frase.',
    tryDemo: 'Probar demo (voz sintética)',
    speakLine: 'Escuchar la frase con voz sintética (lenta)', saveSentence: 'Guardar frase', aiExplain: 'Explicar con IA', fullscreen: 'Pantalla completa',
    prevLine: 'Frase anterior (A)', repeatLine: 'Repetir frase (S)', playPause: 'Reproducir / pausa (Espacio)', nextLine: 'Frase siguiente (D)',
    mode: 'Modo', record: 'Grabarme (R)', playMine: 'Escuchar mi grabación (P)', compare: 'Original y después mi voz (C)',
    myRecording: 'Mi grabación', translateYourself: 'Tradúcelo tú', translateHint: 'Escribe en tu idioma lo que dice la frase y compáralo.',
    check: 'Comprobar', tabSubs: 'Subtítulos', tabGrammar: 'Gramática', tabSaved: 'Guardados', tabRoutine: 'Rutina', tabProgress: 'Progreso',
    searchSubs: 'Buscar en subtítulos', translateAll: 'Traducir todo', words: 'Palabras', sentences: 'Frases', review: 'Repasar', exportAnki: 'Exportar (Anki)',
    loadTitle: 'Cargar vídeo y subtítulos', srcFile: 'Archivo del ordenador', srcUrl: 'Enlace', srcTts: 'Solo texto (voz)',
    videoFile: 'Vídeo o audio (mp4, webm, mkv, mp3…)',
    fileHint: 'El archivo no se sube a ningún servidor: se reproduce en tu navegador. Así puedes usar películas completas sin límite de tamaño.',
    videoUrl: 'YouTube, enlace directo .mp4/.webm/.m3u8 o Azure Blob',
    urlHint: 'Funcionan: <b>YouTube</b> y enlaces directos a archivos de vídeo (por ejemplo tu Azure Blob Storage). Plataformas como Bilibili, Netflix o Disney+ no permiten controlar su reproductor desde otra web: descarga el vídeo o usa el archivo local y sus subtítulos .srt.',
    ttsHint: 'Sin vídeo: una voz sintética lee cada frase. Útil para practicar con transcripciones, canciones o textos.',
    subsFile: 'Subtítulos del idioma que aprendes (.srt, .vtt, .ass, .txt)', pasteSubs: '…o pega el texto de los subtítulos',
    subs2File: 'Subtítulos en tu idioma (opcional; si no, se traducen automáticamente)', title: 'Título', cancel: 'Cancelar', start: 'Empezar',
    profiles: 'Perfiles (2 personas)', aiTitle: 'Asistente IA (opcional)',
    aiHint: 'Con una clave de la API de Claude obtienes explicaciones gramaticales profundas, respuestas a preguntas y ejemplos a medida. Sin clave, la app funciona igual con su motor gramatical integrado.',
    apiKey: 'Clave API de Anthropic', aiModel: 'Modelo', aiWarn: 'La clave se guarda solo en este navegador. No la uses en ordenadores compartidos.',
    data: 'Datos', exportData: 'Exportar copia (JSON)', importData: 'Importar copia', resetData: 'Borrar todo', save: 'Guardar',
    aiAskPh: 'Pregunta lo que quieras sobre esta frase…', ask: 'Preguntar',
    // modes
    m_watch: '👀 Ver con subtítulos', m_mumble: '🤫 Mumbling (murmurar)', m_overlap: '📖 Overlapping (leer a la vez)',
    m_shadow_line: '🗣 Shadowing frase a frase', m_shadow_full: '🏃 Shadowing continuo', m_record: '🎙 Grabar y comparar', m_translate: '🌐 Traducir cada frase',
    // toggles
    t_autoPause: 'Pausa al final de cada frase', t_loop: 'Repetir frase', t_times: 'veces', t_autoResume: 'Continuar sola tras', t_gap: 'pausa ×',
    t_prevBtn: 'Botón retroceder', t_hide: 'Ocultar texto', t_trans: 'Traducción', t_blur: 'Traducción borrosa', t_karaoke: 'Karaoke',
    t_stress: 'Mapa de acento', t_autoRec: 'Grabar en la pausa', t_overlayRec: 'Grabar encima (auriculares)', t_offset: 'Sincronía',
    // misc
    line: 'Frase', of: 'de', noSubs: 'Sin subtítulos cargados', saved: 'Guardado', removed: 'Eliminado', copied: 'Copiado',
    meaning: 'Significado', definition: 'Definición (inglés)', examples: 'Ejemplos', fromVideo: 'En el vídeo', partOf: 'Forma parte de',
    listen: 'Escuchar', saveWord: 'Guardar palabra', unsave: 'Quitar', loading: 'Cargando…', notFound: 'No se encontró en el diccionario.',
    grammarOf: 'Gramática de la frase', noGrammar: 'No se detectaron estructuras especiales. Prueba con «Explicar con IA».',
    connected: 'Habla conectada (cómo suena de verdad)', intonation: 'Entonación', corpusTitle: 'Gramática de todo el vídeo',
    corpusHint: 'Pulsa una estructura para ver todas las frases del vídeo que la usan.', seeAll: 'Ver todas las frases con esta estructura',
    filterOn: 'Filtrando por', clear: 'Quitar filtro', mergedNext: 'Unida con la siguiente línea para analizar la oración completa.',
    recNoMic: 'No se pudo acceder al micrófono.', recording: 'Grabando…', yourDur: 'Tu voz', origDur: 'Original', recognized: 'Lo que se entendió',
    noRecog: 'Tu navegador no reconoce voz (usa Chrome o Edge para la puntuación).', score: 'coincidencia',
    yourTrans: 'Tu traducción', refTrans: 'Traducción de referencia', similarity: 'similitud', writeFirst: 'Escribe primero tu traducción.',
    nothingSaved: 'Todavía no has guardado nada. Pasa el ratón por una palabra y pulsa ☆.', show: 'Mostrar', know: 'Lo sé', again: 'Otra vez', jump: 'Ir a la frase',
    reviewDone: '¡Repaso terminado!', library: 'Recientes', open: 'Abrir', del: 'Borrar', reselect: 'Vuelve a elegir el archivo de vídeo',
    needSubs: 'Añade un archivo de subtítulos o pega el texto.', needVideo: 'Elige un vídeo o un enlace.', badUrl: 'Este enlace no se puede controlar desde aquí.',
    unsupportedSite: 'Este sitio (por ejemplo Bilibili) no permite controlar su reproductor desde otra web. Descarga el vídeo y cárgalo como archivo, o sube el archivo a Azure Blob Storage y pega el enlace directo.',
    translating: 'Traduciendo…', translated: 'Traducción lista', transFail: 'No se pudo traducir (sin conexión o límite alcanzado).',
    aiNoKey: 'Añade tu clave de la API en Ajustes para usar la IA.', aiThinking: 'La IA está analizando la frase…', aiError: 'Error de la IA',
    literal: 'Traducción literal', natural: 'Traducción natural', vocab: 'Vocabulario', pronunciation: 'Pronunciación', culture: 'Contexto / uso',
    stLines: 'frases practicadas', stRec: 'grabaciones', stMin: 'minutos de práctica', stStreak: 'días seguidos', stWords: 'palabras guardadas', stTrans: 'traducción media',
    last4w: 'Últimas 4 semanas', routineTitle: 'Rutina de shadowing (≈15 min por clip)', useMode: 'Activar este modo', resetRoutine: 'Reiniciar rutina',
    profileName: 'Nombre', nativeLang: 'Idioma nativo', targetLang: 'Idioma que aprende', imported: 'Copia importada', confirmReset: '¿Borrar todos los datos de ambos perfiles?',
    mistakesTitle: 'Errores frecuentes',
    demoTitle: 'Demo — Shadowing', subsLoaded: 'subtítulos cargados', untimed: 'Texto sin tiempos: se leerá con voz sintética.',
    speakSlow: 'Lento', tags_q: 'pregunta',
  },
  ar: {
    load: 'تحميل فيديو', settings: 'الإعدادات', help: 'مساعدة',
    emptyTitle: 'تدرّب على تقنية الشادوينغ مع أي فيلم',
    emptyText: 'حمّل فيديو (ملف، يوتيوب أو رابط مباشر) مع ترجمته. ثم استمع، كرّر، سجّل صوتك، ترجم وحلّل قواعد كل جملة.',
    tryDemo: 'جرّب العرض (صوت اصطناعي)',
    speakLine: 'استمع للجملة بصوت اصطناعي (بطيء)', saveSentence: 'حفظ الجملة', aiExplain: 'شرح بالذكاء الاصطناعي', fullscreen: 'ملء الشاشة',
    prevLine: 'الجملة السابقة (A)', repeatLine: 'إعادة الجملة (S)', playPause: 'تشغيل / إيقاف (مسافة)', nextLine: 'الجملة التالية (D)',
    mode: 'الوضع', record: 'سجّل صوتك (R)', playMine: 'استمع لتسجيلك (P)', compare: 'الأصل ثم صوتك (C)',
    myRecording: 'تسجيلي', translateYourself: 'ترجمها بنفسك', translateHint: 'اكتب بلغتك معنى الجملة ثم قارن.',
    check: 'تحقّق', tabSubs: 'الترجمة', tabGrammar: 'القواعد', tabSaved: 'المحفوظات', tabRoutine: 'الروتين', tabProgress: 'التقدّم',
    searchSubs: 'ابحث في النص', translateAll: 'ترجمة الكل', words: 'كلمات', sentences: 'جمل', review: 'مراجعة', exportAnki: 'تصدير (Anki)',
    loadTitle: 'تحميل الفيديو والترجمة', srcFile: 'ملف من الجهاز', srcUrl: 'رابط', srcTts: 'نص فقط (صوت)',
    videoFile: 'فيديو أو صوت (mp4, webm, mkv, mp3…)',
    fileHint: 'لا يُرفع الملف إلى أي خادم: يُشغَّل في متصفحك. يمكنك استخدام أفلام كاملة دون حدّ للحجم.',
    videoUrl: 'يوتيوب، رابط مباشر ‎.mp4/.webm/.m3u8 أو Azure Blob',
    urlHint: 'يعمل: <b>يوتيوب</b> والروابط المباشرة لملفات الفيديو (مثل Azure Blob Storage). منصات مثل Bilibili وNetflix لا تسمح بالتحكم في مشغّلها من موقع آخر: نزّل الفيديو واستخدمه كملف مع ترجمة ‎.srt.',
    ttsHint: 'بدون فيديو: صوت اصطناعي يقرأ كل جملة. مفيد للتدرّب على النصوص والأغاني.',
    subsFile: 'ترجمة اللغة التي تتعلمها (.srt, .vtt, .ass, .txt)', pasteSubs: '…أو الصق نص الترجمة',
    subs2File: 'ترجمة بلغتك (اختياري؛ وإلا تُترجم تلقائيًا)', title: 'العنوان', cancel: 'إلغاء', start: 'ابدأ',
    profiles: 'الملفات الشخصية (شخصان)', aiTitle: 'مساعد الذكاء الاصطناعي (اختياري)',
    aiHint: 'بمفتاح Claude API تحصل على شروح نحوية عميقة وإجابات وأمثلة مخصّصة. بدون مفتاح يعمل التطبيق بمحرّك القواعد المدمج.',
    apiKey: 'مفتاح Anthropic API', aiModel: 'النموذج', aiWarn: 'يُحفظ المفتاح في هذا المتصفح فقط. لا تستخدمه على أجهزة مشتركة.',
    data: 'البيانات', exportData: 'تصدير نسخة (JSON)', importData: 'استيراد نسخة', resetData: 'حذف الكل', save: 'حفظ',
    aiAskPh: 'اسأل أي شيء عن هذه الجملة…', ask: 'اسأل',
    m_watch: '👀 مشاهدة مع الترجمة', m_mumble: '🤫 الهمهمة (Mumbling)', m_overlap: '📖 القراءة المتزامنة (Overlapping)',
    m_shadow_line: '🗣 شادوينغ جملة بجملة', m_shadow_full: '🏃 شادوينغ متواصل', m_record: '🎙 سجّل وقارن', m_translate: '🌐 ترجم كل جملة',
    t_autoPause: 'توقّف في نهاية كل جملة', t_loop: 'كرّر الجملة', t_times: 'مرات', t_autoResume: 'تابع تلقائيًا بعد', t_gap: 'توقف ×',
    t_prevBtn: 'زر الرجوع', t_hide: 'إخفاء النص', t_trans: 'الترجمة', t_blur: 'ترجمة ضبابية', t_karaoke: 'كاريوكي',
    t_stress: 'خريطة النبر', t_autoRec: 'سجّل أثناء التوقف', t_overlayRec: 'سجّل فوق الصوت (سماعات)', t_offset: 'المزامنة',
    line: 'جملة', of: 'من', noSubs: 'لا توجد ترجمة', saved: 'تم الحفظ', removed: 'تم الحذف', copied: 'تم النسخ',
    meaning: 'المعنى', definition: 'التعريف (بالإنجليزية)', examples: 'أمثلة', fromVideo: 'في الفيديو', partOf: 'جزء من',
    listen: 'استمع', saveWord: 'احفظ الكلمة', unsave: 'إزالة', loading: 'جارٍ التحميل…', notFound: 'لم توجد في القاموس.',
    grammarOf: 'قواعد الجملة', noGrammar: 'لم تُكتشف تراكيب خاصة. جرّب «شرح بالذكاء الاصطناعي».',
    connected: 'الكلام المتصل (كيف يُنطق فعلًا)', intonation: 'التنغيم', corpusTitle: 'قواعد الفيديو كاملًا',
    corpusHint: 'اضغط على تركيب لرؤية كل جمل الفيديو التي تستخدمه.', seeAll: 'عرض كل الجمل بهذا التركيب',
    filterOn: 'تصفية حسب', clear: 'إزالة التصفية', mergedNext: 'دُمجت مع السطر التالي لتحليل الجملة كاملة.',
    recNoMic: 'تعذّر الوصول إلى الميكروفون.', recording: 'جارٍ التسجيل…', yourDur: 'صوتك', origDur: 'الأصل', recognized: 'ما تم فهمه',
    noRecog: 'متصفحك لا يدعم التعرّف على الصوت (استخدم Chrome أو Edge للتقييم).', score: 'تطابق',
    yourTrans: 'ترجمتك', refTrans: 'ترجمة مرجعية', similarity: 'تشابه', writeFirst: 'اكتب ترجمتك أولًا.',
    nothingSaved: 'لم تحفظ شيئًا بعد. مرّر الفأرة على كلمة واضغط ☆.', show: 'إظهار', know: 'أعرفها', again: 'مرة أخرى', jump: 'اذهب للجملة',
    reviewDone: 'انتهت المراجعة!', library: 'الأخيرة', open: 'فتح', del: 'حذف', reselect: 'اختر ملف الفيديو مرة أخرى',
    needSubs: 'أضف ملف ترجمة أو الصق النص.', needVideo: 'اختر فيديو أو رابطًا.', badUrl: 'لا يمكن التحكم بهذا الرابط من هنا.',
    unsupportedSite: 'هذا الموقع (مثل Bilibili) لا يسمح بالتحكم في مشغّله من موقع آخر. نزّل الفيديو وحمّله كملف، أو ارفعه إلى Azure Blob Storage والصق الرابط المباشر.',
    translating: 'جارٍ الترجمة…', translated: 'الترجمة جاهزة', transFail: 'تعذّرت الترجمة (لا اتصال أو تم بلوغ الحد).',
    aiNoKey: 'أضف مفتاح API في الإعدادات لاستخدام الذكاء الاصطناعي.', aiThinking: 'الذكاء الاصطناعي يحلّل الجملة…', aiError: 'خطأ في الذكاء الاصطناعي',
    literal: 'ترجمة حرفية', natural: 'ترجمة طبيعية', vocab: 'المفردات', pronunciation: 'النطق', culture: 'السياق / الاستعمال',
    stLines: 'جمل تدرّبت عليها', stRec: 'تسجيلات', stMin: 'دقائق تدريب', stStreak: 'أيام متتالية', stWords: 'كلمات محفوظة', stTrans: 'متوسط الترجمة',
    last4w: 'آخر 4 أسابيع', routineTitle: 'روتين الشادوينغ (≈15 دقيقة لكل مقطع)', useMode: 'فعّل هذا الوضع', resetRoutine: 'إعادة الروتين',
    profileName: 'الاسم', nativeLang: 'اللغة الأم', targetLang: 'اللغة التي يتعلمها', imported: 'تم الاستيراد', confirmReset: 'حذف كل بيانات الملفين؟',
    mistakesTitle: 'أخطاء شائعة',
    demoTitle: 'عرض — شادوينغ', subsLoaded: 'سطر ترجمة', untimed: 'نص بدون توقيت: سيُقرأ بصوت اصطناعي.',
    speakSlow: 'بطيء', tags_q: 'سؤال',
  },
};
Object.assign(S.es, {
  appShadow: 'Shadowing', appGame: 'Escucha y completa', gameTitle: 'Escucha y completa',
  gameIntro: 'Escucha y escribe las palabras que faltan. Puedes escribir mientras suena. Si la frase termina con huecos, el vídeo se pausa y corre el reloj: ¡sé rápido! Si se acaba el tiempo pierdes una vida.',
  lvl_basic: 'Básico', lvl_medium: 'Medio', lvl_hard: 'Difícil',
  lvlDesc_basic: '1 palabra por frase · 5 vidas', lvlDesc_medium: '50% de las palabras · 4 vidas', lvlDesc_hard: '90% de las palabras · 3 vidas',
  startBegin: 'Desde el principio', startHere: 'Desde la frase actual', g_score: 'Puntos', combo: 'Combo', lives: 'Vidas',
  hint: 'Pista', skip: 'Saltar', replay: 'Repetir frase', listening: '🎧 Escucha y escribe…', typeNow: '⏱ ¡Escribe ya!', timeUp: '⏰ ¡Tiempo!',
  perfect: '✨ ¡Perfecto!', results: 'Resultados', accuracy: 'Precisión', maxCombo: 'Combo máximo', best: 'Récord', newBest: '🏆 ¡Nuevo récord!',
  missedWords: 'Palabras que fallaste', saveMissed: 'Guardar estas palabras', playAgain: 'Jugar otra vez', nextLevel: 'Siguiente nivel',
  exitGame: 'Salir', quit: 'Terminar partida', gameKeys: 'Enter = repetir frase · ↓ = pista · Esc = saltar',
  needVideoGame: 'Carga primero un vídeo (o la demo) con subtítulos.', gameOverLives: '💔 Sin vidas', gameDone: '🎉 ¡Clip completado!',
  showTrans: 'Ver traducción', savedN: 'palabras guardadas',
});
Object.assign(S.ar, {
  appShadow: 'شادوينغ', appGame: 'استمع وأكمل', gameTitle: 'استمع وأكمل',
  gameIntro: 'استمع واكتب الكلمات الناقصة. يمكنك الكتابة أثناء التشغيل. إذا انتهت الجملة وبقيت فراغات يتوقف الفيديو ويبدأ العدّ التنازلي: كن سريعًا! إذا انتهى الوقت تخسر حياة.',
  lvl_basic: 'مبتدئ', lvl_medium: 'متوسط', lvl_hard: 'صعب',
  lvlDesc_basic: 'كلمة واحدة في كل جملة · 5 أرواح', lvlDesc_medium: '50% من الكلمات · 4 أرواح', lvlDesc_hard: '90% من الكلمات · 3 أرواح',
  startBegin: 'من البداية', startHere: 'من الجملة الحالية', g_score: 'النقاط', combo: 'سلسلة', lives: 'أرواح',
  hint: 'تلميح', skip: 'تخطَّ', replay: 'أعد الجملة', listening: '🎧 استمع واكتب…', typeNow: '⏱ اكتب الآن!', timeUp: '⏰ انتهى الوقت!',
  perfect: '✨ ممتاز!', results: 'النتائج', accuracy: 'الدقة', maxCombo: 'أطول سلسلة', best: 'الرقم القياسي', newBest: '🏆 رقم قياسي جديد!',
  missedWords: 'كلمات أخطأت فيها', saveMissed: 'احفظ هذه الكلمات', playAgain: 'العب مرة أخرى', nextLevel: 'المستوى التالي',
  exitGame: 'خروج', quit: 'أنهِ اللعبة', gameKeys: 'Enter = أعد الجملة · ↓ = تلميح · Esc = تخطَّ',
  needVideoGame: 'حمّل أولًا فيديو (أو العرض التجريبي) مع ترجمة.', gameOverLives: '💔 نفدت الأرواح', gameDone: '🎉 أكملت المقطع!',
  showTrans: 'إظهار الترجمة', savedN: 'كلمات محفوظة',
});
S.en = Object.assign({}, S.es, {
  load: 'Load video', settings: 'Settings', help: 'Help', emptyTitle: 'Practice shadowing with any movie',
  emptyText: 'Load a video (file, YouTube or direct link) and its subtitles. Then listen, repeat, record yourself, translate and analyse the grammar of every line.',
  tryDemo: 'Try the demo (synthetic voice)', tabSubs: 'Subtitles', tabGrammar: 'Grammar', tabSaved: 'Saved', tabRoutine: 'Routine', tabProgress: 'Progress',
  check: 'Check', start: 'Start', cancel: 'Cancel', save: 'Save', words: 'Words', sentences: 'Sentences', review: 'Review',
});

let lang = 'es';
export function setLang(l) { lang = S[l] ? l : 'es'; document.documentElement.lang = lang; }
export function getLang() { return lang; }
export function t(key) { return (S[lang] && S[lang][key]) ?? S.es[key] ?? key; }
/** Pick the right language from an {es, ar, en} object. */
export function tr(obj) {
  if (obj == null) return '';
  if (typeof obj === 'string') return obj;
  return obj[lang] ?? obj.es ?? obj.en ?? '';
}

export function applyStatic(root = document) {
  root.querySelectorAll('[data-i18n]').forEach(el => { el.textContent = t(el.dataset.i18n); });
  root.querySelectorAll('[data-i18n-html]').forEach(el => { el.innerHTML = t(el.dataset.i18nHtml); });
  root.querySelectorAll('[data-i18n-title]').forEach(el => { el.title = t(el.dataset.i18nTitle); });
  root.querySelectorAll('[data-i18n-ph]').forEach(el => { el.placeholder = t(el.dataset.i18nPh); });
}

export const LANGS = {
  es: 'Español', ar: 'العربية', en: 'English', fr: 'Français', de: 'Deutsch', it: 'Italiano', pt: 'Português',
  ja: '日本語', ko: '한국어', zh: '中文', ru: 'Русский', tr: 'Türkçe',
};
export const SPEECH_LOCALE = { en: 'en-US', es: 'es-ES', ar: 'ar-SA', fr: 'fr-FR', de: 'de-DE', it: 'it-IT', pt: 'pt-BR', ja: 'ja-JP', ko: 'ko-KR', zh: 'zh-CN', ru: 'ru-RU', tr: 'tr-TR' };

export const POS_NAMES = {
  noun: { es: 'sustantivo', ar: 'اسم' }, verb: { es: 'verbo', ar: 'فعل' }, adjective: { es: 'adjetivo', ar: 'صفة' },
  adverb: { es: 'adverbio', ar: 'ظرف' }, pronoun: { es: 'pronombre', ar: 'ضمير' }, preposition: { es: 'preposición', ar: 'حرف جر' },
  conjunction: { es: 'conjunción', ar: 'حرف عطف' }, interjection: { es: 'interjección', ar: 'تعجّب' }, article: { es: 'artículo', ar: 'أداة' },
  determiner: { es: 'determinante', ar: 'محدِّد' }, abbreviation: { es: 'abreviatura', ar: 'اختصار' }, 'auxiliary verb': { es: 'verbo auxiliar', ar: 'فعل مساعد' },
  phrase: { es: 'expresión', ar: 'عبارة' }, prefix: { es: 'prefijo', ar: 'بادئة' }, suffix: { es: 'sufijo', ar: 'لاحقة' }, exclamation: { es: 'exclamación', ar: 'تعجّب' },
};
export function posName(p) { const o = POS_NAMES[String(p || '').toLowerCase()]; return o ? tr(o) : (p || ''); }
