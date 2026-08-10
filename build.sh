#!/usr/bin/env bash
set -o errexit

python -m pip install --upgrade pip
pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate --noinput
python manage.py cargar_red_vial
python manage.py cargar_rendimientos
python manage.py crear_admin_inicial
