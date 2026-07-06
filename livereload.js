// In-place live reload with no flicker. Runs only on pages that opt in with
// <meta name="show-in-vivaldi">. Asks the background service worker to read the
// file (a content script can't fetch file:// itself), and when it changes swaps
// the page content in a single paint instead of navigating, so there is no
// white flash and the scroll position is kept.
(() => {
  if (!document.querySelector('meta[name="show-in-vivaldi"]')) return;

  const url = location.href.split('#')[0];
  let last = null;

  function read() {
    return new Promise((resolve) => {
      chrome.runtime.sendMessage({ action: 'read', url }, (text) => resolve(text ?? null));
    });
  }

  async function poll() {
    const text = await read();
    if (text == null) return;
    if (last === null) {
      last = text;
      return;
    }
    if (text === last) return;
    last = text;

    const next = new DOMParser().parseFromString(text, 'text/html');
    const x = scrollX;
    const y = scrollY;
    document.head.innerHTML = next.head.innerHTML;
    document.body.innerHTML = next.body.innerHTML;
    scrollTo(x, y);
  }

  setInterval(poll, 500);
})();
