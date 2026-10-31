#!/bin/sh
set -eu

# Support Docker secrets: VAR_FILE=/run/secrets/xxx -> VAR=<file content>
for var in ILO_HOST ILO_USERNAME ILO_PASSWORD; do
    file_var="${var}_FILE"
    eval "file=\${$file_var:-}"
    if [ -n "$file" ]; then
        if [ ! -r "$file" ]; then
            echo "[entrypoint] $file_var points to an unreadable file: $file" >&2
            exit 1
        fi
        export "$var=$(cat "$file")"
        unset "$file_var"
    fi
done

for var in ILO_HOST ILO_USERNAME ILO_PASSWORD; do
    eval "val=\${$var:-}"
    [ -n "$val" ] || echo "[entrypoint] Warning: $var (or ${var}_FILE) is not set" >&2
done

exec "$@"
