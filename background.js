// Relays file reads from the live-reload content script to the offscreen
// document (see offscreen.js for why that is the only context that can read
// file:// URLs). Created lazily; `creating` guards against the "only a single
// offscreen document" error when polls from several tabs race.
let creating;
async function ensureOffscreen() {
  if (await chrome.offscreen.hasDocument()) return;
  creating ??= chrome.offscreen
    .createDocument({
      url: 'offscreen.html',
      reasons: ['DOM_PARSER'],
      justification: 'XMLHttpRequest is the only way to read file:// URLs',
    })
    .finally(() => (creating = undefined));
  await creating;
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.action !== 'read') return;
  ensureOffscreen()
    .then(() =>
      chrome.runtime.sendMessage({
        target: 'offscreen',
        url: msg.url,
        seed: msg.seed,
        tabId: sender.tab.id, // the offscreen page tracks last-served text per tab
      })
    )
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
