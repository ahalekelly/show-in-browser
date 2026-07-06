// In-place live reload with no flicker, for local HTML pages (the manifest
// scopes injection to .html/.htm/.xhtml — other types render through
// browser-generated wrapper documents the swap would clobber). Asks the
// background service worker to relay reads to an offscreen extension page,
// the only context that can read file://: content scripts and pages cannot,
// and the service worker has no XHR and its fetch is unreliable. When the
// file changes, it swaps the page content in a single paint instead of
// navigating, so there is no white flash and the scroll position is kept —
// except pages with <script>s, which get a normal (flashing) reload, because
// the swap would not re-run them.
//
// Polls every 1s while the tab is visible and every 60s while it is in the
// background, to save CPU. On becoming visible it polls immediately, so a change
// made while the tab was backgrounded shows up at once. A seed read at load
// captures the file as rendered, so that background change is detected.
(() => {
  const url = location.href.split('#')[0];
  let last = null;
  let timer = null;

  // Reloading the extension orphans this script for good: sendMessage then
  // throws "Extension context invalidated" synchronously. Stop polling —
  // reloading the tab injects a fresh copy.
  function read() {
    try {
      return chrome.runtime.sendMessage({ action: 'read', url }).catch(() => null);
    } catch {
      clearInterval(timer);
      return null;
    }
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
    const ms = document.hidden ? 60000 : 1000;
    timer = setInterval(poll, ms);
  }

  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) poll(); // immediate refresh when brought to foreground
    reschedule();
  });

  poll(); // seed at load
  reschedule(); // start at the right cadence
})();
