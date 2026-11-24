// Runs in every frame. Stays tiny until the user opens EnglishPro: then it loads the UI module
// in the frame that holds the biggest visible <video> (players are often inside iframes).
(() => {
  if (window.__englishProLoaded) return;
  window.__englishProLoaded = true;
  let ctrl = null;
  let loading = null;

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
    loading = loading || import(chrome.runtime.getURL('lib/ui.js')).then(m => m.mount(v, bestVideo));
    ctrl = await loading;
    return true;
  }

  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (!msg || msg.type !== 'ep-toggle') return false;
    if (!ctrl && !bestVideo()) return false; // let a frame that has a video answer
    toggle().then(ok => sendResponse({ ok })).catch(err => { console.error('[EnglishPro]', err); sendResponse({ ok: false }); });
    return true;
  });
})();
