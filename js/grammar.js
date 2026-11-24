// Offline grammar engine for English sentences.
// Detects ~40 structures (tenses, modals, conditionals, passive, phrasal verbs, reductions…),
// explains them in Spanish and Arabic, and adds connected-speech / intonation hints for shadowing.
import { normalize } from './subtitles.js';

// ---------------------------------------------------------------- word lists
const PP_IRR = 'been|done|gone|seen|taken|given|eaten|written|spoken|broken|chosen|driven|forgotten|gotten|got|made|said|told|found|thought|brought|bought|caught|taught|felt|kept|left|lost|meant|met|paid|sent|sold|stood|understood|won|hurt|become|begun|drunk|sung|swum|known|grown|thrown|flown|drawn|shown|worn|torn|born|hidden|ridden|risen|fallen|held|heard|built|spent|lent|slept|dealt|fed|fled|led|fought|sought|stolen|frozen|woken|shaken|mistaken|forgiven|hung|struck|stuck|dug|sworn|beaten|bitten|proven|had|laid|spread|quit|burnt|learnt|dreamt|bound|lit|shot|slid|withdrawn|overcome|undone|upset|forbidden|ground|sat|run|come|put|cut|hit|let|set|shut|read';
const PAST_IRR = 'went|came|saw|took|gave|ate|wrote|spoke|broke|chose|drove|forgot|got|made|said|told|found|thought|brought|bought|caught|taught|felt|kept|left|lost|meant|met|paid|ran|sent|sold|sat|stood|understood|won|became|began|drank|sang|swam|knew|grew|threw|flew|drew|wore|tore|hid|rode|rose|fell|held|heard|built|spent|slept|fought|did|woke|shook|hung|struck|stuck|dug|swore|bit|stole|froze|forgave|fed|fled|led|lay|shot|lit|slid|sought|bound|was|were|had|could';
const PP = `(?:[a-z]{2,}ed|${PP_IRR})`;
const BE = "(?:am|is|are|was|were|be|been|being|'m|'re|'s|isn't|aren't|wasn't|weren't)";
const ADV = '(?:(?:not|never|just|already|really|still|always|ever|also|even|finally|actually|probably|definitely|completely|totally|recently|only)\\s+)';
const ED_NOT_VERB = new Set('need feed seed speed bleed breed indeed proceed succeed exceed bed red shed wed sacred hundred naked wicked bred fred ted ned weed greed deed reed sled embed shred steed tweed ed beloved rugged ragged jagged crooked kindred sled hatred infrared'.split(' '));
const FEEL_ADJ = new Set('tired interested bored excited worried scared married surprised pleased confused embarrassed disappointed annoyed amazed relaxed satisfied shocked frightened terrified ashamed prepared done finished involved engaged exhausted convinced determined upset lost stuck drunk closed gone supposed used concerned obsessed impressed thrilled fed stressed depressed overwhelmed qualified talented crowded experienced'.split(' '));
const ING_ADJ = new Set('interesting amazing boring exciting surprising annoying confusing disappointing embarrassing frightening shocking terrifying tiring relaxing charming disgusting fascinating exhausting depressing overwhelming satisfying worrying stunning'.split(' '));
const ING_NOT_VERB = new Set('thing things nothing something anything everything morning mornings evening evenings king ring wing string spring ceiling sibling darling pudding wedding earring swing sing bring during awning bling cling fling sting'.split(' '));
const SUP_NOT = new Set('rest test west chest guest nest interest request quest forest contest protest honest modest best worst arrest priest suggest'.split(' '));
export const FUNCTION_WORDS = new Set("a an the and or but so to of in on at for from by with as if than that this these those it its i you he she we they me him her us them my your his our their is am are was were be been being do does did have has had will would can could shall should may might must not no yes there here what when where who whom which why how all some any just very too also then up out off over about into onto upon 'm 're 's 've 'll 'd i'm you're he's she's it's we're they're i've you've we've they've i'll you'll he'll she'll we'll they'll i'd you'd he'd she'd we'd they'd isn't aren't wasn't weren't don't doesn't didn't haven't hasn't hadn't won't wouldn't can't couldn't shouldn't mustn't let's that's there's what's who's".split(' '));

const IRR_FORMS = {
  take: 'takes took taken taking', give: 'gives gave given giving', get: 'gets got gotten getting', go: 'goes went gone going',
  come: 'comes came come coming', make: 'makes made made making', put: 'puts put put putting', set: 'sets set set setting',
  run: 'runs ran run running', break: 'breaks broke broken breaking', bring: 'brings brought brought bringing', find: 'finds found found finding',
  hold: 'holds held held holding', keep: 'keeps kept kept keeping', let: 'lets let let letting', grow: 'grows grew grown growing',
  throw: 'throws threw thrown throwing', show: 'shows showed shown showing', sit: 'sits sat sat sitting', stand: 'stands stood stood standing',
  wake: 'wakes woke woken waking', hang: 'hangs hung hung hanging', shut: 'shuts shut shut shutting', think: 'thinks thought thought thinking',
  deal: 'deals dealt dealt dealing', catch: 'catches caught caught catching', drop: 'drops dropped dropped dropping', mess: 'messes messed messed messing',
  cheer: 'cheers cheered cheered cheering', fill: 'fills filled filled filling', pass: 'passes passed passed passing', watch: 'watches watched watched watching',
  carry: 'carries carried carried carrying', figure: 'figures figured figured figuring', move: 'moves moved moved moving', calm: 'calms calmed calmed calming',
  belong: 'belongs belonged belonged belonging',
};
function verbForms(v) {
  if (IRR_FORMS[v]) return [v, ...IRR_FORMS[v].split(' ')];
  const s = /[^aeiou]y$/.test(v) ? v.slice(0, -1) + 'ies' : /(s|sh|ch|x|o)$/.test(v) ? v + 'es' : v + 's';
  const ed = v.endsWith('e') ? v + 'd' : /[^aeiou]y$/.test(v) ? v.slice(0, -1) + 'ied' : v + 'ed';
  const ing = v.endsWith('ie') ? v.slice(0, -2) + 'ying' : (v.endsWith('e') && !v.endsWith('ee')) ? v.slice(0, -1) + 'ing' : v + 'ing';
  return [v, s, ed, ing];
}

