#!/bin/bash
set -e

cd ~/apps/health_feedback_app

git pull

cd backend
source venv/bin/activate

pip install -r requirements.txt

python manage.py migrate
python manage.py collectstatic --noinput

sudo systemctl restart gunicorn

echo "Deployment completed successfully."