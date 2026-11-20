FROM php:8.3-apache
RUN apt-get update && apt-get install -y --no-install-recommends git libicu-dev libzip-dev libpq-dev libpng-dev libjpeg-dev libfreetype6-dev libxml2-dev libonig-dev libcurl4-openssl-dev ca-certificates \
 && docker-php-ext-configure gd --with-freetype --with-jpeg \
 && docker-php-ext-install -j2 gd intl zip pgsql pdo_pgsql soap opcache \
 && rm -rf /var/lib/apt/lists/*
RUN git -c http.version=HTTP/1.1 clone --progress --depth 1 --branch MOODLE_405_STABLE https://github.com/moodle/moodle.git /var/www/html \
 && rm -rf /var/www/html/.git \
 && mkdir -p /var/moodledata /var/moodle-state \
 && chown www-data:www-data /var/moodledata /var/moodle-state \
 && ln -s /var/moodle-state/config.php /var/www/html/config.php \
 && printf 'max_input_vars=5000\nmemory_limit=256M\n' > /usr/local/etc/php/conf.d/moodle.ini
COPY config.template.php /opt/moodle-config.php

COPY entrypoint.sh /usr/local/bin/moodle-entrypoint
RUN chmod +x /usr/local/bin/moodle-entrypoint
ENTRYPOINT ["moodle-entrypoint"]
CMD ["apache2-foreground"]
