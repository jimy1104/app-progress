// Optional AI tutor using the Claude Messages API directly from the browser.
// The page is a static site with no build step, so it calls the REST endpoint with fetch.
// The key is stored only in this browser (localStorage) and sent only to api.anthropic.com.
import { LANGS } from './i18n.js';

const ENDPOINT = 'https://api.anthropic.com/v1/messages';

const LINE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['natural_translation', 'literal_translation', 'grammar', 'vocabulary', 'pronunciation', 'usage_note'],
  properties: {
    natural_translation: { type: 'string' },
    literal_translation: { type: 'string' },
    grammar: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false, required: ['structure', 'fragment', 'explanation', 'how_to_use', 'examples'],
        properties: {
          structure: { type: 'string' }, fragment: { type: 'string' }, explanation: { type: 'string' }, how_to_use: { type: 'string' },
          examples: { type: 'array', items: { type: 'object', additionalProperties: false, required: ['en', 'translation'], properties: { en: { type: 'string' }, translation: { type: 'string' } } } },
        },
      },
    },
    vocabulary: {
      type: 'array',
      items: { type: 'object', additionalProperties: false, required: ['term', 'meaning', 'example'], properties: { term: { type: 'string' }, meaning: { type: 'string' }, example: { type: 'string' } } },
    },
    pronunciation: { type: 'array', items: { type: 'string' } },
    usage_note: { type: 'string' },
  },
};

async function callClaude({ key, model, system, content, schema, maxTokens = 6000 }) {
  const body = {
    model: model || 'claude-opus-5-5',
    max_tokens: maxTokens,
    system,
    messages: [{ role: 'user', content }],
    output_config: { effort: 'low', ...(schema ? { format: { type: 'json_schema', schema } } : {}) },
  };
  const headers = {
    'content-type': 'application/json',
    'x-api-key': key,
    'anthropic-version': '2023-06-01',
    'anthropic-dangerous-direct-browser-access': 'true',
  };
  // Server-side fallback if the model declines a request (supported on Opus 5.5 / Sonnet 5.5).
  const withFallback = /opus-5-5|sonnet-5-5/.test(body.model);
  const send = (fb) => fetch(ENDPOINT, {
    method: 'POST',
    headers: fb ? { ...headers, 'anthropic-beta': 'server-side-fallback-2026-07-01' } : headers,
    body: JSON.stringify(fb ? { ...body, fallbacks: 'default' } : body),
  });
  let res = await send(withFallback);
  if (!res.ok && res.status === 400 && withFallback) res = await send(false); // retry plainly if the beta is unavailable
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg = (data && data.error && data.error.message) || `HTTP ${res.status}`;
    const err = new Error(res.status === 401 ? 'Clave API no válida / مفتاح غير صالح' : msg);
    err.status = res.status; throw err;
  }
  if (data.stop_reason === 'refusal') throw new Error('La IA no pudo responder a esta petición.');
  const text = (data.content || []).filter(b => b.type === 'text').map(b => b.text).join('');
  if (schema) {
    try { return JSON.parse(text); } catch { throw new Error('Respuesta incompleta de la IA (inténtalo de nuevo).'); }
  }
  return text;
}

function sys(native, target) {
  const n = LANGS[native] || native, t = LANGS[target] || target;
  return `You are a warm, precise language tutor for a learner whose native language is ${n} and who is learning ${t} by shadowing movie and video subtitles.
Write every explanation, meaning and translation in ${n}. Keep example sentences in ${t}, short and simple (A2–B1 level), each with a ${n} translation.
Explain grammar the way a great teacher would: name the structure, why it is used in THIS sentence, and how the learner can reuse it.
Subtitle lines can be fragments of a longer sentence; use the surrounding lines for context.`;
}

export async function explainLine({ key, model, line, prev, next, native, target }) {
  const content = `Subtitle line to explain:\n"${line}"\n\nPrevious line: "${prev || ''}"\nNext line: "${next || ''}"\n\nReturn: a natural translation, a literal word-by-word translation, every important grammar structure (with the exact fragment from the line, explanation, how to use it, and 2 simple examples), useful vocabulary/idioms/phrasal verbs (meaning + simple example), pronunciation tips for shadowing (connected speech, reductions, stress, intonation), and a short usage/cultural note.`;
  return callClaude({ key, model, system: sys(native, target), content, schema: LINE_SCHEMA });
}

export async function askAbout({ key, model, line, question, native, target }) {
  const content = `Subtitle line: "${line}"\n\nLearner's question: ${question}\n\nAnswer concisely and clearly, with 1–3 short examples in ${LANGS[target] || target} when useful.`;
  return callClaude({ key, model, system: sys(native, target), content, maxTokens: 3000 });
}
