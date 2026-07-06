// Reads file:// URLs for the service worker. This runs in an extension-origin
// page, the only context that can both use XMLHttpRequest and read file://
// URLs (with "Allow access to file URLs" enabled): a service worker has no
// XHR and its fetch() of file:// is unreliable, and a content script's
// requests use the page's file:// origin, which cannot read file:// at all.
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.target !== 'offscreen') return;
  const xhr = new XMLHttpRequest();
  xhr.open('GET', msg.url);
  xhr.onload = () => sendResponse(xhr.responseText);
  xhr.onerror = () => sendResponse(null);
  xhr.send();
  return true; // keep the message channel open for the async response
});
