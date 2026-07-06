const MARKER = '#claude-move-to-end';

chrome.tabs.onUpdated.addListener((tabId, changeInfo) => {
  if (!changeInfo.url || !changeInfo.url.endsWith(MARKER)) return;
  const targetUrl = changeInfo.url.slice(0, -MARKER.length);
  chrome.tabs.remove(tabId);
  chrome.tabs.query({}).then((tabs) => {
    const target = tabs.find((t) => t.id !== tabId && t.url === targetUrl);
    if (target) chrome.tabs.move(target.id, { index: -1 });
  });
});
