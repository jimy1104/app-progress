// Word lookup: English definitions, phonetics, audio and simple example sentences
// (Free Dictionary API), plus translation into the learner's native language.
import { translateWord, translateLines } from './translate.js';

const mem = new Map();

const IRREGULAR_LEMMA = {
  was: 'be', were: 'be', is: 'be', are: 'be', am: 'be', been: 'be', being: 'be', "'s": 'be', "'re": 'be', "'m": 'be',
  went: 'go', gone: 'go', goes: 'go', did: 'do', done: 'do', does: 'do', had: 'have', has: 'have',
  said: 'say', made: 'make', took: 'take', taken: 'take', came: 'come', saw: 'see', seen: 'see', knew: 'know', known: 'know',
  got: 'get', gotten: 'get', gave: 'give', given: 'give', found: 'find', thought: 'think', told: 'tell', became: 'become',
  left: 'leave', felt: 'feel', brought: 'bring', began: 'begin', begun: 'begin', kept: 'keep', held: 'hold', wrote: 'write',
  written: 'write', stood: 'stand', heard: 'hear', meant: 'mean', met: 'meet', ran: 'run', paid: 'pay', sat: 'sit', spoke: 'speak',
  spoken: 'speak', lay: 'lie', led: 'lead', grew: 'grow', grown: 'grow', lost: 'lose', fell: 'fall', fallen: 'fall', sent: 'send',
  built: 'build', understood: 'understand', drew: 'draw', drawn: 'draw', broke: 'break', broken: 'break', spent: 'spend', cut: 'cut',
  rose: 'rise', risen: 'rise', drove: 'drive', driven: 'drive', bought: 'buy', wore: 'wear', worn: 'wear', chose: 'choose', chosen: 'choose',
  sought: 'seek', threw: 'throw', thrown: 'throw', caught: 'catch', dealt: 'deal', won: 'win', forgot: 'forget', forgotten: 'forget',
  ate: 'eat', eaten: 'eat', fought: 'fight', taught: 'teach', sold: 'sell', slept: 'sleep', flew: 'fly', flown: 'fly', hid: 'hide',
  hidden: 'hide', stole: 'steal', stolen: 'steal', woke: 'wake', woken: 'wake', shook: 'shake', drank: 'drink', drunk: 'drink',
  sang: 'sing', sung: 'sing', swam: 'swim', rang: 'ring', bit: 'bite', bitten: 'bite', beat: 'beat', froze: 'freeze', frozen: 'freeze',
  children: 'child', men: 'man', women: 'woman', people: 'person', feet: 'foot', teeth: 'tooth', mice: 'mouse', better: 'good', best: 'good',
  worse: 'bad', worst: 'bad', "won't": 'will', "can't": 'can', "don't": 'do', "doesn't": 'do', "didn't": 'do',
};

export function lemmaCandidates(word) {
  const w = word.toLowerCase().replace(/’/g, "'").replace(/'s$/, '');
  const c = [w];
  if (IRREGULAR_LEMMA[w]) c.push(IRREGULAR_LEMMA[w]);
  const add = x => { if (x && x.length > 1 && !c.includes(x)) c.push(x); };
  if (w.endsWith('ies')) add(w.slice(0, -3) + 'y');
  if (w.endsWith('es')) add(w.slice(0, -2));
  if (w.endsWith('s') && !w.endsWith('ss')) add(w.slice(0, -1));
  if (w.endsWith('ied')) add(w.slice(0, -3) + 'y');
  if (w.endsWith('ed')) { add(w.slice(0, -2)); add(w.slice(0, -1)); if (/(.)\1ed$/.test(w)) add(w.slice(0, -3)); }
  if (w.endsWith('ing')) { add(w.slice(0, -3)); add(w.slice(0, -3) + 'e'); if (/(.)\1ing$/.test(w)) add(w.slice(0, -4)); }
  if (w.endsWith('er')) { add(w.slice(0, -2)); add(w.slice(0, -1)); }
  if (w.endsWith('est')) { add(w.slice(0, -3)); add(w.slice(0, -2)); }
  if (w.endsWith('ly')) add(w.slice(0, -2));
  if (w.endsWith("n't")) add(w.slice(0, -3));
  return c;
}

async function freeDictionary(word) {
  const r = await fetch(`https://api.dictionaryapi.dev/api/v2/entries/en/${encodeURIComponent(word)}`);
  if (!r.ok) return null;
  const data = await r.json();
  if (!Array.isArray(data) || !data.length) return null;
  const entry = { word: data[0].word, phonetic: '', audio: '', meanings: [] };
  for (const e of data) {
    if (!entry.phonetic) entry.phonetic = e.phonetic || (e.phonetics || []).map(p => p.text).find(Boolean) || '';
    if (!entry.audio) {
      const a = (e.phonetics || []).map(p => p.audio).filter(Boolean);
      entry.audio = a.find(x => /-us\.mp3/.test(x)) || a[0] || '';
    }
    for (const m of e.meanings || []) {
      let g = entry.meanings.find(x => x.pos === m.partOfSpeech);
      if (!g) { g = { pos: m.partOfSpeech, defs: [] }; entry.meanings.push(g); }
      for (const d of m.definitions || []) g.defs.push({ def: d.definition, example: d.example || '' });
    }
  }
  return entry;
}

/**
 * Full lookup. Returns { word, lemma, phonetic, audio, meanings[], translation:{main,alts}, examples:[{en, tr}] }
 */
export async function lookup(word, { target = 'en', native = 'es' } = {}) {
  const key = `${target}|${native}|${word.toLowerCase()}`;
  if (mem.has(key)) return mem.get(key);
  const p = (async () => {
    const res = { word, lemma: word, phonetic: '', audio: '', meanings: [], translation: { main: '', alts: [] }, examples: [] };
    const tasks = [];
    tasks.push(translateWord(word, target, native).then(t => { res.translation = t; }).catch(() => {}));
    if (target === 'en') {
      tasks.push((async () => {
        for (const cand of lemmaCandidates(word).slice(0, 5)) {
          try {
            const e = await freeDictionary(cand);
            if (e) { Object.assign(res, { lemma: e.word, phonetic: e.phonetic, audio: e.audio, meanings: e.meanings }); break; }
          } catch { break; }
        }
      })());
    }
    await Promise.all(tasks);
    // If the inflected form translated poorly, also translate the lemma.
    if (res.lemma && res.lemma.toLowerCase() !== word.toLowerCase()) {
      try { res.lemmaTranslation = await translateWord(res.lemma, target, native); } catch {}
    }
    // Simple examples: prefer short ones.
    const ex = [];
    for (const m of res.meanings) for (const d of m.defs) if (d.example) ex.push(d.example);
    ex.sort((a, b) => a.length - b.length);
    const chosen = [...new Set(ex)].filter(e => e.length <= 110).slice(0, 3);
    if (chosen.length) {
      try {
        const trs = await translateLines(chosen, target, native);
        res.examples = chosen.map((en, i) => ({ en, tr: trs[i] || '' }));
      } catch { res.examples = chosen.map(en => ({ en, tr: '' })); }
    }
    // Translate the first definition so beginners understand it.
    const firstDef = res.meanings[0] && res.meanings[0].defs[0] && res.meanings[0].defs[0].def;
    if (firstDef) { try { res.defTr = (await translateLines([firstDef], 'en', native))[0]; } catch {} }
    return res;
  })();
  mem.set(key, p);
  try { return await p; } catch (e) { mem.delete(key); throw e; }
}
