// Static learning content: practice modes, the shadowing routine, common mistakes, help and demo.
const X = (es, ar, en) => ({ es, ar, en: en || es });

export const MODES = {
  watch: { autoPause: false, loopLine: false, autoResume: false, hideText: false, autoRecord: false, overlayRecord: false, showTranslation: true, karaoke: true },
  mumble: { autoPause: false, loopLine: false, autoResume: false, hideText: true, autoRecord: false, overlayRecord: false, showTranslation: false },
  overlap: { autoPause: false, loopLine: false, autoResume: false, hideText: false, karaoke: true, autoRecord: false, showTranslation: false },
  shadow_line: { autoPause: true, loopLine: false, autoResume: true, gapFactor: 1.3, hideText: true, autoRecord: false, overlayRecord: false, showTranslation: false },
  shadow_full: { autoPause: false, loopLine: false, autoResume: false, hideText: true, autoRecord: false, showTranslation: false },
  record: { autoPause: true, loopLine: false, autoResume: true, gapFactor: 1.4, hideText: false, autoRecord: true, overlayRecord: false, showTranslation: false },
  translate: { autoPause: true, loopLine: false, autoResume: false, hideText: false, autoRecord: false, overlayRecord: false, showTranslation: false },
};

export const ROUTINE = [
  { mode: 'watch', title: X('1. Elige un clip de 1–2 minutos', '1. اختر مقطعًا من 1–2 دقيقة', '1. Pick a 1–2 minute clip'),
    text: X('Un solo hablante claro, natural pero sin prisas, adecuado a tu nivel. Usa la búsqueda o salta a una escena concreta.', 'متحدث واحد واضح، طبيعي دون سرعة زائدة ومناسب لمستواك.', 'One clear speaker, natural but not rushed, right for your level. Use search or jump to a specific scene.') },
  { mode: 'watch', title: X('2. Escucha y entiende', '2. استمع وافهم', '2. Listen and understand'),
    text: X('Míralo con subtítulos duales. Pasa el ratón por las palabras que no conozcas y guárdalas. Revisa la pestaña Gramática. Mientras haces shadowing no deberías estar descifrando el significado.', 'شاهده مع ترجمة مزدوجة. مرّر الفأرة على الكلمات الجديدة واحفظها. راجع تبويب القواعد. أثناء الشادوينغ يجب ألا تنشغل بفهم المعنى.', 'Watch it with dual subtitles. Hover unknown words and save them. Check the Grammar tab. While shadowing you should not be decoding the meaning.') },
  { mode: 'mumble', title: X('3. Mumbling: murmura a la vez', '3. الهمهمة مع الصوت', '3. Mumbling: murmur along'),
    text: X('Reproduce el clip y sigue el ritmo en voz baja, sin texto. No te preocupes aún por cada palabra.', 'شغّل المقطع وتابع الإيقاع بصوت منخفض دون نص. لا تهتم بكل كلمة بعد.', 'Play the clip and follow the rhythm quietly, without text. Don\'t worry about every word yet.') },
  { mode: 'overlap', title: X('4. Overlapping: lee a la vez', '4. القراءة المتزامنة', '4. Overlapping: read along'),
    text: X('Lee los subtítulos en voz alta exactamente al mismo tiempo que el hablante (el modo karaoke te marca el ritmo). Iguala velocidad, pausas y subidas/bajadas de la voz.', 'اقرأ الترجمة بصوت عالٍ في نفس لحظة المتحدث (وضع الكاريوكي يحدّد الإيقاع). طابق السرعة والتوقفات وارتفاع الصوت وانخفاضه.', 'Read the subtitles aloud exactly at the same time as the speaker (karaoke mode marks the rhythm). Match speed, pauses and the rise and fall of the voice.') },
  { mode: 'shadow_line', title: X('5. Shadowing frase a frase', '5. شادوينغ جملة بجملة', '5. Line-by-line shadowing'),
    text: X('Texto oculto. Cada frase se pausa sola para que la repitas; pulsa ↺ (S) para volver a escuchar la que se te atasque. Activa «Repetir frase» para las difíciles.', 'النص مخفي. تتوقف كل جملة تلقائيًا لتكررها؛ اضغط ↺ (S) لإعادة الجملة الصعبة. فعّل «كرّر الجملة» للجمل الصعبة.', 'Text hidden. Each line pauses by itself so you can repeat it; press ↺ (S) to hear a tricky one again. Turn on “Repeat line” for hard ones.') },
  { mode: 'shadow_full', title: X('6. Shadowing del clip entero', '6. شادوينغ للمقطع كاملًا', '6. Shadow the whole clip'),
    text: X('Sigue al hablante sin parar, más o menos medio segundo por detrás, hablando en voz alta y con volumen normal.', 'تابع المتحدث دون توقف، متأخرًا عنه بنصف ثانية تقريبًا، بصوت عالٍ وطبيعي.', 'Follow the speaker without stopping, about half a second behind, speaking out loud at normal volume.') },
  { mode: 'record', title: X('7. Grábate y compara', '7. سجّل صوتك وقارن', '7. Record yourself and compare'),
    text: X('Se graba tu voz en cada pausa. Pulsa ⇄ para oír original y después tu versión; mira duración, forma de onda y la puntuación de palabras reconocidas. Elige UNA cosa para mejorar mañana.', 'يُسجَّل صوتك في كل توقف. اضغط ⇄ لسماع الأصل ثم صوتك؛ راقب المدة وشكل الموجة ونسبة الكلمات المفهومة. اختر شيئًا واحدًا لتحسينه غدًا.', 'Your voice is recorded in each pause. Press ⇄ to hear the original and then you; check duration, waveform and the recognised-words score. Pick ONE thing to improve tomorrow.') },
  { mode: 'translate', title: X('8. Traduce a tu idioma', '8. ترجم إلى لغتك', '8. Translate into your language'),
    text: X('Escribe en tu idioma lo que dice cada frase y compárala con la traducción de referencia. Comprueba que de verdad entiendes lo que repites.', 'اكتب بلغتك معنى كل جملة وقارنها بالترجمة المرجعية. تأكّد أنك تفهم فعلًا ما تكرره.', 'Write what each line means in your language and compare it with the reference. Make sure you really understand what you repeat.') },
];

