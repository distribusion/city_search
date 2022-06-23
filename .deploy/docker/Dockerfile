ARG PYTHON_IMAGE=python:3.9-slim-bullseye

FROM $PYTHON_IMAGE
WORKDIR /app

RUN apt update && apt install gcc -y && apt install -y build-essential libpq-dev

# Install package dependencies
RUN /usr/local/bin/python -m pip install --upgrade pip
RUN pip install --no-input "poetry>=1.2.0b1<2.0"

COPY poetry.lock ./
COPY pyproject.toml ./
RUN POETRY_VIRTUALENVS_CREATE=false poetry install --no-root
COPY ./ ./

# Install app
RUN pip install --no-deps .

COPY .deploy/docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
EXPOSE 80
ENTRYPOINT [ "/entrypoint.sh" ]
