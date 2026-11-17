<?php
unset($CFG);
global $CFG;
$CFG = new stdClass();
$CFG->dbtype = 'pgsql';
$CFG->dblibrary = 'native';
$CFG->dbhost = 'db';
$CFG->dbname = 'moodle';
$CFG->dbuser = 'moodle';
$CFG->dbpass = getenv('POSTGRES_PASSWORD');
$CFG->prefix = 'mdl_';
$CFG->wwwroot = 'http://localhost:8080';
$CFG->dataroot = '/var/moodledata';
$CFG->directorypermissions = 02770;
$CFG->admin = 'admin';
// O cliente REST interno usa o DNS do Compose; links usam wwwroot.
require_once('/var/www/html/lib/setup.php');