export const MISTAKES = [
  X('Material demasiado difícil: si no lo entiendes ni con subtítulos, elige uno más fácil.', 'مادة صعبة جدًا: إن لم تفهمها حتى مع الترجمة فاختر أسهل.', 'Material that is too hard: if you can\'t follow it even with subtitles, pick an easier one.'),
  X('Quedarte siempre en el mumbling: es solo un calentamiento; luego habla en voz alta.', 'البقاء في الهمهمة: إنها مجرد إحماء؛ بعدها تكلّم بصوت عالٍ.', 'Never leaving mumbling: it\'s only a warm-up; then speak out loud.'),
  X('Obsesionarte con cada palabra: primero el ritmo y la entonación; las palabras llegan con la repetición.', 'التركيز على كل كلمة: الإيقاع والتنغيم أولًا، والكلمات تأتي بالتكرار.', 'Obsessing over every word: rhythm and intonation first; the words come with repetition.'),
  X('No escucharte nunca: grábate, si no rara vez detectas qué corregir.', 'عدم الاستماع لنفسك: سجّل صوتك وإلا فلن تعرف ما تصححه.', 'Never listening to yourself: record yourself, or you\'ll rarely notice what to fix.'),
  X('Hacer solo shadowing: combínalo con crear tus propias frases (usa los ejemplos de la pestaña Gramática).', 'الاكتفاء بالشادوينغ: اجمعه مع تكوين جملك الخاصة (استعمل أمثلة تبويب القواعد).', 'Only shadowing: combine it with building your own sentences (use the examples in the Grammar tab).'),
  X('Mejor 10–15 minutos cada día que una hora a la semana. Repite el mismo clip varios días seguidos.', '10–15 دقيقة يوميًا أفضل من ساعة أسبوعيًا. كرّر نفس المقطع عدة أيام متتالية.', '10–15 minutes every day beat one hour a week. Repeat the same clip several days in a row.'),
];

