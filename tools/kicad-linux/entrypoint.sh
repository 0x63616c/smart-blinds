#!/bin/sh
set -eu
[ "$(uname -s)" = Linux ] || { echo 'Linux runner required' >&2; exit 64; }
mkdir -p "$XDG_CONFIG_HOME" "$XDG_CACHE_HOME" "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"
# Keep the private server alive across clients created during wx/GTK import.
# X server diagnostics are retained with the command log, never discarded.
exec xvfb-run -a -e /dev/stderr -s '-screen 0 1280x1024x24 -nolisten tcp -noreset' "$@"
