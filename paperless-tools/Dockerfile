FROM python:3.12-slim

# Pull Debian security fixes that land before the next base-image rebuild.
RUN apt-get update \
 && apt-get upgrade -y --no-install-recommends \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# pip is only needed at build time. Removing it also removes the copies of
# msgpack, urllib3 and setuptools it vendors, which trivy flags.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
 && pip uninstall -y pip

COPY app.py .

RUN useradd --create-home --uid 1000 tools
USER tools

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
