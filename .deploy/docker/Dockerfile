FROM python:3.9-slim-bullseye

WORKDIR /app
RUN pip install --no-input "poetry>=1.2.0b1<2.0"

# Install packages in a cache-friendly way
COPY poetry.lock ./
COPY pyproject.toml ./
RUN POETRY_VIRTUALENVS_CREATE=false poetry install --no-root

# Copy package source code
COPY ./city_search ./city_search

# Install package
RUN pip install --no-deps .

CMD [ "gunicorn", \
    "-w", "1", \
    "-k", "uvicorn.workers.UvicornWorker", \
    "city_search.main:app", \
    "--bind", "0.0.0.0:8000", \
    "--timeout", "120" \
    ]
