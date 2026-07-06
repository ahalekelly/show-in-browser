# show-in-vivaldi

Show local HTML files in Vivaldi from the command line, with **flicker-free live reload**. Two parts: a CLI script (`show-in-vivaldi.sh`) that opens/focuses/moves tabs over AppleScript, and a Chromium extension that updates page content in place and moves tabs — the two things AppleScript can't do without a visible flash.

## show-in-vivaldi.sh

`show-in-vivaldi.sh <absolute-path> [focus] [last]` opens a local HTML file in Vivaldi without duplicate tabs. If the tab is already open it leaves it alone — the extension keeps the content current on its own. `focus` brings the tab to the foreground; `last` moves it to the end of the tab strip.

## The extension

**Live reload (no flicker).** A content script runs on every local page. It polls the file and, when it changes, swaps the page content in a single paint instead of navigating — so there is no white flash and the scroll position is kept. Edit the file and the open page updates itself; you don't re-run the script to refresh. Pages with `<script>`s get a normal (flashing) reload instead, because the swap would not re-run them.

The file is read by an offscreen extension document: content scripts and pages cannot read `file://` because their requests use the page's `file://` origin, and the service worker has no XHR and its `fetch(file://)` is unreliable. The content script messages the service worker, which relays to an offscreen document whose `chrome-extension://` origin can XHR `file://` when the extension has file access.

Why not AppleScript: its `reload` does a full document reload (blank → refetch → repaint), which always flashes.

**Move to end (no reload, no flash).** Moving a tab's position doesn't reload its page, but AppleScript's `move` destroys the tab and inserts a blank one, and creating a trigger tab flashes the foreground because Vivaldi activates new tabs. So `last` instead appends `#claude-move-to-end` to the report tab's own URL — a same-document change that neither reloads the page nor changes the active tab — and the extension (`chrome.tabs.move`, the only real relocation API) moves that tab to the end and strips the fragment. This stays flicker-free even when the moved tab is in the background and you're viewing another tab.

## Setup

1. Open `vivaldi://extensions` (or `chrome://extensions`)
2. Enable **Developer mode**
3. **Load unpacked** → select this directory
4. Open the extension's details and enable **Allow access to file URLs** (required for live reload of `file://` pages)

All local `.html`/`.htm`/`.xhtml` pages are live-reloaded. Other file types are left alone: non-HTML files render through browser-generated wrapper documents the swap would clobber, and `.md` has a dedicated markdown extension.
