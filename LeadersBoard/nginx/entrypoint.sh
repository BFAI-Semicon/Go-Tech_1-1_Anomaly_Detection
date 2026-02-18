#!/bin/sh
set -e

HTPASSWD="/etc/nginx/auth/htpasswd"

if [ ! -r "$HTPASSWD" ]; then
    echo "htpasswd missing or unreadable" >&2
    exit 1
fi

exec nginx -g 'daemon off;'
