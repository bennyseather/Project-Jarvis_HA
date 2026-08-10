FROM python:3.13-slim

WORKDIR /app
ENV PYTHONPATH=/app HF_HOME=/models TORCH_HOME=/models/torch \
    OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4
RUN apt-get update \
    && apt-get install -y --no-install-recommends git libgomp1 libsndfile1 \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.6.0 torchaudio==2.6.0 \
    && pip install --no-cache-dir piper-tts==1.4.2 kokoro-onnx==0.5.0 "chatterbox-tts @ git+https://github.com/resemble-ai/chatterbox.git@5de7a54aa4e5e2baadb0182dde554908b48b85c2"
RUN python -c "from urllib.request import urlretrieve; base='https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/'; urlretrieve(base+'kokoro-v1.0.onnx','/app/kokoro-v1.0.onnx'); urlretrieve(base+'voices-v1.0.bin','/app/voices-v1.0.bin')"
COPY assets/jarvis-v5-reference.wav /app/jarvis-reference.wav
RUN python -c "from chatterbox.tts_turbo import ChatterboxTurboTTS; ChatterboxTurboTTS.from_pretrained(device='cpu',nano=True); print('Chatterbox Nano cached')"
COPY app /app
COPY addon_entrypoint.py /addon_entrypoint.py

CMD ["python", "/addon_entrypoint.py"]
