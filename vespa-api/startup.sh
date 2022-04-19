#!/bin/bash

# start pdf import in background
# pipenv run python pdf_import.py data/ &

crontab cron_container.txt && cron

# start api in foreground
pipenv run gunicorn --config gunicorn.conf wsgi:app