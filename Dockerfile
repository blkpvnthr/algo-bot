FROM python:3.11

WORKDIR /srv/app
ENV PYTHONPATH=/srv/app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV WORK_ROOT=/srv/app/workspaces
ENV DB_PATH=/srv/app/app.db

EXPOSE 5001
RUN mkdir -p /srv/app/data /srv/app/workspaces && chmod -R 777 /srv/app/data /srv/app/workspaces

CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5001", "wsgi:app"]
