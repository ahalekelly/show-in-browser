// Reads file:// URLs for the service worker. This runs in an extension-origin
// page, the only context that can both use XMLHttpRequest and read file://
// URLs (with "Allow access to file URLs" enabled): a service worker has no
// XHR and its fetch is unreliable, and a content script's requests use the
// page's file:// origin, which cannot read file:// at all.
//
// Keeps the last text served per tab and answers null when the file has not
// changed, so the full text only crosses process boundaries on a real change.
// A read with seed:true records the text without reporting a change — the
// content script sends it at injection, when the page already shows the file.
const last = new Map(); // "tabId url" → text

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.target !== 'offscreen') return;
  const key = msg.tabId + ' ' + msg.url;
  const xhr = new XMLHttpRequest();
  xhr.open('GET', msg.url);
  xhr.onload = () => {
    const changed = !msg.seed && xhr.responseText !== last.get(key);
    last.set(key, xhr.responseText);
    sendResponse(changed ? xhr.responseText : null);
  };
  xhr.onerror = () => sendResponse(null);
  xhr.send();
  return true; // keep the message channel open for the async response
});
