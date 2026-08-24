// In-place live reload with no flicker, for local HTML pages (the manifest
// scopes injection to .html/.htm/.xhtml — other types render through
// browser-generated wrapper documents the swap would clobber). file:// reads
// are relayed through the background service worker to an offscreen extension
// page; tailnet HTTP pages can fetch themselves directly. Any changed text is
// swapped into the page in a single paint instead of navigating, so there is
// no white flash and the scroll position is kept — except pages with <script>s,
// which get a normal (flashing) reload, because the swap would not re-run them.
//
// Polls every 1s while the tab is visible and not at all while it is hidden —
// a hidden tab has nothing to keep fresh, and becoming visible triggers an
// immediate poll. A seed read at injection records the file as rendered, so
// an edit made while the tab is hidden is detected on focus.
(() => {
  const url = location.href.split('#')[0];
  let timer = null;
  let lastText;

  // Reloading the extension orphans a file:// content script for good:
  // sendMessage then throws "Extension context invalidated" synchronously.
  // Stop polling; reloading the tab injects a fresh copy.
  function readFile(seed = false) {
    try {
      return chrome.runtime.sendMessage({ action: 'read', url, seed }).catch(() => null);
    } catch {
      clearInterval(timer);
      return null;
    }
  }

  async function readHttp(seed = false) {
    try {
      // no-store: the server sends Last-Modified but no Cache-Control, so
      // Chromium's heuristic freshness (10% of file age) would otherwise
      // serve stale content for old files and change detection would miss edits
      const response = await fetch(url, { cache: 'no-store' });
      if (!response.ok) return null;
      const text = await response.text();
      const changed = !seed && text !== lastText;
      lastText = text;
      return changed ? text : null;
    } catch {
      return null;
    }
  }

  const read = location.protocol === 'file:' ? readFile : readHttp;

  async function poll() {
    const text = await read();
    if (text == null) return; // unchanged, or the read failed

    const next = new DOMParser().parseFromString(text, 'text/html');
    if (next.querySelector('script')) {
      location.reload();
      return;
    }
    const x = scrollX;
    const y = scrollY;
    document.head.innerHTML = next.head.innerHTML;
    document.body.innerHTML = next.body.innerHTML;
    scrollTo(x, y);
  }

  function reschedule() {
    clearInterval(timer);
    if (!document.hidden) timer = setInterval(poll, 1000);
  }

  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) poll(); // immediate refresh when brought to foreground
    reschedule();
  });

  read(true); // record the file as rendered
  reschedule();
})();
