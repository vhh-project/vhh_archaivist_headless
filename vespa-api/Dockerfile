FROM python:3.10.1-slim-buster
WORKDIR /code
COPY . .
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_RUN_PORT=5001
ENV GUNICORN_BIND=0.0.0.0:5001
RUN apt-get update && apt-get install -y \
curl poppler-utils cron
RUN pip install --upgrade pip
RUN pip install pipenv
RUN pipenv install
EXPOSE 5001
RUN chmod +x startup.sh
ENTRYPOINT ./startup.sh
