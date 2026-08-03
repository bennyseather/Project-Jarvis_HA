FROM python:3.12-slim

WORKDIR /app
ENV PYTHONPATH=/app
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir kokoro-onnx==0.5.0
RUN python -c "from urllib.request import urlretrieve; base='https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/'; urlretrieve(base+'kokoro-v1.0.onnx','/app/kokoro-v1.0.onnx'); urlretrieve(base+'voices-v1.0.bin','/app/voices-v1.0.bin')"
COPY app /app
COPY addon_entrypoint.py /addon_entrypoint.py

CMD ["python", "/addon_entrypoint.py"]
