// Reads local files on behalf of the live-reload content script: a service
// worker can fetch() a file:// URL when the extension has "Allow access to file
// URLs" enabled, but a content script / page context cannot.
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.action !== 'read') return;
  fetch(msg.url, { cache: 'no-store' })
    .then((r) => r.text())
    .then(sendResponse)
    .catch(() => sendResponse(null));
  return true; // keep the message channel open for the async response
});

// Move-to-end is signalled by the CLI appending this fragment to the report
// tab's own URL. That is a same-document change, so it does not reload the page
// or change the active tab (no flash). We move that tab to the end of its window
// and strip the fragment back off.
const MARKER = '#claude-move-to-end';
chrome.tabs.onUpdated.addListener((tabId, changeInfo) => {
  const url = changeInfo.url;
  if (!url || !url.endsWith(MARKER)) return;
  chrome.tabs.move(tabId, { index: -1 });
  chrome.tabs.update(tabId, { url: url.slice(0, -MARKER.length) });
});
