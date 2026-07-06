#!/bin/bash
# Show a local HTML file in Vivaldi without duplicate tabs.
# Usage: vivaldi-show.sh <absolute-path> [focus] [last]
#   If a tab already has this URL, reload it (quietly, in the background;
#   reload preserves the tab's scroll position).
#   Otherwise open a new tab (new tabs always land at the end of the tab strip).
#   focus - also bring the tab, its window, and Vivaldi to the foreground.
#   last  - move an already-open tab to the end of the tab strip, keeping its
#           scroll position and history. Requires the "Tab Mover for Claude"
#           extension in this repo: the script
#           opens <url>#claude-move-to-end as a trigger tab, which the extension
#           consumes and closes after moving the real tab. If a tab with that
#           marker URL lingers, the extension is not installed or not enabled.
#   Without focus, the user's previously selected tab stays selected.
#   AppleScript's "move" is never used here: on Vivaldi tabs it destroys the tab
#   and inserts a blank one, and tab indexes queried in the same osascript
#   process after any tab mutation are unreliable.
set -euo pipefail
FILE_URL="file://$(python3 -c "import urllib.parse, sys; print(urllib.parse.quote(sys.argv[1]))" "$1")"
shift
FOCUS=false
LAST=false
for opt in "$@"; do
    case "$opt" in
        focus) FOCUS=true ;;
        last) LAST=true ;;
        *) echo "unknown option: $opt" >&2; exit 1 ;;
    esac
done

osascript - "$FILE_URL" "$LAST" <<'EOF'
on run argv
    set theURL to item 1 of argv
    set wantLast to item 2 of argv is "true"
    tell application "Vivaldi"
        repeat with w in windows
            repeat with t in tabs of w
                if URL of t is theURL then
                    reload t
                    if wantLast then
                        -- trigger tab for the Tab Mover extension; it moves the
                        -- real tab to the end, then closes this tab, which also
                        -- restores the user's previously selected tab
                        tell w to make new tab with properties {URL:theURL & "#claude-move-to-end"}
                        return "moved tab to end"
                    end if
                    return "reloaded existing tab"
                end if
            end repeat
        end repeat
        set w to front window
        set prevActive to active tab index of w
        tell w to make new tab with properties {URL:theURL}
        -- restore the user's selected tab (index saved before the mutation)
        set active tab index of w to prevActive
        return "opened new tab"
    end tell
end run
EOF

if $FOCUS; then
    # let the tab strip settle, then locate the tab fresh and bring it forward
    sleep 1
    osascript - "$FILE_URL" <<'EOF'
on run argv
    set theURL to item 1 of argv
    tell application "Vivaldi"
        repeat with w in windows
            set tabIndex to 0
            repeat with t in tabs of w
                set tabIndex to tabIndex + 1
                if URL of t is theURL then
                    set active tab index of w to tabIndex
                    set index of w to 1
                    activate
                    return
                end if
            end repeat
        end repeat
    end tell
end run
EOF
fi
