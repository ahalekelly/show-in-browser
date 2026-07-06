# show-in-vivaldi

Show local HTML files in Vivaldi from the command line — deduplicating tabs, reloading in place, and optionally moving the tab to the end of the strip. Two parts: a CLI script (`show-in-vivaldi.sh`) that drives Vivaldi over AppleScript, and a small Chromium extension that provides the one thing AppleScript cannot do (truly moving a tab without reloading it).

## show-in-vivaldi.sh

`show-in-vivaldi.sh <absolute-path> [focus] [last]` shows a local HTML file in Vivaldi without duplicate tabs: it reloads the existing tab if the file is already open, or opens a new tab, quietly in the background by default. `focus` brings the tab to the foreground; `last` moves it to the end of the tab strip via the extension. Reload and move both preserve scroll position.

Why AppleScript for most of it: query, reload, create, and focus are all reliable over Vivaldi's AppleScript interface. Moving a tab is not — AppleScript's `move` destroys the tab and inserts a blank one in its place, losing scroll position and history. `chrome.tabs.move` is the only real tab-relocation API, so the `last` option delegates to the extension.

## The extension

A minimal Chromium extension that moves an existing tab to the end of its window **without reloading it** — scroll position and history are preserved.

Open `<url>#claude-move-to-end` in a new tab. The extension closes that trigger tab and moves the already-open tab whose URL is exactly `<url>` to the end of its window. Closing the trigger tab also restores the previously selected tab, so nothing steals focus.

Example trigger from AppleScript:

```applescript
tell application "Vivaldi"
    tell front window to make new tab with properties {URL:"file:///path/to/report.html#claude-move-to-end"}
end tell
```

If a tab with the `#claude-move-to-end` marker lingers, the extension is not installed or not enabled.

## Install the extension

1. Open `vivaldi://extensions` (or `chrome://extensions`)
2. Enable **Developer mode**
3. **Load unpacked** → select this directory
