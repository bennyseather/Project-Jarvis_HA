# Project Jarvis Qwen Voice Worker

This optional GPU worker runs Qwen3-TTS 1.7B outside Home Assistant and exposes
only a Wyoming TTS endpoint. Home Assistant retains its dedicated host; the
Project Jarvis Voice add-on connects to this worker over a private LAN or VPN.

## Private files

Create `private/reference.wav` and `private/reference.txt`. The transcript must
match the reference audio exactly. These files, the model cache, and generated
audio must never be committed or included in a public image.

The approved M41 reference SHA-256 is
`bdeda866d836e49275018966aa9b80066af6bbc4bd7e55c4507f513e58e2696f`.
Its exact transcript is retained privately with the reference.

## GPU deployment

1. Install Docker, the NVIDIA driver, and NVIDIA Container Toolkit.
2. Copy this directory to the GPU machine.
3. Put the two private reference files in `private/`.
4. Run `docker compose up -d --build`.
5. Keep TCP `10400` private. For a cloud GPU, use Tailscale or another private
   VPN; do not expose the unauthenticated Wyoming port publicly.
6. Watch startup with `docker compose logs -f`. The first start downloads about
   4.5 GB and logs model-load and prompt-encoding times before listening.

The worker loads the model once, encodes the approved reference once, serializes
requests, and emits the first completed sentence immediately. A persistent
Docker volume retains the public model weights between restarts.
