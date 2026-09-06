# show-in-browser

Show local files in a Mac Chromium browser from the command line or a headless Linux box, with **flicker-free live reload for HTML**. Two parts: a CLI script (`show-in-browser.sh`) that opens/focuses/moves tabs over AppleScript, and a Chromium extension that updates page content in place and moves tabs — the two things AppleScript can't do without a visible flash.

## show-in-browser.sh

`show-in-browser.sh <absolute-path> [focus] [last]` opens a local file without duplicate tabs. It targets Vivaldi by default; set `BROWSER_APP` to another Chromium browser's application name (e.g. `BROWSER_APP="Google Chrome"`) — they all share the AppleScript dictionary the script uses. (Not `BROWSER`: that conventional variable holds a URL-opener command, and agent harnesses export `BROWSER=true`, which is no app name at all.) If the tab is already open it leaves it alone — the extension keeps HTML content current on its own. `focus` brings the tab to the foreground; `last` moves it to the end of the tab strip. Without `focus` the browser never keeps focus: Chromium activates itself when AppleScript creates a tab (even `open -g` can't suppress it), so after opening a new tab the script hands focus back to the app that had it — expect a sub-second flash of the browser on first open, and no focus change at all on later runs.

## Remote mode (headless Linux → Mac)

On a Linux box in the same tailnet, the same `show-in-browser.sh <absolute-path> [focus] [last]` command opens the file's tailnet URL in the Mac's browser. Put the Mac's tailnet hostname on one line in `~/.config/show-in-browser/host`, enable **Remote Login** on the Mac, and configure key-based SSH access.

Install the user service and enable lingering so the server starts at boot:

```sh
systemctl --user link "$HOME/Git/show-in-browser/systemd/show-in-browser.service"
systemctl --user enable --now show-in-browser.service
loginctl enable-linger "$USER"
```

The server binds only to the Linux box's Tailscale IP. It serves HTML, Markdown, and PDF documents under the user's home directory by default, plus the assets pages reference: CSS, JavaScript, JSON, XML, WebAssembly, web manifests, fonts, images, audio, and video (the full suffix list is `SERVABLE_SUFFIXES` in `serve.py`). Other paths are rejected. Passing another regular file to `show-in-browser.sh` authorizes that file until reboot. Text responses are gzipped. The extension injects only into matching `http://*.ts.net/*.html`, `.htm`, and `.xhtml` pages, leaving other formats to the browser.

## The extension

**Live reload (no flicker).** A content script runs on every matched local or tailnet page. It polls the file — every second while the tab is visible, not at all while hidden, with an immediate poll on becoming visible — and when it changes, swaps the page content in a single paint instead of navigating, so there is no white flash and the scroll position is kept. Edit the file and the open page updates itself; you don't re-run the script to refresh. Pages with `<script>`s get a normal (flashing) reload instead, because the swap would not re-run them. A page without a `<title>` gets one from its first `<h1>`, or its file name, so the tab shows a name instead of the address.

The file is read by an offscreen extension document: content scripts and pages cannot read `file://` because their requests use the page's `file://` origin, and the service worker has no XHR and its `fetch(file://)` is unreliable. The content script messages the service worker, which relays to an offscreen document whose `chrome-extension://` origin can XHR `file://` when the extension has file access. The offscreen document remembers the last text served per tab and answers "unchanged" otherwise, so the full file text only crosses process boundaries on a real change — polling a large report costs almost nothing.

Why not AppleScript: its `reload` does a full document reload (blank → refetch → repaint), which always flashes.

**Move to end (no reload, no flash).** Moving a tab's position doesn't reload its page, but AppleScript's `move` destroys the tab and inserts a blank one, and creating a trigger tab flashes the foreground because the browser activates new tabs. So `last` instead appends `#claude-move-to-end` to the report tab's own URL — a same-document change that neither reloads the page nor changes the active tab — and the extension (`chrome.tabs.move`, the only real relocation API) moves that tab to the end and strips the fragment. This stays flicker-free even when the moved tab is in the background and you're viewing another tab.

## Setup

1. Open `vivaldi://extensions` (or `chrome://extensions`)
2. Enable **Developer mode**
3. **Load unpacked** → select this directory
4. Open the extension's details and enable **Allow access to file URLs** (required for live reload of `file://` pages)

All local and matched tailnet `.html`/`.htm`/`.xhtml` pages are live-reloaded. Other file types are left alone: non-HTML files render through browser-generated wrapper documents the swap would clobber, and `.md` has a dedicated markdown extension.
