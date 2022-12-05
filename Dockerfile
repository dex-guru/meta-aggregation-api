# https://github.com/numpy/numpy/issues/17569#issuecomment-922447582
FROM registry.gitlab.com/telekomconsalting/dexguru/dexguru-backend/python:3.10-slim

# TODO: remove comments, because they look redundant

# Create a group and user to run our app
ARG APP_USER=appuser
RUN groupadd -r ${APP_USER} && useradd --no-log-init -r -g ${APP_USER} ${APP_USER}

RUN apt-get update && apt-get install -y git gcc g++ libpq-dev python3-dev
RUN pip install -U pip


# Copy in your requirements file
ADD requirements.txt /requirements.txt

# OR, if you're using a directory for your requirements, copy everything (comment out the above and uncomment this if so):
# ADD requirements /requirements

RUN pip install --no-cache-dir -r /requirements.txt

RUN apt-get purge -y gcc

# Copy your application code to the container (make sure you create a .dockerignore file if any large files or directories should be excluded)
RUN mkdir /code/
WORKDIR /code/
ADD . /code/
ENV PYTHONPATH=.

EXPOSE 8000

RUN chown -R ${APP_USER}:${APP_USER} tests/

# Change to a non-root user
USER ${APP_USER}:${APP_USER}

# Uncomment after creating your docker-entrypoint.sh
# ENTRYPOINT ["/code/docker-entrypoint.sh"]

CMD ["python", "api/run.py"]
