FROM python:3.10-slim-buster
RUN apt-get update && apt-get install -y \
  git gcc g++ libpq-dev python3-dev \
  && rm -rf /var/lib/apt/lists/*

ARG APP_USER=appuser
RUN groupadd -r ${APP_USER} && useradd --no-log-init -r -g ${APP_USER} ${APP_USER}

RUN apt-get update && apt-get install -y git gcc g++ libpq-dev python3-dev
RUN pip install -U pip


ADD requirements.txt /requirements.txt

RUN pip install --no-cache-dir -r /requirements.txt

RUN apt-get purge -y gcc

# Copying actuall application
COPY . /app/src/
ENV PYTHONPATH=.

CMD ["/usr/local/bin/python", "api/run.py"]