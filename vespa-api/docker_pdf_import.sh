#!/bin/bash

import_folder=${1:-data}
docker-compose exec vespa-api pipenv run python pdf_import.py $import_folder