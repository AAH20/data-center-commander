FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir prometheus-client==0.21.1

COPY exporter.py /app/exporter.py

EXPOSE 9091

CMD ["python", "/app/exporter.py"]
