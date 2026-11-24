// Toolbar button / Alt+E: ask every frame of the tab to open EnglishPro on its video.
chrome.action.onClicked.addListener(async tab => {
  if (!tab || tab.id == null) return;
  try {
    const res = await chrome.tabs.sendMessage(tab.id, { type: 'ep-toggle' });
    if (!res || !res.ok) flag(tab.id);
  } catch { flag(tab.id); }
});

// Subtitles captured in one frame (e.g. the page) are shared with every frame of the tab,
// because the video often lives in a different frame (an embedded player).
chrome.runtime.onMessage.addListener((msg, sender) => {
  if (msg && msg.type === 'ep-subs' && sender.tab && sender.tab.id != null) {
    chrome.tabs.sendMessage(sender.tab.id, { type: 'ep-subs-all', cand: msg.cand }).catch(() => {});
  }
});

function flag(tabId) {
  chrome.action.setBadgeBackgroundColor({ tabId, color: '#ff5fa2' });
  chrome.action.setBadgeText({ tabId, text: '?' });
  chrome.action.setTitle({ tabId, title: 'EnglishPro: no video found yet. Start the video, then click again.' });
  setTimeout(() => { chrome.action.setBadgeText({ tabId, text: '' }); chrome.action.setTitle({ tabId, title: 'EnglishPro (Alt+E)' }); }, 4000);
}
