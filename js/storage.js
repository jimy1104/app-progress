// Persistent state in localStorage (per browser). Two profiles, each with its own
// settings, saved items, routine progress and statistics.
const KEY = 'shadowlab.v1';

export const DEFAULT_SETTINGS = {
  mode: 'watch',
  autoPause: false, loopLine: false, repeatCount: 3, autoResume: false, gapFactor: 1.3,
  showPrevBtn: true, hideText: false, showTranslation: true, blurTranslation: false,
  karaoke: true, stressMap: false, autoRecord: false, overlayRecord: false,
  rate: 1, offset: 0, gameShowTrans: false,
};

function newProfile(id, name, native) {
  return {
    id, name, native, target: 'en',
    settings: { ...DEFAULT_SETTINGS },
    saved: { words: {}, sentences: [] },
    stats: { days: {}, lines: 0, recordings: 0, translations: 0, transScoreSum: 0 },
    routine: {},
    game: { best: {}, played: 0 },
  };
}

function defaults() {
  return {
    activeProfile: 'p1',
    profiles: { p1: newProfile('p1', 'Person 1', 'es'), p2: newProfile('p2', 'Person 2', 'ar') },
    ai: { key: '', model: 'claude-opus-5-5' },
    library: {},
  };
}

function merge(base, over) {
  if (Array.isArray(base) || typeof base !== 'object' || base === null) return over === undefined ? base : over;
  const out = { ...base };
  if (over && typeof over === 'object') {
    for (const k of Object.keys(over)) out[k] = (k in base) ? merge(base[k], over[k]) : over[k];
  }
  return out;
}

let state = load();

function load() {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return defaults();
    const parsed = JSON.parse(raw);
    const d = defaults();
    const s = merge(d, parsed);
    for (const id of Object.keys(s.profiles)) {
      s.profiles[id] = merge(newProfile(id, s.profiles[id].name || id, s.profiles[id].native || 'es'), s.profiles[id]);
    }
    // Old default names → English defaults (custom names are kept).
    const rename = { 'Persona 1': 'Person 1', 'Persona 2': 'Person 2', 'شخص 2': 'Person 2' };
    for (const p of Object.values(s.profiles)) if (rename[p.name]) p.name = rename[p.name];
    return s;
  } catch { return defaults(); }
}

let saveTimer = null;
export function persist(now = false) {
  const write = () => {
    try { localStorage.setItem(KEY, JSON.stringify(state)); }
    catch (e) {
      // Quota: drop the oldest library entries and retry once.
      try {
        const entries = Object.entries(state.library).sort((a, b) => (a[1].updated || 0) - (b[1].updated || 0));
        for (let i = 0; i < Math.ceil(entries.length / 2); i++) delete state.library[entries[i][0]];
        localStorage.setItem(KEY, JSON.stringify(state));
      } catch { /* give up silently */ }
    }
  };
  clearTimeout(saveTimer);
  if (now) write(); else saveTimer = setTimeout(write, 300);
}

export function getState() { return state; }
export function profile() { return state.profiles[state.activeProfile] || state.profiles.p1; }
export function settings() { return profile().settings; }
export function setActiveProfile(id) { if (state.profiles[id]) { state.activeProfile = id; persist(); } }

export function exportJSON() { return JSON.stringify(state, null, 2); }
export function importJSON(text) {
  const parsed = JSON.parse(text);
  if (!parsed || !parsed.profiles) throw new Error('invalid');
  state = merge(defaults(), parsed);
  persist(true);
}
export function resetAll() { state = defaults(); persist(true); }

// ---------- Saved items ----------
export function wordKey(w) { return String(w || '').toLowerCase().replace(/[’]/g, "'").trim(); }
export function isWordSaved(w) { return !!profile().saved.words[wordKey(w)]; }
export function saveWord(entry) {
  const k = wordKey(entry.word);
  profile().saved.words[k] = { ...entry, word: entry.word, added: Date.now(), box: 0 };
  persist();
}
export function removeWord(w) { delete profile().saved.words[wordKey(w)]; persist(); }
export function savedWordSet() { return new Set(Object.keys(profile().saved.words)); }

export function isSentenceSaved(text) { return profile().saved.sentences.some(s => s.text === text); }
export function toggleSentence(entry) {
  const list = profile().saved.sentences;
  const i = list.findIndex(s => s.text === entry.text);
  if (i >= 0) { list.splice(i, 1); persist(); return false; }
  list.unshift({ ...entry, added: Date.now() }); persist(); return true;
}

// ---------- Stats ----------
export function today() { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; }
export function addPracticeSeconds(sec) {
  const st = profile().stats; const k = today();
  st.days[k] = (st.days[k] || 0) + sec; persist();
}
export function bump(field, by = 1) { profile().stats[field] = (profile().stats[field] || 0) + by; persist(); }
export function streak() {
  const days = profile().stats.days; let n = 0; const d = new Date();
  if (!(days[fmt(d)] > 30)) d.setDate(d.getDate() - 1); // today not done yet: count from yesterday
  while (days[fmt(d)] > 30) { n++; d.setDate(d.getDate() - 1); }
  return n;
  function fmt(x) { return `${x.getFullYear()}-${String(x.getMonth() + 1).padStart(2, '0')}-${String(x.getDate()).padStart(2, '0')}`; }
}

// ---------- Library (subtitles of past sessions; videos stay on your device) ----------
export function libraryKey(title) { return String(title || 'sin título').slice(0, 120); }
export function saveSession(sess) {
  const k = libraryKey(sess.title);
  const prev = state.library[k] || {};
  state.library[k] = { ...prev, ...sess, updated: Date.now() };
  persist();
}
export function updateSession(title, patch) {
  const k = libraryKey(title);
  if (state.library[k]) { Object.assign(state.library[k], patch); persist(); }
}
export function deleteSession(title) { delete state.library[libraryKey(title)]; persist(); }
