FROM python:3.13-slim

WORKDIR /app
ENV PYTHONPATH=/app
COPY app /app
COPY addon_entrypoint.py /addon_entrypoint.py

CMD ["python", "/addon_entrypoint.py"]
