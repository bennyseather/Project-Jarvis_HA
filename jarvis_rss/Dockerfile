FROM python:3.12-alpine
WORKDIR /app
ENV PYTHONUNBUFFERED=1
RUN pip install --no-cache-dir feedparser==6.0.11
COPY app /app
CMD ["python", "/app/main.py"]
