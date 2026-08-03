FROM python:3.13-slim

WORKDIR /app
ENV PYTHONPATH=/app HF_HOME=/models TORCH_HOME=/models/torch \
    OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4
RUN apt-get update \
    && apt-get install -y --no-install-recommends git libgomp1 libsndfile1 \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.6.0 torchaudio==2.6.0 \
    && pip install --no-cache-dir kokoro-onnx==0.5.0 "chatterbox-tts @ git+https://github.com/resemble-ai/chatterbox.git@5de7a54aa4e5e2baadb0182dde554908b48b85c2"
RUN python -c "from urllib.request import urlretrieve; base='https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/'; urlretrieve(base+'kokoro-v1.0.onnx','/app/kokoro-v1.0.onnx'); urlretrieve(base+'voices-v1.0.bin','/app/voices-v1.0.bin')"
RUN python -c "import wave,numpy as np; from kokoro_onnx import Kokoro; k=Kokoro('/app/kokoro-v1.0.onnx','/app/voices-v1.0.bin'); a,r=k.create('Good evening. Project Jarvis is online and ready to assist. All systems are operating normally.',voice='bm_daniel',speed=1.05,lang='en-gb'); w=wave.open('/app/jarvis-reference.wav','wb'); w.setparams((1,2,int(r),0,'NONE','')); w.writeframes((np.clip(a,-1,1)*32767).astype('<i2').tobytes()); w.close()"
RUN python -c "from chatterbox.tts_turbo import ChatterboxTurboTTS; ChatterboxTurboTTS.from_pretrained(device='cpu',nano=True); print('Chatterbox Nano cached')"
COPY app /app
COPY addon_entrypoint.py /addon_entrypoint.py

CMD ["python", "/addon_entrypoint.py"]
