FROM python:3.10-slim-buster
RUN apt-get update && apt-get install -y \
  git gcc g++ libpq-dev python3-dev \
  && rm -rf /var/lib/apt/lists/*

RUN pip install -U pip

ADD ../requirements.txt /app/src/requirements.txt

WORKDIR /app/src

# Installing requirements
RUN pip install --no-cache-dir -r /app/src/requirements.txt

# Removing gcc
RUN apt-get purge -y \
  gcc \
  && rm -rf /var/lib/apt/lists/*

# Copying actuall application
COPY . /app/src/
ENV PYTHONPATH=.

CMD ["/usr/local/bin/python", "api/run.py"]