FROM registry.gitlab.com/telekomconsalting/dexguru/dexguru-backend/python:3.10-slim

ARG APP_USER=appuser
RUN groupadd -r ${APP_USER} && useradd --no-log-init -r -g ${APP_USER} ${APP_USER}

ADD requirements.txt /requirements.txt
RUN apt-get update && apt-get install -y git gcc g++ libpq-dev python3-dev && \
    pip install -U pip && pip install --no-cache-dir -r /requirements.txt && \
    apt-get purge -y gcc && apt-get clean

RUN mkdir /code/
WORKDIR /code/
ADD . /code/
ENV PYTHONPATH=.

EXPOSE 8000

RUN chown -R ${APP_USER}:${APP_USER} tests/

USER ${APP_USER}:${APP_USER}

CMD ["python", "api/run.py"]
