FROM pytorch/pytorch:2.7.1-cuda12.8-cudnn9-runtime

WORKDIR /app
ENV HF_HOME=/data/models/hf PYTHONUNBUFFERED=1
RUN apt-get update \
    && apt-get install -y --no-install-recommends libsndfile1 sox \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY protocol.py qwen_engine.py server.py /app/
EXPOSE 10400
CMD ["python", "/app/server.py"]