export const HELP = X(`
<h3>Atajos de teclado</h3>
<table class="help-table">
<tr><td><kbd>Espacio</kbd></td><td>Reproducir / pausa</td></tr>
<tr><td><kbd>A</kbd> / <kbd>←</kbd></td><td>Frase anterior</td></tr>
<tr><td><kbd>S</kbd></td><td>Repetir la frase actual</td></tr>
<tr><td><kbd>D</kbd> / <kbd>→</kbd></td><td>Frase siguiente</td></tr>
<tr><td><kbd>R</kbd></td><td>Empezar / parar grabación</td></tr>
<tr><td><kbd>P</kbd></td><td>Escuchar mi grabación</td></tr>
<tr><td><kbd>C</kbd></td><td>Comparar: original y luego mi voz</td></tr>
<tr><td><kbd>H</kbd></td><td>Mostrar el texto oculto un momento</td></tr>
<tr><td><kbd>T</kbd></td><td>Mostrar / ocultar traducción</td></tr>
<tr><td><kbd>L</kbd></td><td>Repetir frase en bucle</td></tr>
<tr><td><kbd>Q</kbd></td><td>Pausa automática al final de cada frase</td></tr>
<tr><td><kbd>F</kbd></td><td>Pantalla completa</td></tr>
</table>
<h3>¿De dónde saco subtítulos?</h3>
<ul>
<li>Películas: busca el .srt en sitios de subtítulos o extráelo de un .mkv con <code>ffmpeg -i pelicula.mkv -map 0:s:0 subs.srt</code>.</li>
<li>YouTube: descarga los subtítulos (.srt/.vtt) con herramientas como yt-dlp (<code>yt-dlp --write-subs --sub-langs en --skip-download URL</code>).</li>
<li>Si los subtítulos van adelantados o retrasados, ajusta «Sincronía» (±0,1 s).</li>
</ul>
<h3>¿Y Bilibili, Netflix…?</h3>
<p>Esas webs no permiten que otra página controle su reproductor (pausar en cada frase, repetir…). Descarga el vídeo con permiso y cárgalo como archivo; nunca se sube a ningún servidor. Si queréis compartir vídeos entre las dos personas, subidlos a Azure Blob Storage y pegad el enlace directo.</p>
<h3>Dos personas</h3>
<p>Cada perfil tiene su idioma nativo (por ejemplo español y árabe), sus palabras guardadas, ajustes y progreso. Cambia de perfil arriba a la derecha. Para pasar datos a otro dispositivo usa Ajustes → Exportar / Importar.</p>
`, `
<h3>اختصارات لوحة المفاتيح</h3>
<table class="help-table">
<tr><td><kbd>Space</kbd></td><td>تشغيل / إيقاف</td></tr>
<tr><td><kbd>A</kbd> / <kbd>←</kbd></td><td>الجملة السابقة</td></tr>
<tr><td><kbd>S</kbd></td><td>إعادة الجملة الحالية</td></tr>
<tr><td><kbd>D</kbd> / <kbd>→</kbd></td><td>الجملة التالية</td></tr>
<tr><td><kbd>R</kbd></td><td>بدء / إيقاف التسجيل</td></tr>
<tr><td><kbd>P</kbd></td><td>استمع لتسجيلي</td></tr>
<tr><td><kbd>C</kbd></td><td>قارن: الأصل ثم صوتي</td></tr>
<tr><td><kbd>H</kbd></td><td>أظهر النص المخفي لحظة</td></tr>
<tr><td><kbd>T</kbd></td><td>إظهار / إخفاء الترجمة</td></tr>
<tr><td><kbd>L</kbd></td><td>تكرار الجملة</td></tr>
<tr><td><kbd>Q</kbd></td><td>توقف تلقائي في نهاية كل جملة</td></tr>
<tr><td><kbd>F</kbd></td><td>ملء الشاشة</td></tr>
</table>
<h3>من أين أحصل على الترجمة؟</h3>
<ul>
<li>الأفلام: ابحث عن ملف ‎.srt أو استخرجه من ‎.mkv بالأمر <code>ffmpeg -i movie.mkv -map 0:s:0 subs.srt</code>.</li>
<li>يوتيوب: نزّل الترجمة بأداة مثل yt-dlp.</li>
<li>إذا كانت الترجمة متقدمة أو متأخرة، اضبط «المزامنة» (±0.1 ث).</li>
</ul>
<h3>وماذا عن Bilibili وNetflix؟</h3>
<p>هذه المواقع لا تسمح لصفحة أخرى بالتحكم في مشغّلها. نزّل الفيديو وحمّله كملف؛ لا يُرفع إلى أي خادم. لمشاركة الفيديوهات بينكما ارفعاها إلى Azure Blob Storage والصقا الرابط المباشر.</p>
<h3>شخصان</h3>
<p>لكل ملف شخصي لغته الأم وكلماته المحفوظة وإعداداته وتقدّمه. بدّل الملف من أعلى اليمين. لنقل البيانات إلى جهاز آخر استخدم الإعدادات ← تصدير / استيراد.</p>
`, `
<h3>Keyboard shortcuts</h3>
<table class="help-table">
<tr><td><kbd>Space</kbd></td><td>Play / pause</td></tr>
<tr><td><kbd>A</kbd> / <kbd>←</kbd></td><td>Previous line</td></tr>
<tr><td><kbd>S</kbd></td><td>Repeat the current line</td></tr>
<tr><td><kbd>D</kbd> / <kbd>→</kbd></td><td>Next line</td></tr>
<tr><td><kbd>R</kbd></td><td>Start / stop recording</td></tr>
<tr><td><kbd>P</kbd></td><td>Play my recording</td></tr>
<tr><td><kbd>C</kbd></td><td>Compare: original, then my voice</td></tr>
<tr><td><kbd>H</kbd></td><td>Peek at hidden text</td></tr>
<tr><td><kbd>T</kbd></td><td>Show / hide translation</td></tr>
<tr><td><kbd>L</kbd></td><td>Loop the line</td></tr>
<tr><td><kbd>Q</kbd></td><td>Auto-pause after each line</td></tr>
<tr><td><kbd>F</kbd></td><td>Full screen</td></tr>
</table>
<h3>Listen &amp; complete</h3>
<p><kbd>Enter</kbd> replay line · <kbd>↓</kbd> hint · <kbd>Esc</kbd> skip. Capitals, accents and apostrophes don't matter (“im” counts as “I'm”).</p>
<h3>Where do I get subtitles?</h3>
<ul>
<li>Movies: find the .srt file on a subtitle site, or extract it from an .mkv with <code>ffmpeg -i movie.mkv -map 0:s:0 subs.srt</code>.</li>
<li>YouTube: download the subtitles (.srt/.vtt) with a tool such as yt-dlp (<code>yt-dlp --write-subs --sub-langs en --skip-download URL</code>).</li>
<li>If the subtitles are early or late, adjust “Sync” (±0.1 s).</li>
</ul>
<h3>Two people</h3>
<p>Each profile has its own native language (used only for meanings and translations), saved words, settings and progress. Switch profile at the top right. To move data to another device use Settings → Export / Import.</p>
`);

export const DEMO_SRT = `1
00:00:00,500 --> 00:00:02,600
Hi! Do you have a minute?

2
00:00:03,000 --> 00:00:05,800
I've been looking for you all morning.

3
00:00:06,200 --> 00:00:09,000
I'm going to tell you something important.

4
00:00:09,400 --> 00:00:12,600
If you had told me earlier, I would have helped you.

5
00:00:13,000 --> 00:00:15,600
Don't worry, we'll figure it out together.

6
00:00:16,000 --> 00:00:19,000
The window was broken by someone who lives here.

7
00:00:19,400 --> 00:00:22,400
You should have called the police, shouldn't you?

8
00:00:22,800 --> 00:00:25,800
I wanna know what you're gonna do about it.

9
00:00:26,200 --> 00:00:29,200
Let's calm down and think about it.

10
00:00:29,600 --> 00:00:32,600
I used to live here, but I'm not used to this noise.
`;
