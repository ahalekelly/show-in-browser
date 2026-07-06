# Tab Mover for Claude

A minimal Chromium extension that moves an existing tab to the end of its window **without reloading it** — scroll position and history are preserved. Built because AppleScript cannot truly move Vivaldi/Chrome tabs (its `move` command destroys the tab and inserts a blank one); `chrome.tabs.move` is the only real tab-relocation API.

## How it works

Open `<url>#claude-move-to-end` in a new tab. The extension closes that trigger tab and moves the already-open tab whose URL is exactly `<url>` to the end of its window. Closing the trigger tab also restores the previously selected tab, so nothing steals focus.

Example trigger from AppleScript:

```applescript
tell application "Vivaldi"
    tell front window to make new tab with properties {URL:"file:///path/to/report.html#claude-move-to-end"}
end tell
```

If a tab with the `#claude-move-to-end` marker lingers, the extension is not installed or not enabled.

## Install

1. Open `vivaldi://extensions` (or `chrome://extensions`)
2. Enable **Developer mode**
3. **Load unpacked** → select this directory

Used by `~/.claude/scripts/vivaldi-show.sh` (the `last` option).
