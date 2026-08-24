#!/bin/bash
# Show an HTML file in a Chromium browser without duplicate tabs.
# Usage: [BROWSER=<app name>] show-in-browser.sh <absolute-path-or-url> [focus] [last]
#   BROWSER is the browser's macOS application name (default "Vivaldi", e.g.
#   BROWSER="Google Chrome"). Any Chromium browser works: they share the
#   AppleScript dictionary this script uses, and the extension is plain MV3.
#   If a tab already has this URL, leave it in place: the extension's live-reload
#   content script updates the page content on its own when the file changes,
#   with no flicker and no re-running of this script.
#   Otherwise open a new tab (new tabs always land at the end of the tab strip).
#   focus - bring the tab, its window, and the browser to the foreground.
#   last  - move an already-open tab to the end of the tab strip, keeping its
#           scroll position and history. Signalled by appending a fragment to the
#           tab's own URL (a same-document change, so no reload and no focus
#           change); the extension moves the tab and strips the fragment.
#   Without focus, the user's previously selected tab stays selected, and the
#   previously frontmost app keeps focus: the browser activates itself when a
#   tab is created via AppleScript (even `open -g` can't suppress this), so
#   after opening a new tab the script hands focus back to the app that had it.
#
# Live reload of file URLs requires the extension loaded and "Allow access to
# file URLs" enabled for it.
# Tab URLs are fetched one window at a time as a bulk list (`URL of tabs of w`),
# one Apple event per window; asking each tab individually takes tens of
# seconds on a session with many tabs.
# AppleScript's "move" is never used here: on Vivaldi tabs it destroys the tab
# and inserts a blank one, and tab indexes queried in the same osascript process
# after any tab mutation are unreliable.
set -euo pipefail
BROWSER="${BROWSER:-Vivaldi}"
INPUT=$1
case "$INPUT" in
    http://*|https://*) FILE_URL=$INPUT; IS_PATH=false ;;
    *)
        ENCODED_PATH=$(python3 -c "import urllib.parse, sys; print(urllib.parse.quote(sys.argv[1]))" "$INPUT")
        FILE_URL="file://$ENCODED_PATH"
        IS_PATH=true
        ;;
esac
shift

if [ "$(uname -s)" != "Darwin" ]; then
    HOST_FILE="$HOME/.config/show-in-browser/host"
    if [ ! -f "$HOST_FILE" ]; then
        echo "Missing $HOST_FILE. Create it with one line containing your Mac's tailnet hostname (for example, macbook.ts.net); macOS Remote Login must be enabled." >&2
        exit 1
    fi
    MACHOST=$(<"$HOST_FILE")

    if $IS_PATH; then
        IDENTITY=$(tailscale status --json | python3 -c 'import json, sys; s=json.load(sys.stdin)["Self"]; print(s["DNSName"].rstrip(".")); print(s["TailscaleIPs"][0])')
        TAILSCALE_DNS=${IDENTITY%%$'\n'*}
        TAILSCALE_IP=${IDENTITY#*$'\n'}
        FILE_URL="http://$TAILSCALE_DNS:8377$ENCODED_PATH"
        HEALTH_URL="http://$TAILSCALE_IP:8377/"

        if ! curl -sf -o /dev/null --max-time 2 "$HEALTH_URL"; then
            CONFIG_DIR="$HOME/.config/show-in-browser"
            mkdir -p "$CONFIG_DIR"
            SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
            setsid nohup python3 "$SCRIPT_DIR/serve.py" "$TAILSCALE_IP" 8377 >>"$CONFIG_DIR/serve.log" 2>&1 </dev/null &
            SERVER_READY=false
            for _ in 1 2 3 4 5 6 7 8 9 10; do
                if curl -sf -o /dev/null --max-time 2 "$HEALTH_URL"; then
                    SERVER_READY=true
                    break
                fi
                sleep 0.2
            done
            if ! $SERVER_READY; then
                echo "Failed to start the tailnet file server; see $CONFIG_DIR/serve.log" >&2
                exit 1
            fi
        fi
    fi

    exec ssh -o BatchMode=yes "$MACHOST" '~/Git/show-in-browser/show-in-browser.sh' "$FILE_URL" "$@"
fi

FOCUS=false
LAST=false
for opt in "$@"; do
    case "$opt" in
        focus) FOCUS=true ;;
        last) LAST=true ;;
        *) echo "unknown option: $opt" >&2; exit 1 ;;
    esac
done

PREV_APP=$(osascript -e 'tell application "System Events" to get name of first process whose frontmost is true')

# bash 3.2 misparses a heredoc placed directly inside $(...), so the osascript
# call lives in a function
find_or_open() {
    osascript - "$FILE_URL" "$LAST" <<EOF
on run argv
    set theURL to item 1 of argv
    set wantLast to item 2 of argv is "true"
    set markerURL to theURL & "#claude-move-to-end"
    tell application "$BROWSER"
        repeat with w in windows
            set urlList to URL of tabs of w
            repeat with i from 1 to count of urlList
                set u to item i of urlList
                if u is theURL or u is markerURL then
                    -- if the extension died mid-move, the fragment is left stuck
                    -- on the URL; strip it so the set below is a real URL change
                    if u is markerURL then set URL of (tab i of w) to theURL
                    if wantLast then
                        -- append a fragment to the tab's own URL: a same-document
                        -- change, so no reload and no focus change. The extension
                        -- moves this tab to the end and strips the fragment.
                        set URL of (tab i of w) to markerURL
                        return "moving tab to end"
                    end if
                    return "already open"
                end if
            end repeat
        end repeat
        set w to front window
        set prevActive to active tab index of w
        tell w to make new tab with properties {URL:theURL}
        set active tab index of w to prevActive
        return "opened new tab"
    end tell
end run
EOF
}
RESULT=$(find_or_open)
echo "$RESULT"

if [ "$RESULT" = "opened new tab" ] && ! $FOCUS; then
    # the browser is about to activate itself because of the new tab; wait for
    # that activation to land, then hand focus back
    sleep 0.5
    osascript -e "tell application \"System Events\" to set frontmost of process \"$PREV_APP\" to true"
fi

if $FOCUS; then
    # let the tab strip settle, then locate the tab fresh and bring it forward
    sleep 1
    osascript - "$FILE_URL" <<EOF
on run argv
    set theURL to item 1 of argv
    tell application "$BROWSER"
        repeat with w in windows
            set urlList to URL of tabs of w
            repeat with i from 1 to count of urlList
                set u to item i of urlList
                if u is theURL or u is (theURL & "#claude-move-to-end") then
                    set active tab index of w to i
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
