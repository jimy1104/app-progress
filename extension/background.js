// Toolbar button / Alt+E: ask every frame of the tab to open EnglishPro on its video.
chrome.action.onClicked.addListener(async tab => {
  if (!tab || tab.id == null) return;
  try {
    const res = await chrome.tabs.sendMessage(tab.id, { type: 'ep-toggle' });
    if (!res || !res.ok) flag(tab.id);
  } catch { flag(tab.id); }
});

function flag(tabId) {
  // No frame answered with a video (page still loading, or no <video> on it).
  chrome.action.setBadgeBackgroundColor({ tabId, color: '#ff5fa2' });
  chrome.action.setBadgeText({ tabId, text: '?' });
  chrome.action.setTitle({ tabId, title: 'EnglishPro: no video found yet. Start the video, then click again.' });
  setTimeout(() => { chrome.action.setBadgeText({ tabId, text: '' }); chrome.action.setTitle({ tabId, title: 'EnglishPro (Alt+E)' }); }, 4000);
}