// [verb, particle, es, ar]
export const PHRASAL = [
  ['give', 'up', 'rendirse; dejar de (hacer algo)', 'يستسلم؛ يتوقف عن'], ['find', 'out', 'descubrir, enterarse', 'يكتشف، يعرف'],
  ['take', 'over', 'tomar el control', 'يتولّى السيطرة'], ['look', 'for', 'buscar', 'يبحث عن'], ['look', 'after', 'cuidar', 'يعتني بـ'],
  ['look', 'forward to', 'tener ganas de, esperar con ilusión', 'يتطلّع إلى'], ['look', 'up', 'buscar (información)', 'يبحث عن معلومة'],
  ['look', 'out', 'tener cuidado', 'ينتبه، يحذر'], ['look', 'into', 'investigar', 'يحقّق في'], ['come', 'back', 'volver', 'يعود'],
  ['come', 'on', '¡vamos! / ¡venga!', 'هيا! / بالله عليك'], ['come', 'up with', 'idear, ocurrírsele', 'يبتكر، تخطر له فكرة'],
  ['come', 'across', 'encontrarse por casualidad', 'يصادف'], ['go', 'on', 'continuar; ocurrir', 'يستمر؛ يحدث'], ['go', 'out', 'salir', 'يخرج'],
  ['go', 'back', 'volver', 'يرجع'], ['go', 'away', 'irse', 'يذهب بعيدًا'], ['go', 'through', 'pasar por (algo difícil)', 'يمرّ بـ'],
  ['get', 'up', 'levantarse', 'ينهض'], ['get', 'out', 'salir', 'يخرج'], ['get', 'back', 'volver; recuperar', 'يعود؛ يستعيد'],
  ['get', 'over', 'superar', 'يتجاوز، يتعافى من'], ['get', 'along', 'llevarse bien', 'يتوافق، ينسجم'], ['get', 'in', 'entrar (subir a un coche)', 'يدخل، يركب'],
  ['get', 'away', 'escaparse', 'يفلت، يهرب'], ['get', 'rid of', 'deshacerse de', 'يتخلّص من'], ['turn', 'on', 'encender', 'يشغّل'],
  ['turn', 'off', 'apagar', 'يطفئ'], ['turn', 'down', 'rechazar; bajar (volumen)', 'يرفض؛ يخفض'], ['turn', 'up', 'aparecer; subir (volumen)', 'يظهر؛ يرفع'],
  ['turn', 'out', 'resultar (que)', 'يتبيّن أن'], ['turn', 'around', 'darse la vuelta', 'يستدير'], ['put', 'on', 'ponerse (ropa)', 'يرتدي'],
  ['put', 'off', 'posponer', 'يؤجّل'], ['put', 'up with', 'aguantar, soportar', 'يتحمّل'], ['take', 'off', 'despegar; quitarse', 'تقلع؛ يخلع'],
  ['take', 'care of', 'cuidar de; encargarse de', 'يعتني بـ؛ يتولّى'], ['take', 'on', 'asumir (un reto)', 'يتولّى، يتحمّل'], ['pick', 'up', 'recoger; aprender', 'يلتقط؛ يقلّ'],
  ['set', 'up', 'montar, organizar; tender una trampa', 'يُعدّ، يؤسّس؛ يوقع به'], ['show', 'up', 'aparecer, presentarse', 'يحضر، يظهر'], ['show', 'off', 'presumir', 'يتباهى'],
  ['figure', 'out', 'entender, resolver', 'يفهم، يحلّ'], ['work', 'out', 'hacer ejercicio; salir bien', 'يتمرّن؛ ينجح'], ['hang', 'out', 'pasar el rato', 'يقضي الوقت مع'],
  ['hang', 'on', 'espera un momento', 'انتظر لحظة'], ['calm', 'down', 'calmarse', 'يهدأ'], ['shut', 'up', 'callarse', 'يصمت'],
  ['break', 'up', 'romper (una relación)', 'ينفصل'], ['break', 'down', 'averiarse; derrumbarse', 'يتعطّل؛ ينهار'], ['break', 'into', 'entrar a la fuerza', 'يقتحم'],
  ['run', 'out of', 'quedarse sin', 'ينفد منه'], ['run', 'away', 'huir', 'يهرب'], ['carry', 'on', 'continuar', 'يواصل'],
  ['check', 'out', 'echar un vistazo; comprobar', 'يتفقّد، يلقي نظرة'], ['fill', 'out', 'rellenar (un formulario)', 'يملأ (استمارة)'], ['fill', 'in', 'rellenar; sustituir', 'يملأ؛ ينوب'],
  ['hold', 'on', 'espera; agárrate', 'انتظر؛ تمسّك'], ['keep', 'up', 'mantener el ritmo', 'يواكب'], ['let', 'down', 'decepcionar', 'يخذل'],
  ['make', 'up', 'inventar; reconciliarse', 'يختلق؛ يتصالح'], ['mess', 'up', 'estropear, fastidiar', 'يُفسد، يخرّب'], ['point', 'out', 'señalar', 'يشير إلى'],
  ['sort', 'out', 'solucionar, ordenar', 'يحلّ، يرتّب'], ['wake', 'up', 'despertarse', 'يستيقظ'], ['grow', 'up', 'crecer, criarse', 'يكبر، ينشأ'],
  ['bring', 'up', 'sacar un tema; criar', 'يذكر موضوعًا؛ يربّي'], ['end', 'up', 'acabar (en/haciendo)', 'ينتهي به الأمر'], ['give', 'back', 'devolver', 'يعيد'],
  ['call', 'back', 'devolver la llamada', 'يعاود الاتصال'], ['sit', 'down', 'sentarse', 'يجلس'], ['stand', 'up', 'ponerse de pie', 'يقف'],
  ['throw', 'away', 'tirar (a la basura)', 'يرمي'], ['deal', 'with', 'ocuparse de, lidiar con', 'يتعامل مع'], ['count', 'on', 'contar con', 'يعتمد على'],
  ['pass', 'out', 'desmayarse', 'يُغمى عليه'], ['back', 'up', 'respaldar; retroceder', 'يدعم؛ يتراجع'], ['catch', 'up', 'ponerse al día', 'يلحق بـ'],
  ['cheer', 'up', 'animarse', 'يبتهج'], ['drop', 'by', 'pasarse (de visita)', 'يزور سريعًا'], ['move', 'on', 'pasar página, seguir adelante', 'يمضي قدمًا'],
  ['watch', 'out', '¡cuidado!', 'احذر!'], ['belong', 'to', 'pertenecer a', 'ينتمي إلى'], ['think', 'about', 'pensar en', 'يفكّر في'],
];
const OBJ = '(?:it|him|her|them|me|us|you|this|that|everything|something|things)';
const PHRASAL_RE = PHRASAL.map(([v, p, es, ar]) => ({
  v, p, es, ar,
  re: new RegExp(`\\b(?:${verbForms(v).join('|')})(?:\\s+${OBJ})?\\s+${p.replace(/ /g, '\\s+')}\\b`, 'g'),
}));

// ---------------------------------------------------------------- helpers
function scan(re, lc, filter) {
  const out = []; re.lastIndex = 0; let m;
  while ((m = re.exec(lc))) {
    if (!m[0].length) { re.lastIndex++; continue; }
    const r = { s: m.index, e: m.index + m[0].length, m };
    if (!filter || filter(m, r)) out.push(r);
  }
  return out;
}
const rx = (s, f = 'g') => new RegExp(s, f);
const X = (es, ar, en) => ({ es, ar, en: en || es });

