#!/bin/bash
cd /home/site/wwwroot
python -m pip install --target /home/site/wwwroot/deps -r requirements.txt 2>&1
export PYTHONPATH=/home/site/wwwroot/deps:$PYTHONPATH
exec gunicorn app.main:app --bind 0.0.0.0:8000 --workers 2 --worker-class uvicorn.workers.UvicornWorker --timeout 120