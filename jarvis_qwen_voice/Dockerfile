FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 HF_HOME=/data/models/hf \
    OMP_NUM_THREADS=6 MKL_NUM_THREADS=6 OPENBLAS_NUM_THREADS=6
RUN apt-get update \
    && apt-get install -y --no-install-recommends libsndfile1 sox \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.7.1 torchaudio==2.7.1 \
    && pip install --no-cache-dir qwen-tts==0.1.1 soundfile==0.13.1
COPY app /app
COPY addon_entrypoint.py /addon_entrypoint.py
CMD ["python", "/addon_entrypoint.py"]
