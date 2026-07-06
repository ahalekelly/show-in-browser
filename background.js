// Reads local files on behalf of the live-reload content script: a service
// worker can fetch() a file:// URL when the extension has "Allow access to file
// URLs" enabled, but a content script / page context cannot. Also moves a tab
// to the end of its window without reloading it.

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.action !== 'read') return;
  fetch(msg.url, { cache: 'no-store' })
    .then((r) => r.text())
    .then(sendResponse)
    .catch(() => sendResponse(null));
  return true; // keep the message channel open for the async response
});

// The CLI opens a lightweight data-URL trigger tab whose fragment carries the
// encoded target URL; we read it, close the trigger, and move the real tab.
const MARKER = '#claude-move-to-end:';

chrome.tabs.onUpdated.addListener((tabId, changeInfo) => {
  const url = changeInfo.url;
  if (!url || !url.includes(MARKER)) return;
  const targetUrl = decodeURIComponent(url.slice(url.indexOf(MARKER) + MARKER.length));
  chrome.tabs.remove(tabId);
  chrome.tabs.query({}).then((tabs) => {
    const target = tabs.find((t) => t.id !== tabId && t.url === targetUrl);
    if (target) chrome.tabs.move(target.id, { index: -1 });
  });
});
