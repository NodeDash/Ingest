#FROM python:3.13.3-alpine3.21  - For now Python 3.11 or newer
# doesn't work due to js2py bytecode errors.
# Issue - https://github.com/PiotrDabkowski/Js2Py/issues/334
FROM python:3.11.12-alpine3.21

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app
COPY . .
RUN rm -rf venv
RUN rm -rf .venv
RUN rm -rf __pycache__

# Fix CVE-2023-5752, CVE-2024-6345
# Can be removed when js2py is compatible with Python 3.13.
RUN pip install -U pip setuptools

RUN pip install -r requirements.txt
ENTRYPOINT ["uvicorn", "app.main:app", "--host", "0.0.0.0"]