// ---------------------------------------------------------------- rules
export const RULES = [
  {
    id: 'present_simple', level: 'A1',
    name: X('Presente simple', 'المضارع البسيط', 'Present simple'),
    structure: 'I/you/we/they + verbo · he/she/it + verbo-s · do/does (not) + verbo',
    explain: X('Hábitos, verdades generales, gustos y estados (know, want, like, need…). Con he/she/it el verbo lleva -s; en preguntas y negaciones usamos do/does.',
      'للعادات والحقائق العامة والمشاعر والحالات (know, want, like…). مع he/she/it يُضاف ‎-s للفعل؛ وفي السؤال والنفي نستعمل do/does.'),
    examples: ['She works in a hospital.', "I don't know what you mean.", 'Does he like coffee?'],
    tip: X('Los verbos de estado (know, want, believe) casi nunca van en -ing: «I know», no «I am knowing».', 'أفعال الحالة (know, want, believe) لا تأتي عادةً بصيغة ‎-ing: نقول «I know» وليس «I am knowing».'),
    find(lc) {
      const a = scan(rx(`\\b(?:he|she|it|who|everyone|everybody|nobody|someone|somebody|that|this)\\s+(?:${ADV.slice(0, -1)})?([a-z]{3,}s)\\b`), lc,
        m => !/(?:ss|us|is|ous|was|has|does|this|his|its|yes|always|sometimes|perhaps|towards|ones|lots|less|news|thanks)$/.test(m[1]) && !/^(?:his|its|has|was|is|does)$/.test(m[1]));
      const b = scan(rx("\\b(?:i|you|we|they)\\s+(?:really\\s+|just\\s+|still\\s+|always\\s+|never\\s+|also\\s+|totally\\s+)?(?:know|think|want|need|like|mean|guess|love|hate|believe|remember|understand|feel|hope|seem|care|agree|wonder|promise|swear|bet|suppose|trust|live|work|see|get it)\\b"), lc);
      const c = scan(/\b(?:does|doesn't|do you|do i|do we|do they|don't you|don't we|don't they)\b/g, lc);
      return [...a, ...b, ...c];
    },
  },
  {
    id: 'present_continuous', level: 'A1',
    name: X('Presente continuo', 'المضارع المستمر', 'Present continuous'),
    structure: 'am/is/are + verbo-ing',
    explain: X('Acciones que ocurren ahora o alrededor de ahora, situaciones temporales y planes ya decididos para el futuro.',
      'لأفعال تحدث الآن أو في هذه الفترة، وللمواقف المؤقتة، وللخطط المؤكدة في المستقبل.'),
    examples: ["I'm looking for my keys.", 'They are living with her parents this month.', "We're leaving tomorrow."],
    find(lc) {
      return scan(rx(`\\b(?:am|is|are|isn't|aren't|i'm|you're|we're|they're|he's|she's|it's|what's|who's|that's|'m|'re)\\s+${ADV}?([a-z]{2,}ing)\\b`), lc,
        m => !ING_NOT_VERB.has(m[1]) && !ING_ADJ.has(m[1]) && !/^going\s+to\s/.test(lc.slice(lc.indexOf(m[1], m.index))));
    },
  },
  {
    id: 'past_simple', level: 'A2',
    name: X('Pasado simple', 'الماضي البسيط', 'Past simple'),
    structure: 'verbo-ed / irregular (went, saw…) · did (not) + verbo',
    explain: X('Acciones terminadas en un momento concreto del pasado. Los verbos regulares añaden -ed; los irregulares tienen forma propia. En preguntas y negaciones: did + verbo base.',
      'لأفعال انتهت في وقت محدّد في الماضي. الأفعال المنتظمة تأخذ ‎-ed، والشاذة لها صيغة خاصة. في السؤال والنفي: did + الفعل المجرد.'),
    examples: ['We met last summer.', "I didn't see anything.", 'Where did you go?'],
    tip: X('Después de did el verbo vuelve a la forma base: «Did you see?», nunca «Did you saw?».', 'بعد did يعود الفعل لصيغته المجردة: «Did you see?» وليس «Did you saw?».'),
    find(lc) {
      const pre = `(?<!\\b(?:have|has|had|'ve|'d|having|be|been|being|is|are|was|were|am|'m|'re|'s|get|gets|getting|got|will|would|can|could|should|must|might|may)\\s+${ADV}?)`;
      const a = scan(rx(`${pre}\\b(?:${PAST_IRR.replace(/\|could|\|was|\|were|\|had/g, '')}|[a-z]{2,}ed)\\b(?!')`), lc, m => !ED_NOT_VERB.has(m[0]) && !FEEL_ADJ.has(m[0]));
      const b = scan(rx(`(?<!\\bif\\s+(?:i|he|she|it)\\s+)\\b(?:was|were|wasn't|weren't)\\b(?!\\s+${ADV}?(?:[a-z]+ing|going|${PP})\\b)`), lc);
      const c = scan(/\b(?:did|didn't|did not)\b(?=\s+[a-z])/g, lc);
      const d = scan(rx(`\\bhad\\b(?!\\s+${ADV}?(?:${PP}|better)\\b)`), lc);
      return [...a, ...b, ...c, ...d];
    },
  },
  {
    id: 'past_continuous', level: 'A2',
    name: X('Pasado continuo', 'الماضي المستمر', 'Past continuous'),
    structure: 'was/were + verbo-ing',
    explain: X('Una acción en progreso en un momento del pasado, a menudo interrumpida por otra en pasado simple.',
      'فعل كان مستمرًا في لحظة من الماضي، وغالبًا ما يقطعه فعل آخر في الماضي البسيط.'),
    examples: ['I was sleeping when you called.', 'What were you doing last night?', 'They were talking about you.'],
    find(lc) { return scan(rx(`\\b(?:was|were|wasn't|weren't)\\s+${ADV}?([a-z]{2,}ing)\\b`), lc, m => !ING_NOT_VERB.has(m[1]) && !ING_ADJ.has(m[1]) && m[1] !== 'going'); },
  },
  {
    id: 'present_perfect', level: 'B1',
    name: X('Presente perfecto', 'المضارع التام', 'Present perfect'),
    structure: 'have/has + participio (done, seen, worked…)',
    explain: X('Conecta el pasado con el presente: experiencias (ever/never), acciones recientes con resultado ahora (just, already, yet) o situaciones que continúan (for/since). No se usa con fechas concretas del pasado.',
      'يربط الماضي بالحاضر: التجارب (ever/never)، أفعال حديثة لها نتيجة الآن (just, already, yet)، أو مواقف مستمرة (for/since). لا يُستعمل مع زمن محدّد في الماضي.'),
    examples: ["I've never been to London.", 'She has just left.', 'Have you ever seen this movie?'],
    tip: X('«I have seen it» (sin fecha) vs «I saw it yesterday» (fecha concreta → pasado simple).', '«I have seen it» (بدون وقت) مقابل «I saw it yesterday» (وقت محدّد ← الماضي البسيط).'),
    find(lc) {
      const after = (r) => lc.slice(r.e);
      const ok = (m, r) => !(/been$/.test(m[0]) && /^\s+[a-z]+ing\b/.test(after(r)));
      const a = scan(rx(`(?<!\\b(?:should|could|would|must|might|may|'d|shouldn't|couldn't|wouldn't|will|'ll|won't|to)\\s+(?:not\\s+)?)\\b(?:have|has|haven't|hasn't|'ve)\\s+${ADV}?(?:${PP})\\b`), lc, ok);
      const b = scan(rx(`\\b(?:he|she|it|that|there|who|what)'s\\s+${ADV}?(?:${PP_IRR})\\b`), lc, (m, r) => { const last = m[0].split(/\s+/).pop(); return ok(m, r) && (!FEEL_ADJ.has(last) || last === 'gone'); });
      const c = scan(rx(`\\b(?:have|has|haven't|hasn't)\\s+(?:i|you|he|she|it|we|they)\\s+${ADV}?(?:${PP})\\b`), lc, ok);
      return [...a, ...b, ...c];
    },
  },
  {
    id: 'present_perfect_cont', level: 'B1',
    name: X('Presente perfecto continuo', 'المضارع التام المستمر', 'Present perfect continuous'),
    structure: 'have/has been + verbo-ing',
    explain: X('Una actividad que empezó en el pasado y sigue (o acaba de parar), destacando la duración: for/since/all day.',
      'نشاط بدأ في الماضي وما زال مستمرًا (أو توقف للتو)، مع التركيز على المدة: for/since/all day.'),
    examples: ["I've been waiting for an hour.", 'She has been crying all day.', 'How long have you been working here?'],
    find(lc) { return scan(rx(`\\b(?:have|has|haven't|hasn't|'ve|'s)\\s+${ADV}?been\\s+[a-z]{2,}ing\\b|\\b(?:have|has)\\s+(?:i|you|he|she|it|we|they)\\s+been\\s+[a-z]+ing\\b`), lc); },
  },
  {
    id: 'past_perfect', level: 'B1',
    name: X('Pasado perfecto', 'الماضي التام', 'Past perfect'),
    structure: 'had + participio',
    explain: X('Una acción anterior a otra acción pasada («el pasado del pasado»). Muy común en narraciones y en el condicional tipo 3.',
      'فعل حدث قبل فعل آخر في الماضي («ماضي الماضي»). شائع في السرد وفي الشرطية من النوع الثالث.'),
    examples: ['When I arrived, the train had already left.', "I'd never seen her before.", 'She told me she had lost her job.'],
    find(lc) { return scan(rx(`\\b(?:had|hadn't|'d)\\s+${ADV}?(?:${PP})\\b`), lc, m => !/\bbetter$/.test(m[0]) && !/'d\s+(?:like|rather|love|prefer|say|go|come|get|make|take|run|put|let|set|cut|hit)$/.test(m[0])); },
  },
  {
    id: 'future_will', level: 'A2',
    name: X('Futuro con will', 'المستقبل بـ will', 'Future with will'),
    structure: "will / 'll / won't + verbo",
    explain: X('Decisiones del momento, promesas, ofrecimientos y predicciones basadas en opinión.', 'للقرارات اللحظية، والوعود، والعروض، والتوقعات المبنية على الرأي.'),
    examples: ["I'll call you later.", "Don't worry, I won't tell anyone.", 'I think it will rain.'],
    find(lc) { return scan(rx(`\\b(?:will|won't|'ll)\\s+(?:not\\s+)?(?:(?:i|you|he|she|it|we|they)\\s+)?(?!be\\s+[a-z]+ing\\b|have\\s+${PP}\\b)[a-z]+`), lc); },
  },
  {
    id: 'going_to', level: 'A2',
    name: X('Futuro con going to', 'المستقبل بـ going to', 'Going to'),
    structure: 'am/is/are + going to + verbo  (≈ gonna)',
    explain: X('Planes e intenciones ya decididos, o predicciones con evidencia presente («mira esas nubes: va a llover»). En el habla rápida suena «gonna».',
      'للخطط والنوايا المقررة مسبقًا، أو التوقعات المبنية على دليل حاضر. في الكلام السريع تُنطق «gonna».'),
    examples: ["I'm going to tell her the truth.", "It's going to rain.", "We're gonna be late!"],
    find(lc) { return scan(rx(`\\b(?:${BE.slice(3, -1)})\\s+(?:not\\s+)?going\\s+to\\s+[a-z]+|\\bgonna\\b(?:\\s+[a-z]+)?`), lc); },
  },
  {
    id: 'future_cont_perf', level: 'B2',
    name: X('Futuro continuo / perfecto', 'المستقبل المستمر / التام', 'Future continuous / perfect'),
    structure: 'will be + -ing · will have + participio',
    explain: X('«will be -ing»: algo en progreso en un momento futuro. «will have + participio»: algo terminado antes de un momento futuro.',
      '«will be -ing»: فعل سيكون مستمرًا في لحظة مستقبلية. «will have + التصريف الثالث»: فعل سينتهي قبل لحظة مستقبلية.'),
    examples: ["This time tomorrow I'll be flying to Paris.", "By Friday, we'll have finished the project."],
    find(lc) { return scan(rx(`\\b(?:will|won't|'ll)\\s+(?:not\\s+)?(?:be\\s+[a-z]+ing|have\\s+${PP})\\b`), lc); },
  },
  {
    id: 'passive', level: 'B1',
    name: X('Voz pasiva', 'المبني للمجهول', 'Passive voice'),
    structure: 'be (en cualquier tiempo) + participio  (+ by …)',
    explain: X('El foco está en la acción o en quien la recibe, no en quien la hace. El tiempo lo marca el verbo «be»: is made, was taken, has been sent, will be done.',
      'التركيز على الفعل أو على من يقع عليه، لا على الفاعل. يحدّد الزمنُ الفعلَ «be»: is made, was taken, has been sent, will be done.'),
    examples: ['The window was broken.', 'English is spoken all over the world.', 'He has been arrested.'],
    tip: X('También existe la pasiva con «get»: «He got fired» (lo despidieron).', 'توجد أيضًا صيغة المجهول بـ «get»: «He got fired» (طُرد من عمله).'),
    find(lc) {
      return scan(rx(`\\b(?:${BE.slice(3, -1)}|get|gets|got|getting)\\s+${ADV}?(${PP})\\b`), lc,
        (m, r) => !FEEL_ADJ.has(m[1]) && !ED_NOT_VERB.has(m[1]) && !/^(?:been|had|got|gotten|gone)$/.test(m[1]) && !/^\s+to\b/.test(lc.slice(r.e)) || (m[1] === 'born'));
    },
  },
  {
    id: 'modals', level: 'A2',
    name: X('Verbos modales', 'الأفعال الناقصة (Modals)', 'Modal verbs'),
    structure: 'modal + verbo base (sin «to», sin -s)',
    explain: X('Añaden matices de capacidad, permiso, consejo, obligación o probabilidad. Nunca llevan -s ni «to» después.', 'تضيف معاني القدرة أو الإذن أو النصيحة أو الإلزام أو الاحتمال. لا تأخذ ‎-s ولا يأتي بعدها «to».'),
    examples: ['Can you help me?', 'You should see a doctor.', 'It might be true.'],
    details: {
      can: { name: X('can — poder (capacidad / permiso)', 'can — القدرة / الإذن'), examples: ['I can swim.', 'Can I sit here?'] },
      could: { name: X('could — podía / podría (pasado, posibilidad, petición educada)', 'could — كان يستطيع / قد / طلب مهذب'), examples: ['Could you open the door?', 'It could be dangerous.'] },
      should: { name: X('should — debería (consejo, expectativa)', 'should — ينبغي (نصيحة، توقّع)'), examples: ['You should rest.', 'They should be here soon.'] },
      would: { name: X('would — -ría (hipótesis, cortesía, hábito pasado)', 'would — شرط/افتراض، تأدّب، عادة في الماضي'), examples: ['I would never do that.', 'Would you like some tea?'] },
      must: { name: X('must — deber (obligación fuerte / deducción segura)', 'must — يجب (إلزام قوي / استنتاج مؤكد)'), examples: ['You must wear a seatbelt.', 'You must be tired.'] },
      might: { name: X('might — quizás (posibilidad baja)', 'might — ربما (احتمال ضعيف)'), examples: ['I might go to the party.', 'He might not know.'] },
      may: { name: X('may — puede que / permiso formal', 'may — قد / إذن رسمي'), examples: ['May I come in?', 'It may take a while.'] },
      shall: { name: X('shall — ¿…? (ofrecer, sugerir)', 'shall — للعرض والاقتراح'), examples: ['Shall we go?', 'Shall I open the window?'] },
    },
    find(lc) {
      return scan(rx(`\\b(can|could|should|would|must|might|may|shall|can't|cannot|couldn't|shouldn't|wouldn't|mustn't|mightn't)\\b(?:\\s+not)?(?:\\s+(?:i|you|he|she|it|we|they))?(?:\\s+(?!have\\s+${PP})[a-z']+)?`), lc,
        (m, r) => { const base = m[1].replace(/n't$/, '').replace(/not$/, ''); r.detail = base === 'ca' ? 'can' : base; return !/\b(?:would|'d)\s+(?:rather|like|love)\b/.test(m[0]); });
    },
  },
  {
    id: 'modal_perfect', level: 'B2',
    name: X('Modales en pasado', 'الأفعال الناقصة في الماضي', 'Modal perfect'),
    structure: 'should / could / would / must / might + have + participio',
    explain: X('Hablan del pasado: arrepentimiento o crítica (should have), posibilidades no realizadas (could have), deducciones (must have) o hipótesis (would have).',
      'للحديث عن الماضي: الندم أو اللوم (should have)، احتمالات لم تحدث (could have)، استنتاج (must have)، أو افتراض (would have).'),
    examples: ['You should have told me.', 'She must have forgotten.', 'I would have helped you.'],
    tip: X("En el habla suena «shoulda / coulda / woulda» (should've).", "في الكلام السريع تُنطق «shoulda / coulda / woulda» (should've)."),
    find(lc) { return scan(rx(`\\b(?:should|could|would|must|might|may|'d|shouldn't|couldn't|wouldn't)\\s+(?:not\\s+)?(?:have|'ve|of)\\s+${ADV}?${PP}\\b|\\b(?:shoulda|coulda|woulda)\\b`), lc); },
  },
  {
    id: 'obligation', level: 'A2',
    name: X('Obligación y necesidad', 'الإلزام والحاجة', 'Obligation & necessity'),
    structure: 'have to / has to / had to / need to / have got to (gotta) + verbo',
    explain: X('Obligación externa o necesidad. «don’t have to» = no es necesario (≠ «mustn’t» = está prohibido).', 'إلزام خارجي أو حاجة. «don’t have to» = ليس ضروريًا (≠ «mustn’t» = ممنوع).'),
    examples: ['I have to go now.', "You don't have to come.", 'We need to talk.'],
    find(lc) { return scan(/\b(?:have|has|had|having)\s+(?:got\s+)?to\s+[a-z]+|\b(?:need|needs|needed)\s+to\s+[a-z]+|\bgotta\b(?:\s+[a-z]+)?|\bhafta\b/g, lc); },
  },
  {
    id: 'conditional', level: 'B1',
    name: X('Oraciones condicionales', 'الجمل الشرطية', 'Conditionals'),
    structure: 'if + condición, resultado',
    explain: X('Expresan una condición y su resultado. El tipo depende de lo real o imaginario que sea.', 'تعبّر عن شرط ونتيجته. يتحدّد النوع بحسب واقعية الشرط.'),
    details: {
      0: { name: X('Condicional 0 (verdades)', 'الشرطية 0 (حقائق)'), structure: 'if + presente, presente', explain: X('Algo que siempre ocurre si se cumple la condición.', 'شيء يحدث دائمًا عند تحقق الشرط.'), examples: ['If you heat ice, it melts.'] },
      1: { name: X('Condicional 1 (posible)', 'الشرطية 1 (ممكنة)'), structure: 'if + presente, will/can/imperativo + verbo', explain: X('Situación real o probable en el futuro.', 'موقف حقيقي أو محتمل في المستقبل.'), examples: ['If it rains, we will stay home.', 'If you see him, tell him to call me.'] },
      2: { name: X('Condicional 2 (imaginario)', 'الشرطية 2 (افتراضية)'), structure: 'if + pasado (were), would/could + verbo', explain: X('Situación hipotética o poco probable en el presente/futuro. Con «be» se usa «were» para todas las personas: «If I were you…».', 'موقف افتراضي أو غير محتمل في الحاضر/المستقبل. مع «be» نستعمل «were» لكل الضمائر: «If I were you…».'), examples: ['If I had money, I would travel.', 'If I were you, I would call her.'] },
      3: { name: X('Condicional 3 (pasado irreal)', 'الشرطية 3 (ماضٍ غير واقعي)'), structure: 'if + had + participio, would have + participio', explain: X('Un pasado que no ocurrió y su resultado imaginario; muchas veces expresa arrepentimiento.', 'ماضٍ لم يحدث ونتيجته المتخيّلة؛ غالبًا للتعبير عن الندم.'), examples: ['If you had told me, I would have helped you.'] },
      mixed: { name: X('Condicional (unless / mixto)', 'شرطية (unless / مختلطة)'), structure: 'unless = if … not', explain: X('«unless» significa «a menos que / si no».', '«unless» تعني «إلا إذا».'), examples: ["I won't go unless you come with me."] },
    },
    find(lc) {
      const m = /\b(if|unless)\b/.exec(lc); if (!m) return [];
      let type;
      const ifPart = lc.slice(m.index);
      if (m[1] === 'unless') type = 'mixed';
      else if (rx(`\\bhad\\s+(?:not\\s+)?${PP}`, '').test(ifPart) && /\b(?:would|could|might|'d|wouldn't|couldn't)\s+(?:not\s+)?(?:have|'ve)\b/.test(lc)) type = 3;
      else if (/\b(?:would|could|might|wouldn't|couldn't|'d)\b/.test(lc)) type = 2;
      else if (/\b(?:will|'ll|won't|can|can't|may|might|should|must|going to|gonna)\b/.test(lc) || /^\s*[a-z]+\b/.test(lc.slice(lc.indexOf(',') + 1)) && lc.includes(',')) type = 1;
      else type = 0;
      // "if" meaning "whether" after verbs like know/ask/wonder is not a conditional.
      if (/\b(?:know|ask|asked|wonder|wondering|see|sure|check|tell me)\s+if\b/.test(lc) && type === 0) return [];
      return [{ s: m.index, e: lc.length, detail: type }];
    },
  },
  {
    id: 'wish', level: 'B2',
    name: X('Deseos: wish / if only', 'التمنّي: wish / if only', 'Wishes'),
    structure: 'wish + pasado · wish + had + participio · wish + would',
    explain: X('«I wish + pasado» = desearía que el presente fuera distinto. «I wish + had + participio» = arrepentimiento del pasado. «I wish you would…» = queja o deseo de que alguien cambie.',
      '«I wish + ماضٍ» = أتمنى لو كان الحاضر مختلفًا. «I wish + had + تصريف ثالث» = ندم على الماضي. «I wish you would…» = تذمّر أو رغبة في أن يتغيّر شخص ما.'),
    examples: ['I wish I knew the answer.', "I wish I hadn't said that.", 'If only you were here.'],
    find(lc) { return scan(/\b(?:wish|wishes|wished)\b(?!\s+(?:you|him|her|them|us|me)\s+(?:a|an|luck|good|happy|merry|all)\b)(?:\s+[a-z']+){0,3}|\bif only\b(?:\s+[a-z']+){0,3}/g, lc); },
  },
  {
    id: 'questions', level: 'A1',
    name: X('Preguntas', 'الأسئلة', 'Questions'),
    structure: '(Wh-) + auxiliar + sujeto + verbo?',
    explain: X('En inglés el auxiliar va delante del sujeto: «Are you…?», «Did she…?», «What do you…?».', 'في الإنجليزية يأتي الفعل المساعد قبل الفاعل: «Are you…?»، «Did she…?»، «What do you…?».'),
    details: {
      wh: { name: X('Pregunta Wh- (información)', 'سؤال Wh- (طلب معلومة)'), structure: 'What/Where/Why/How… + auxiliar + sujeto + verbo', explain: X('Pide información. La entonación suele BAJAR al final ↘.', 'يطلب معلومة. ينخفض التنغيم في النهاية عادةً ↘.'), examples: ['Where do you live?', 'Why did you do that?'] },
      yesno: { name: X('Pregunta de sí/no', 'سؤال نعم/لا'), structure: 'Auxiliar (do/is/can/have…) + sujeto + verbo', explain: X('Se responde con sí o no. La entonación SUBE al final ↗.', 'يُجاب عنه بنعم أو لا. يرتفع التنغيم في النهاية ↗.'), examples: ['Is it my fault?', 'Can you hear me?'] },
      tag: { name: X('Question tag (¿verdad?)', 'سؤال ذيلي (أليس كذلك؟)'), structure: 'afirmación, + auxiliar negativo + pronombre?', explain: X('Una coletilla para confirmar: frase positiva → tag negativo y viceversa. Baja ↘ si estás seguro, sube ↗ si de verdad preguntas.', 'ذيل للتأكيد: جملة مثبتة ← ذيل منفي والعكس. ينخفض ↘ إن كنت متأكدًا ويرتفع ↗ إن كنت تسأل فعلًا.'), examples: ["It's cold, isn't it?", "You didn't call him, did you?"] },
      statement: { name: X('Pregunta con forma de afirmación', 'سؤال بصيغة الخبر'), structure: 'sujeto + verbo …?', explain: X('En el habla informal se pregunta con orden de afirmación y entonación ascendente ↗.', 'في الكلام غير الرسمي نسأل بترتيب الجملة الخبرية مع تنغيم صاعد ↗.'), examples: ['You did it?', "She's coming?"] },
    },
    find(lc) {
      const out = [];
      const re = /[^.!?]*\?/g; let m;
      while ((m = re.exec(lc))) {
        const raw = m[0]; const lead = raw.match(/^[\s"'(\-–—]*/)[0].length;
        const q = raw.slice(lead).trim(); if (q.length < 2) continue;
        let detail;
        if (/,\s*(?:isn't|aren't|wasn't|weren't|don't|doesn't|didn't|haven't|hasn't|won't|wouldn't|can't|couldn't|shouldn't|is|are|was|were|do|does|did|have|has|will|would|can|could|right|okay|ok|huh|yeah)\s*(?:it|he|she|they|you|we|i|there|that)?\s*\?$/.test(q)) detail = 'tag';
        else if (/^(?:and\s+|but\s+|so\s+|then\s+|oh\s+|well\s+)?(?:what|why|where|when|who|whom|whose|which|how)\b/.test(q)) detail = 'wh';
        else if (/^(?:and\s+|but\s+|so\s+|oh\s+|well\s+)?(?:do|does|did|is|are|was|were|have|has|had|can|could|will|would|should|may|might|must|shall|am|isn't|aren't|don't|doesn't|didn't|won't|can't|wouldn't|couldn't|haven't|hasn't)\b/.test(q)) detail = 'yesno';
        else detail = 'statement';
        out.push({ s: m.index + lead, e: m.index + raw.length, detail });
      }
      return out;
    },
  },
  {
    id: 'indirect_question', level: 'B1',
    name: X('Pregunta indirecta', 'السؤال غير المباشر', 'Indirect question'),
    structure: 'Do you know / I wonder / tell me + wh-/if + sujeto + verbo',
    explain: X('Dentro de otra frase, la pregunta pierde la inversión: «Do you know where he IS?» (no «where is he»).', 'داخل جملة أخرى يفقد السؤال ترتيبه المقلوب: «Do you know where he IS?» وليس «where is he».'),
    examples: ['Do you know where the station is?', "I don't know what you mean.", 'I wonder if she is okay.'],
    find(lc) { return scan(/\b(?:know|knows|knew|wonder|wondering|tell me|ask|asked|sure|idea|remember|understand|guess|explain|find out|figure out|see)\s+(?:what|where|when|why|how|who|whether|if|which)\b(?:\s+[a-z']+){0,3}/g, lc); },
  },
  {
    id: 'do_negation', level: 'A1',
    name: X('Negación con do/does/did', 'النفي بـ do/does/did', 'Negation with do'),
    structure: "don't / doesn't / didn't + verbo base",
    explain: X('Para negar verbos normales se usa el auxiliar do (presente), does (he/she/it) o did (pasado) + not + verbo base.', 'لنفي الأفعال العادية نستعمل do (مضارع) أو does (he/she/it) أو did (ماضٍ) + not + الفعل المجرد.'),
    examples: ["I don't like it.", "He doesn't care.", "We didn't know."],
    find(lc) { return scan(/\b(?:don't|doesn't|didn't|do not|does not|did not)\s+(?:really\s+|even\s+|just\s+|ever\s+|always\s+)?[a-z]+/g, lc); },
  },
  {
    id: 'emphatic_do', level: 'B1',
    name: X('Do enfático', 'do للتوكيد', 'Emphatic do'),
    structure: 'sujeto + do/does/did + verbo base (afirmativo)',
    explain: X('Añadir do/does/did en una frase afirmativa da énfasis o contradice: «I DO love you» (¡claro que te quiero!).', 'إضافة do/does/did في جملة مثبتة تفيد التوكيد أو الرد على شك: «I DO love you».'),
    examples: ['I do love you.', 'She did call, I promise.'],
    find(lc) { return scan(/\b(?:i|you|we|they|he|she|it)\s+(?:do|does|did)\s+(?:love|want|know|like|need|think|care|remember|hope|mean|believe|understand|feel|see|try|miss|have|appreciate|agree)\b/g, lc); },
  },
  {
    id: 'imperative', level: 'A1',
    name: X('Imperativo', 'صيغة الأمر', 'Imperative'),
    structure: "verbo base … · don't + verbo",
    explain: X('Órdenes, instrucciones, consejos o invitaciones. No lleva sujeto. Para suavizar: «please», «just».', 'للأوامر والتعليمات والنصائح والدعوات. لا يُذكر الفاعل. للتلطيف: «please»، «just».'),
    examples: ['Sit down, please.', "Don't worry.", 'Look at this!'],
    find(lc) {
      const out = [];
      const re = /(^|[.!?]\s+|["'—–-]\s*)((?:please\s+|just\s+|now\s+|oh\s+|hey,?\s+)?(?:don't\s+|do not\s+|never\s+)?(?:go|come|look|listen|wait|stop|tell|give|take|get|be|have|make|try|keep|leave|help|sit|stand|put|bring|call|run|follow|check|watch|hold|calm|shut|move|turn|open|close|remember|forget|think|say|show|find|ask|stay|hurry|relax|trust|believe|let|answer|forgive|excuse|imagine|enjoy|thank|drop|hang|pick|stay|step|grab|eat|drink|read|write|sleep|wake|meet|kill|save|drive|worry|touch|speak|talk|smile|breathe|focus|shoot|push|pull)\b)/g;
      let m;
      while ((m = re.exec(lc))) {
        const start = m.index + m[1].length;
        const rest = lc.slice(start); const end = rest.search(/[.!?]|$/);
        const sentence = rest.slice(0, end === -1 ? rest.length : end + 1);
        if (/\?$/.test(sentence.trim()) && !/^(?:please\s+)?(?:don't|do not)\b/.test(sentence)) continue;
        if (/^(?:let me|let's|let us)\b/.test(lc.slice(start)) || /^(?:be|have|get|go|come|keep)\s+(?:i|you|he|she|we|they)\b/.test(sentence)) continue;
        out.push({ s: start, e: start + m[2].length });
        if (re.lastIndex === m.index) re.lastIndex++;
      }
      return out;
    },
  },
  {
    id: 'lets', level: 'A1',
    name: X("Let's / Let me", "Let's / Let me", "Let's / Let me"),
    structure: "let's + verbo (sugerencia) · let me + verbo (ofrecerse / pedir permiso)",
    explain: X("«Let's» = vamos a… (propuesta para nosotros). «Let me» = déjame… En el habla: «lemme».", "«Let's» = هيا بنا… (اقتراح لنا جميعًا). «Let me» = دعني… وتُنطق «lemme»."),
    examples: ["Let's go!", 'Let me help you.', "Let's not argue."],
    find(lc) { return scan(/\b(?:let's|let us|let me|lemme)\s+(?:not\s+)?[a-z]+/g, lc); },
  },
  {
    id: 'there_be', level: 'A1',
    name: X('There is / There are', 'There is / There are', 'There is / are'),
    structure: 'there + be (is/are/was/were/will be…) + sustantivo',
    explain: X('Para decir que algo existe o hay algo. Singular «there is», plural «there are».', 'للتعبير عن وجود شيء (يوجد/هناك). مفرد «there is» وجمع «there are».'),
    examples: ["There's a problem.", 'There were many people.', 'Is there anything I can do?'],
    find(lc) { return scan(/\bthere\s+(?:is|are|was|were|isn't|aren't|wasn't|weren't|will be|won't be|has been|have been|had been|must be|might be|could be|used to be|seems to be)\b|\bthere's\b|\b(?:is|are|was|were)\s+there\b/g, lc); },
  },
  {
    id: 'comparative', level: 'A2',
    name: X('Comparativos', 'المقارنة', 'Comparatives'),
    structure: 'adj-er than · more + adj + than · as + adj + as',
    explain: X('Para comparar dos cosas. Adjetivos cortos: -er (bigger); largos: more (more expensive). Igualdad: as … as. Irregulares: good → better, bad → worse.',
      'لمقارنة شيئين. الصفات القصيرة: ‎-er (bigger)؛ الطويلة: more (more expensive). المساواة: as … as. الشاذة: good ← better، bad ← worse.'),
    examples: ['She is taller than me.', 'This is more important than money.', "It's not as easy as it looks."],
    find(lc) { return scan(/\b(?:more|less|fewer)\s+[a-z]+\s+than\b|\b[a-z]{2,}er\s+than\b|\b(?:better|worse|more|less|fewer|rather|other)\s+than\b|\bas\s+(?:much|many|[a-z]+)\s+as\b|\bthe\s+(?:more|less|better)\b[^,]*,\s*the\s+(?:more|less|better)\b/g, lc); },
  },
  {
    id: 'superlative', level: 'A2',
    name: X('Superlativos', 'صيغة التفضيل العليا', 'Superlatives'),
    structure: 'the + adj-est · the most/least + adj',
    explain: X('El extremo de un grupo: the biggest, the most beautiful, the best, the worst. Suele ir con «the».', 'أقصى درجة في مجموعة: the biggest، the most beautiful، the best، the worst. يأتي عادةً مع «the».'),
    examples: ["It's the best day of my life.", 'She is the most intelligent person I know.'],
    find(lc) { return scan(/\b(?:the|my|your|his|her|our|their)\s+(?:(?:most|least)\s+[a-z]+|best|worst|[a-z]{2,}est)\b/g, lc, m => !SUP_NOT.has(m[0].split(/\s+/).pop()) || /best|worst/.test(m[0])); },
  },
  {
    id: 'relative', level: 'B1',
    name: X('Oraciones de relativo', 'جمل الصلة (Relative clauses)', 'Relative clauses'),
    structure: 'sustantivo + who / which / that / whose / where + …',
    explain: X('Dan información sobre un sustantivo: who (personas), which (cosas), that (personas o cosas), whose (posesión), where (lugares). A menudo «that» se omite: «the man (that) I saw».',
      'تضيف معلومات عن اسم: who (للأشخاص)، which (للأشياء)، that (للأشخاص والأشياء)، whose (للملكية)، where (للأماكن). كثيرًا ما تُحذف «that»: «the man (that) I saw».'),
    examples: ['The woman who called you is here.', 'Everything that happened was my fault.', "That's the place where we met."],
    find(lc) {
      const a = scan(/(?<=\b[a-z']+[,]?\s)(?:who|which|whose|whom)\b/g, lc, (m, r) => !/\b(?:know|wonder|ask|tell|sure|idea|guess|see|asked|knew|explain|understand|remember|matter|decide)\s*$/.test(lc.slice(0, r.s)) && !/[?]/.test(lc.slice(r.s).split(/[.!]/)[0]) || /,\s*$/.test(lc.slice(0, r.s)));
      const b = scan(/\b(?:something|anything|everything|nothing|someone|anyone|everyone|somebody|anybody|all|the (?:one|only|first|last|thing|person|man|woman|guy|people|way|reason))\s+that\b/g, lc);
      const c = scan(/\b(?:place|house|city|room|town|country|day|time|moment|year|reason|night)\s+(?:where|when|why)\b/g, lc);
      return [...a, ...b, ...c];
    },
  },
  {
    id: 'reported', level: 'B1',
    name: X('Estilo indirecto', 'الكلام المنقول', 'Reported speech'),
    structure: 'said (that) … · told + persona + (that/to) · asked + if/to',
    explain: X('Contar lo que otra persona dijo. Los tiempos suelen «retroceder»: «I am tired» → «She said she was tired». «say» no lleva persona; «tell» sí: «told me».',
      'لنقل ما قاله شخص آخر. ترجع الأزمنة عادةً خطوة إلى الماضي: «I am tired» ← «She said she was tired». «say» بدون مفعول، و«tell» مع شخص: «told me».'),
    examples: ['He said that he was busy.', 'She told me to wait.', 'They asked if I was okay.'],
    find(lc) { return scan(/\b(?:said|says|told|tells|asked|explained|mentioned|promised|admitted|claimed|warned)\b(?:\s+(?:me|him|her|us|them|you|everyone))?\s+(?:that|to|if|whether|(?:i|you|he|she|it|we|they)\b)/g, lc); },
  },
  {
    id: 'gerund_after', level: 'B1',
    name: X('Verbo + -ing (gerundio)', 'فعل + ‎-ing', 'Verb + -ing'),
    structure: 'enjoy / stop / keep / mind / avoid / finish / miss… + verbo-ing',
    explain: X('Algunos verbos van seguidos de -ing, no de «to». También tras preposiciones: «good at swimming», «thanks for coming».',
      'بعض الأفعال يأتي بعدها ‎-ing وليس «to». وكذلك بعد حروف الجر: «good at swimming»، «thanks for coming».'),
    examples: ['I enjoy reading.', 'Stop talking!', 'Thanks for coming.'],
    tip: X('«stop smoking» (dejar de fumar) ≠ «stop to smoke» (pararse para fumar).', '«stop smoking» (التوقف عن التدخين) ≠ «stop to smoke» (التوقف من أجل التدخين).'),
    find(lc) { return scan(/\b(?:enjoy|enjoys|enjoyed|mind|minds|avoid|avoided|stop|stops|stopped|keep|keeps|kept|finish|finished|consider|considered|imagine|miss|missed|suggest|suggested|admit|admitted|deny|denied|practice|quit|risk|can't stand|feel like|felt like|thanks for|thank you for|good at|bad at|interested in|tired of|instead of|before|after|without|about|used to|look forward to)\s+(?!thing|nothing|something|anything|everything|morning|evening)[a-z]{2,}ing\b/g, lc); },
  },
  {
    id: 'infinitive_after', level: 'A2',
    name: X('Verbo + to + infinitivo', 'فعل + to + المصدر', 'Verb + to-infinitive'),
    structure: 'want / need / decide / try / hope / plan… + (persona) + to + verbo',
    explain: X('Muchos verbos van seguidos de «to + verbo». Con want/ask/tell podemos poner a la persona en medio: «I want YOU to stay».',
      'كثير من الأفعال يتبعها «to + فعل». ومع want/ask/tell يمكن وضع الشخص في الوسط: «I want YOU to stay».'),
    examples: ['I want to go home.', 'She decided to leave.', 'I need you to listen.'],
    tip: X("want to → «wanna» al hablar rápido.", "want to ← تُنطق «wanna» في الكلام السريع."),
    find(lc) { return scan(/\b(?:want|wants|wanted|decide|decides|decided|hope|hopes|hoped|plan|plans|planned|try|tries|tried|trying|learn|learned|agree|agreed|promise|promised|refuse|refused|seem|seems|seemed|expect|expected|manage|managed|afford|offer|offered|pretend|pretended|deserve|deserves|choose|chose|tend|tends|ask|asked|tell|told|would like|'d like|love|like|hate|prefer|begin|began|start|started|wait|waited|happen|happened|mean|meant|forget|forgot|remember)\s+(?:(?:me|you|him|her|us|them|it|someone)\s+)?to\s+(?!the\b|a\b|an\b|my\b|your\b|his\b|her\b|me\b|you\b|him\b|us\b|them\b|it\b)[a-z]+/g, lc); },
  },
  {
    id: 'phrasal', level: 'B1',
    name: X('Phrasal verbs', 'الأفعال المركّبة (Phrasal verbs)', 'Phrasal verbs'),
    structure: 'verbo + partícula (up, out, on, off…)',
    explain: X('Verbo + partícula con un significado nuevo, muchas veces imposible de adivinar palabra por palabra. Son clave para entender películas y conversaciones.',
      'فعل + أداة يعطيان معنى جديدًا لا يُفهم غالبًا من الكلمات منفردة. أساسية لفهم الأفلام والمحادثات.'),
    find(lc) {
      const out = [];
      for (const p of PHRASAL_RE) for (const r of scan(p.re, lc)) out.push({ ...r, detail: `${p.v} ${p.p}`, meaning: { es: p.es, ar: p.ar, en: `${p.v} ${p.p}` } });
      return out;
    },
  },
  {
    id: 'used_to', level: 'B1',
    name: X('Used to / be used to', 'Used to / be used to', 'Used to'),
    structure: 'used to + verbo (hábito pasado) · be/get used to + -ing (estar acostumbrado)',
    explain: X('«I used to play» = antes jugaba (ya no). «I’m used to working late» = estoy acostumbrado. «get used to» = acostumbrarse.',
      '«I used to play» = كنت ألعب سابقًا (ولم أعد). «I’m used to working late» = أنا معتاد. «get used to» = يعتاد على.'),
    examples: ['I used to live here.', "I'm not used to this.", "You'll get used to it."],
    find(lc) { return scan(/\b(?:used|use)\s+to\s+[a-z]+/g, lc, (m, r) => /\b(?:used|did|didn't|be|is|are|was|were|am|'m|'re|'s|get|got|getting)\s*$|^/.test(lc.slice(0, r.s)) && !/\b(?:is|are|was|were|be|been)\s+used\s+to\s+(?:make|do|build|create|cut|describe|treat|help|keep|hold|store)\b/.test(lc)); },
  },
  {
    id: 'supposed_to', level: 'B1',
    name: X('Be supposed to', 'Be supposed to', 'Be supposed to'),
    structure: 'be + supposed to + verbo',
    explain: X('Lo que se espera o está previsto (pero a veces no ocurre): «se supone que…».', 'ما هو متوقَّع أو مقرَّر (وقد لا يحدث): «من المفترض أن…».'),
    examples: ["You're supposed to be at work.", 'What am I supposed to do?'],
    find(lc) { return scan(/\b(?:am|is|are|was|were|'m|'re|'s|isn't|aren't|wasn't|weren't|i|you|we|they|he|she|it)\s+(?:not\s+)?supposed\s+to\s+[a-z]+/g, lc); },
  },
  {
    id: 'rather_better', level: 'B2',
    name: X("Would rather / Had better", "Would rather / Had better", "Would rather / Had better"),
    structure: "would rather + verbo (preferencia) · had better + verbo (advertencia)",
    explain: X("«I'd rather stay» = prefiero quedarme. «You'd better go» = más te vale irte (consejo fuerte / advertencia).", "«I'd rather stay» = أفضّل البقاء. «You'd better go» = من الأفضل لك أن تذهب (تحذير / نصيحة قوية)."),
    examples: ["I'd rather not talk about it.", "You'd better hurry."],
    find(lc) { return scan(/\b(?:would|'d)\s+rather\b(?:\s+not)?(?:\s+[a-z]+)?|\b(?:had|'d)\s+better\b(?:\s+not)?(?:\s+[a-z]+)?/g, lc); },
  },
  {
    id: 'would_like', level: 'A2',
    name: X("Would like (petición educada)", "Would like (طلب مهذّب)", "Would like"),
    structure: "would ('d) like + sustantivo / to + verbo",
    explain: X("Forma educada de «want»: «I'd like a coffee», «Would you like to come?».", "صيغة مهذّبة لـ «want»: «I'd like a coffee»، «Would you like to come?»."),
    examples: ["I'd like a full security audit.", 'Would you like some tea?'],
    find(lc) { return scan(/\b(?:would|'d)\s+(?:(?:you|he|she|they|we|i)\s+)?(?:like|love)\b(?:\s+(?:to\s+)?[a-z]+)?/g, lc); },
  },
  {
    id: 'causative', level: 'B2',
    name: X('Causativo: make / let / have / get', 'السببية: make / let / have / get', 'Causative'),
    structure: 'make/let + persona + verbo · have/get + algo + participio',
    explain: X('«make someone do» = obligar; «let someone do» = permitir; «have/get something done» = que otro lo haga por ti («I had my hair cut»).',
      '«make someone do» = إجبار؛ «let someone do» = سماح؛ «have/get something done» = أن يقوم غيرك بالعمل لك («I had my hair cut»).'),
    examples: ["Don't make me laugh.", 'Let me know.', 'I need to get my car fixed.'],
    find(lc) {
      const a = scan(/\b(?:make|makes|made|making|let|lets|letting|help|helped|helps)\s+(?:me|you|him|her|us|them|it|everyone|people)\s+(?!to\b|be\b|a\b|the\b)[a-z]+/g, lc, m => !/^let\s+me\b/.test(m[0]));
      const b = scan(rx(`\\b(?:have|has|had|get|gets|got|getting)\\s+(?:my|your|his|her|our|their|the|it)\\s+(?:[a-z]+\\s+)?(?:${PP_IRR}|[a-z]{2,}ed)\\b`), lc, m => !ED_NOT_VERB.has(m[0].split(/\s+/).pop()));
      return [...a, ...b];
    },
  },
  {
    id: 'feeling_adj', level: 'A2',
    name: X('Adjetivos -ed / -ing', 'صفات ‎-ed / ‎-ing', '-ed / -ing adjectives'),
    structure: 'I am bored (-ed: cómo me siento) · It is boring (-ing: cómo es)',
    explain: X('-ed describe cómo se siente alguien; -ing describe qué produce ese sentimiento. «I’m bored» (estoy aburrido) ≠ «I’m boring» (soy aburrido).',
      '‎-ed تصف شعور الشخص؛ ‎-ing تصف ما يسبّب ذلك الشعور. «I’m bored» (أشعر بالملل) ≠ «I’m boring» (أنا مُمِلّ).'),
    examples: ["I'm so tired.", 'This movie is amazing.', 'She looks worried.'],
    find(lc) {
      return scan(/\b(?:am|is|are|was|were|be|been|'m|'re|'s|feel|feels|felt|look|looks|looked|seem|seems|seemed|get|gets|got|getting|sound|sounds)\s+(?:so\s+|very\s+|really\s+|too\s+|pretty\s+|quite\s+|a bit\s+|kind of\s+|kinda\s+|not\s+)?([a-z]+)\b/g, lc,
        m => FEEL_ADJ.has(m[1]) && !/^(?:done|finished|gone|supposed|used|lost|closed|fed|upset|drunk|stuck)$/.test(m[1]) || ING_ADJ.has(m[1]));
    },
  },
  {
    id: 'too_enough', level: 'A2',
    name: X('Too / enough', 'Too / enough', 'Too / enough'),
    structure: 'too + adj (+ to …) · adj + enough · enough + sustantivo',
    explain: X('«too» = demasiado (problema); «enough» = suficiente. Ojo: «enough» va DESPUÉS del adjetivo («old enough») y ANTES del sustantivo («enough time»).',
      '«too» = أكثر من اللازم (مشكلة)؛ «enough» = كافٍ. انتبه: «enough» تأتي بعد الصفة («old enough») وقبل الاسم («enough time»).'),
    examples: ["It's too late.", "You're not old enough.", "We don't have enough time."],
    find(lc) { return scan(/\btoo\s+(?:much|many|[a-z]{2,})\b(?!\s*[.?!,]?\s*$)|\b[a-z]{3,}\s+enough\b|\benough\s+[a-z]+\b/g, lc, m => !/^too\s+(?:and|but|so|then)$/.test(m[0])); },
  },
  {
    id: 'about_to', level: 'B1',
    name: X('Be about to', 'Be about to', 'Be about to'),
    structure: 'be + about to + verbo',
    explain: X('Algo que va a ocurrir inmediatamente: «estar a punto de».', 'شيء على وشك الحدوث فورًا: «على وشك أن».'),
    examples: ["I'm about to leave.", 'The movie is about to start.'],
    find(lc) { return scan(/\b(?:am|is|are|was|were|'m|'re|'s)\s+(?:just\s+)?about\s+to\s+[a-z]+/g, lc); },
  },
  {
    id: 'contractions', level: 'A1',
    name: X('Contracciones', 'الاختصارات (Contractions)', 'Contractions'),
    structure: "I'm = I am · don't = do not · I'll = I will · I'd = I would/had …",
    explain: X('Formas cortas típicas del inglés hablado. Reconocerlas es clave para entender y para que tu shadowing suene natural.', 'صيغ مختصرة نموذجية في الإنجليزية المحكية. التعرّف عليها ضروري للفهم ولكي يبدو تقليدك طبيعيًا.'),
    find(lc) {
      return scan(/\b(?:[a-z]+(?:'m|'re|'s|'ve|'ll|'d|n't)|can't|won't|ain't|let's|y'all)\b/g, lc, (m, r) => { r.detail = m[0]; return true; });
    },
  },
  {
    id: 'reductions', level: 'B1',
    name: X('Reducciones del habla informal', 'اختصارات الكلام العامي', 'Informal reductions'),
    structure: 'gonna · wanna · gotta · kinda · lemme · gimme · dunno · ya',
    explain: X('Así se escribe a veces lo que en realidad se pronuncia rápido. Entiéndelas, pero en textos formales usa la forma completa.', 'هكذا يُكتب أحيانًا ما يُنطق بسرعة. افهمها، لكن في الكتابة الرسمية استخدم الصيغة الكاملة.'),
    find(lc) { return scan(/\b(?:gonna|wanna|gotta|kinda|sorta|lemme|gimme|dunno|ya|y'all|'cause|cuz|outta|lotta|whatcha|gotcha|ain't|innit|'em|c'mon|nope|yep|yeah|hafta|oughta|betcha|tryna|lotsa|shoulda|coulda|woulda|musta|alright|'til)\b/g, lc, (m, r) => { r.detail = m[0]; return true; }); },
  },
];

export const CONTRACTION_EXPANSION = {
  "'m": 'am', "'re": 'are', "'ve": 'have', "'ll": 'will', "n't": 'not', "'d": 'would / had', "'s": 'is / has',
  "can't": 'cannot', "won't": 'will not', "ain't": "am not / isn't / haven't (informal)", "let's": 'let us', "y'all": 'you all', "shan't": 'shall not',
};
export function expandContraction(c) {
  c = c.toLowerCase();
  if (CONTRACTION_EXPANSION[c]) return CONTRACTION_EXPANSION[c];
  const m = c.match(/^(.*?)('m|'re|'s|'ve|'ll|'d|n't)$/);
  if (!m) return c;
  let [, base, suf] = m;
  if (suf === "'s" && !/^(?:it|he|she|that|there|what|who|where|how|here|this|everything|nothing|something|everyone|let)$/.test(base)) return `${base} + 's (posesivo / possessive)`;
  if (suf === "n't") return `${base} not`;
  return `${base} ${CONTRACTION_EXPANSION[suf]}`;
}

export const REDUCTIONS = {
  gonna: 'going to', wanna: 'want to', gotta: 'got to / have got to', kinda: 'kind of', sorta: 'sort of', lemme: 'let me', gimme: 'give me',
  dunno: "don't know", ya: 'you', "y'all": 'you all', "'cause": 'because', cuz: 'because', outta: 'out of', lotta: 'lot of', lotsa: 'lots of',
  whatcha: 'what are you / what do you', gotcha: 'got you (entendido)', "ain't": "isn't / am not / haven't", innit: "isn't it", "'em": 'them',
  "c'mon": 'come on', nope: 'no', yep: 'yes', yeah: 'yes', hafta: 'have to', oughta: 'ought to', betcha: 'bet you', tryna: 'trying to',
  shoulda: 'should have', coulda: 'could have', woulda: 'would have', musta: 'must have', alright: 'all right', "'til": 'until',
};

// ---------------------------------------------------------------- connected speech
const SPEECH = [
  { re: /\bgoing to\b(?=\s+[a-z])/g, say: 'gonna' }, { re: /\bwant to\b/g, say: 'wanna' }, { re: /\bwants to\b/g, say: 'wantsta' },
  { re: /\bgot to\b/g, say: 'gotta' }, { re: /\bhave to\b/g, say: 'hafta' }, { re: /\bhas to\b/g, say: 'hasta' },
  { re: /\bkind of\b/g, say: 'kinda' }, { re: /\bsort of\b/g, say: 'sorta' }, { re: /\bout of\b/g, say: 'outta' }, { re: /\ba lot of\b/g, say: 'a lotta' },
  { re: /\b(?:don't|do not) know\b/g, say: 'dunno' }, { re: /\blet me\b/g, say: 'lemme' }, { re: /\bgive me\b/g, say: 'gimme' },
  { re: /\bdid you\b/g, say: 'didja / dija' }, { re: /\bwould you\b/g, say: 'wouldja' }, { re: /\bcould you\b/g, say: 'couldja' },
  { re: /\bdon't you\b/g, say: 'doncha' }, { re: /\bwon't you\b/g, say: 'wonncha' }, { re: /\bgot you\b/g, say: 'gotcha' },
  { re: /\bwhat are you\b/g, say: 'whatcha / whaddaya' }, { re: /\bwhat do you\b/g, say: 'whaddaya' }, { re: /\bhow did you\b/g, say: 'howdja' },
  { re: /\bshould have\b/g, say: 'shoulda' }, { re: /\bcould have\b/g, say: 'coulda' }, { re: /\bwould have\b/g, say: 'woulda' }, { re: /\bmust have\b/g, say: 'musta' },
  { re: /\bbecause\b/g, say: "'cause / cuz" }, { re: /\bthem\b/g, say: "'em" }, { re: /\bmeet you\b/g, say: 'meetcha' }, { re: /\bbet you\b/g, say: 'betcha' },
  { re: /\btrying to\b/g, say: 'tryna' }, { re: /\bought to\b/g, say: 'oughta' }, { re: /\bwhat is\b/g, say: "what's" }, { re: /\bi am\b/g, say: "I'm" },
];
const WEAK = {
  to: '/tə/', for: '/fər/', of: '/əv/ → «a»', and: "/ən/ → «'n'»", can: '/kən/', was: '/wəz/', were: '/wər/', at: '/ət/', from: '/frəm/',
  the: '/ðə/', a: '/ə/', an: '/ən/', you: '/jə/ → «ya»', your: '/jər/', have: '/əv/', has: '/əz/', are: '/ər/', them: '/ðəm/ → «\'em»', him: "/ɪm/ → «'im»", her: "/ər/ → «'er»", some: '/səm/', but: '/bət/', than: '/ðən/', as: '/əz/',
};
const VOWEL_START = /^[aeiou]/; const CONS_END = /[bcdfgklmnprstvxz]$/;
const SPEECH_TXT = {
  reduce: X('Reducción', 'اختزال'), link: X('Enlace consonante + vocal (se pronuncia como una sola palabra)', 'ربط صامت + صائت (يُنطقان ككلمة واحدة)'),
  flap: X('T «suave» americana (suena casi como una d/r rápida)', 'حرف T الأمريكي الليّن (يُنطق كـ d/r سريعة)'), elision: X('Elisión: la t/d final casi desaparece', 'حذف: يكاد يختفي حرف t/d في النهاية'),
  weak: X('Formas débiles (palabras gramaticales átonas)', 'الصيغ الضعيفة (كلمات نحوية غير منبورة)'),
};

export function connectedSpeech(text) {
  const lc = normalize(text).toLowerCase();
  const items = [];
  for (const s of SPEECH) { s.re.lastIndex = 0; let m; while ((m = s.re.exec(lc))) items.push({ kind: 'reduce', label: SPEECH_TXT.reduce, from: m[0], to: s.say }); }
  const ws = lc.match(/[a-z']+/g) || [];
  const links = []; const flaps = []; const elis = [];
  for (let i = 0; i < ws.length - 1; i++) {
    const a = ws[i], b = ws[i + 1];
    if (CONS_END.test(a) && VOWEL_START.test(b) && !/^(?:u|eu|one|once)/.test(b)) links.push(`${a}‿${b}`);
    if (/[aeiou]t$/.test(a) && VOWEL_START.test(b)) flaps.push(`${a} ${b}`);
    if (/(?:st|nd|ct|ft|pt)$/.test(a) && /^[bcdfgjklmnpqrstvwyz]/.test(b) && !/^(?:h)/.test(b)) elis.push(`${a} ${b}`);
  }
  for (const w of ws) if (/^[a-z]*[aeiou]tt?[aeiouy][a-z]*$/.test(w) && w.length > 3 && /tt?(?:er|le|y|ing|ed|en|a|o)\b/.test(w)) flaps.push(w);
  if (links.length) items.push({ kind: 'link', label: SPEECH_TXT.link, list: links.slice(0, 6) });
  if (flaps.length) items.push({ kind: 'flap', label: SPEECH_TXT.flap, list: [...new Set(flaps)].slice(0, 5) });
  if (elis.length) items.push({ kind: 'elision', label: SPEECH_TXT.elision, list: elis.slice(0, 4) });
  const weak = [...new Set(ws.filter(w => WEAK[w]))].slice(0, 6).map(w => `${w} ${WEAK[w]}`);
  if (weak.length) items.push({ kind: 'weak', label: SPEECH_TXT.weak, list: weak });
  return items;
}

export function intonation(text) {
  const q = normalize(text).trim().toLowerCase();
  if (/\?\s*["')]*$/.test(q)) {
    if (/,\s*(?:isn't|aren't|wasn't|weren't|don't|doesn't|didn't|haven't|hasn't|won't|can't|is|are|do|does|did|right)\s*\w*\s*\?/.test(q)) return { arrow: '↘ / ↗', text: X('Question tag: baja si confirmas, sube si preguntas de verdad.', 'سؤال ذيلي: ينخفض إن كنت تؤكد، ويرتفع إن كنت تسأل فعلًا.') };
    if (/^(?:\W*)(?:what|why|where|when|who|which|how)\b/.test(q)) return { arrow: '↘', text: X('Pregunta Wh-: la voz BAJA al final.', 'سؤال Wh-: ينخفض الصوت في النهاية.') };
    return { arrow: '↗', text: X('Pregunta de sí/no: la voz SUBE al final.', 'سؤال نعم/لا: يرتفع الصوت في النهاية.') };
  }
  if (/!\s*["')]*$/.test(q)) return { arrow: '⤵', text: X('Exclamación: mucha energía y caída fuerte al final.', 'تعجّب: طاقة عالية وانخفاض قوي في النهاية.') };
  if (/,/.test(q) && /\b(?:and|or)\b/.test(q)) return { arrow: '↗ ↗ ↘', text: X('Lista: cada elemento sube un poco y el último baja.', 'قائمة: يرتفع كل عنصر قليلًا ويهبط الأخير.') };
  if (/(?:\.\.\.|…|,|—|-)\s*$/.test(q) || !/[.!?]\s*["')]*$/.test(q)) return { arrow: '→', text: X('Frase sin terminar: la voz se mantiene, continúa en la siguiente línea.', 'جملة غير مكتملة: يبقى الصوت مستويًا ويستمر في السطر التالي.') };
  return { arrow: '↘', text: X('Afirmación: la voz baja al final. Acentúa las palabras con contenido (sustantivos, verbos, adjetivos).', 'جملة خبرية: ينخفض الصوت في النهاية. انبر الكلمات ذات المعنى (الأسماء والأفعال والصفات).') };
}

// ---------------------------------------------------------------- public API
/** Analyse one sentence. Returns [{ rule, matches:[{s,e,detail,meaning}] }] in rule order. */
export function analyze(text) {
  const lc = normalize(text).toLowerCase();
  const out = [];
  for (const rule of RULES) {
    let matches = [];
    try { matches = rule.find(lc) || []; } catch (e) { matches = []; }
    if (!matches.length) continue;
    // dedupe overlapping duplicates
    const seen = new Set();
    matches = matches.filter(m => { const k = `${m.s}-${m.e}-${m.detail ?? ''}`; if (seen.has(k)) return false; seen.add(k); return true; }).sort((a, b) => a.s - b.s);
    out.push({ rule, matches });
  }
  return out;
}

/** Which rules appear in which lines (for the "grammar of the whole video" view). */
export function corpus(cues) {
  const map = new Map();
  cues.forEach((c, i) => {
    for (const { rule, matches } of analyze(c.text)) {
      if (!map.has(rule.id)) map.set(rule.id, { rule, lines: [] });
      map.get(rule.id).lines.push(i);
      if (rule.id === 'phrasal') for (const m of matches) {
        const k = 'pv:' + m.detail;
        if (!map.has(k)) map.set(k, { rule, phrasal: m.detail, lines: [] });
        map.get(k).lines.push(i);
      }
    }
  });
  return map;
}

export function isFunctionWord(w) { return FUNCTION_WORDS.has(String(w).toLowerCase().replace(/’/g, "'")); }

/** Phrasal verbs present in a sentence with token spans (for the word popup). */
export function phrasalAt(text) {
  const lc = normalize(text).toLowerCase();
  const out = [];
  for (const p of PHRASAL_RE) for (const r of scan(p.re, lc)) out.push({ s: r.s, e: r.e, name: `${p.v} ${p.p}`, es: p.es, ar: p.ar });
  return out;
}
