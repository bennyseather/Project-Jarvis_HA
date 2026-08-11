# Project Jarvis Local Qwen Voice Worker

This experimental add-on runs Qwen3-TTS 1.7B directly on the Home Assistant
computer. It requires an amd64 processor, at least 16 GB RAM, and approximately
10 GB of free storage for the image and public model cache. The i5-8500/64 GB
Project Jarvis host satisfies the memory requirement; actual CPU latency must be
measured before this becomes the preferred voice route.

## Private reference

Create these files before starting the add-on:

- `/share/jarvis_voice/qwen-reference.wav`
- `/share/jarvis_voice/qwen-reference.txt`

The transcript must match the audio exactly. Neither file is included in Git,
HACS, the add-on image, logs, or generated output.

## Connection

After the worker reports `listening on 0.0.0.0:10400`, configure Project Jarvis
Voice with `engine: qwen_1_7b`, the Home Assistant computer's LAN address as
`qwen_host`, and `qwen_port: 10400`.
