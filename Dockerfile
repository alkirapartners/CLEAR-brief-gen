FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501

HEALTHCHECK CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/api/brief/health')" || exit 1

# The API trusts the X-Auth-Email header, so it must only ever be reachable
# through the proxy that sets it. Inside the container it listens on all
# interfaces; docker-compose.yml publishes the port on the host's loopback only.
ENTRYPOINT ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8501"]
