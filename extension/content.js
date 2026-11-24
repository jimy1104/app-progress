// Runs in every frame. Collects subtitles captured by inject.js (here or in other frames of the tab)
// and, when the user opens EnglishPro, loads the UI in the frame that holds the biggest video.
(() => {
  if (window.__englishProLoaded) return;
  window.__englishProLoaded = true;
  let ctrl = null;
  let loading = null;
  const cands = new Map();

  function addCand(c) {
    if (!c || !c.id || !c.text) return;
    cands.set(c.id, c);
    if (ctrl) ctrl.addCandidate(c);
  }

  // From inject.js in this frame → share with the whole tab.
  window.addEventListener('message', e => {
    if (e.source !== window || !e.data) return;
    const d = e.data;
    if (d.__ep === 'subs') {
      const cand = { id: d.id, url: d.url, text: d.text, lang: d.lang, label: d.label, source: d.source, format: d.format };
      try { chrome.runtime.sendMessage({ type: 'ep-subs', cand }); } catch { addCand(cand); }
    } else if ((d.__ep === 'yt-none' || d.__ep === 'nav') && ctrl) ctrl.onPageEvent(d.__ep);
  });
  window.postMessage({ __ep: 'replay' }, '*'); // anything captured before this script started

  function bestVideo() {
    let best = null, area = 0;
    for (const v of document.querySelectorAll('video')) {
      const r = v.getBoundingClientRect();
      const a = r.width * r.height;
      if (r.width >= 200 && r.height >= 110 && a > area) { best = v; area = a; }
    }
    return best;
  }

  async function toggle() {
    if (ctrl) { ctrl.toggle(); return true; }
    const v = bestVideo();
    if (!v) return false;
    loading = loading || import(chrome.runtime.getURL('lib/ui.js')).then(m => m.mount(v, bestVideo, [...cands.values()]));
    ctrl = await loading;
    return true;
  }

  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (!msg) return false;
    if (msg.type === 'ep-subs-all') { addCand(msg.cand); return false; }
    if (msg.type !== 'ep-toggle') return false;
    if (!ctrl && !bestVideo()) return false; // let a frame that has a video answer
    toggle().then(ok => sendResponse({ ok })).catch(err => { console.error('[EnglishPro]', err); sendResponse({ ok: false }); });
    return true;
  });
})();
