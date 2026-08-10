FROM python:3.13-slim
WORKDIR /app
COPY app /app
COPY addon_entrypoint.py /addon_entrypoint.py
RUN pip install --no-cache-dir .
CMD ["python", "/addon_entrypoint.py"]
