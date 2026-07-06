// In-place live reload with no flicker, for local HTML pages (the manifest
// scopes injection to .html/.htm/.xhtml — other types render through
// browser-generated wrapper documents the swap would clobber). Asks the
// background service worker to relay reads to an offscreen extension page,
// the only context that can read file://: content scripts and pages cannot,
// and the service worker has no XHR and its fetch is unreliable. The offscreen
// page answers null until the file changes (see offscreen.js), so the full
// text only crosses process boundaries on a real change. Any text received is
// a change and gets swapped into the page in a single paint instead of
// navigating, so there is no white flash and the scroll position is kept —
// except pages with <script>s, which get a normal (flashing) reload, because
// the swap would not re-run them.
//
// Polls every 1s while the tab is visible and not at all while it is hidden —
// a hidden tab has nothing to keep fresh, and becoming visible triggers an
// immediate poll. A seed read at injection records the file as rendered, so
// an edit made while the tab is hidden is detected on focus.
(() => {
  const url = location.href.split('#')[0];
  let timer = null;

  // Reloading the extension orphans this script for good: sendMessage then
  // throws "Extension context invalidated" synchronously. Stop polling —
  // reloading the tab injects a fresh copy.
  function read(msg) {
    try {
      return chrome.runtime.sendMessage(msg).catch(() => null);
    } catch {
      clearInterval(timer);
      return null;
    }
  }

  async function poll() {
    const text = await read({ action: 'read', url });
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

  read({ action: 'read', url, seed: true }); // record the file as rendered
  reschedule();
})();
