#!/bin/sh
set -eu

if [ -f /var/moodle-state/config.php ]; then
    cp --remove-destination /var/moodle-state/config.php /var/www/html/config.php
fi

exec docker-php-entrypoint "$@"
