# show-in-vivaldi

Show local HTML files in Vivaldi from the command line, with **flicker-free live reload**. Two parts: a CLI script (`show-in-vivaldi.sh`) that opens/focuses/moves tabs over AppleScript, and a Chromium extension that updates page content in place and moves tabs — the two things AppleScript can't do without a visible flash.

## show-in-vivaldi.sh

`show-in-vivaldi.sh <absolute-path> [focus] [last]` opens a local HTML file in Vivaldi without duplicate tabs. If the tab is already open it leaves it alone — the extension keeps the content current on its own. `focus` brings the tab to the foreground; `last` moves it to the end of the tab strip.

## The extension

**Live reload (no flicker).** A content script runs on pages that opt in with `<meta name="show-in-vivaldi">`. It polls the file and, when it changes, swaps the page content in a single paint instead of navigating — so there is no white flash and the scroll position is kept. Edit the file and the open page updates itself; you don't re-run the script to refresh.

The file is read by the background service worker: in Manifest V3 a content script / page context cannot `fetch()` a `file://` URL, but the service worker can when the extension has file access, so the content script messages it (`{ action: 'read' }`) and gets the text back.

Why not AppleScript: its `reload` does a full document reload (blank → refetch → repaint), which always flashes.

**Move to end (no reload).** Moving a tab's position doesn't reload its page, but AppleScript's `move` destroys the tab and inserts a blank one. `chrome.tabs.move` is the only real tab-relocation API, so `last` delegates here: the script opens a lightweight `data:` trigger tab whose fragment carries the target URL, and the extension reads it, closes the trigger, and moves the real tab.

## Setup

1. Open `vivaldi://extensions` (or `chrome://extensions`)
2. Enable **Developer mode**
3. **Load unpacked** → select this directory
4. Open the extension's details and enable **Allow access to file URLs** (required for live reload of `file://` pages)

Add `<meta name="show-in-vivaldi">` to any HTML you want live-reloaded.
