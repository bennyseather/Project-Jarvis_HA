# M39 voice training

The approved source recordings remain outside Git. Prepare a local, reviewable
dataset with:

```powershell
.venv\Scripts\python.exe tools\prepare_m39_voice_dataset.py `
  C:\Users\besa\Downloads\Xeno1.mp3 `
  C:\Users\besa\Downloads\Xeno2.mp3 `
  C:\Users\besa\Downloads\Xeno3.mp3 `
  --output training\m39_dataset --model small.en
```

Every row in `review.csv` must be listened to, corrected and changed from
`needs_review` to `accepted` or `rejected` before training. Rebuild
`metadata.csv` from accepted rows only. Do not train on music, another speaker,
applause, interview audio, clipped speech or incorrect transcripts.

Start the local review interface with:

```powershell
.venv\Scripts\python.exe tools\review_m39_voice_dataset.py `
  --dataset training\m39_dataset
```

Open `http://127.0.0.1:8765`. Each decision is saved immediately and
`metadata.accepted.csv` is rebuilt after every review.

Piper medium fine-tuning requires a CUDA-capable training environment. The
development and Home Assistant computers are inference targets, not training
hosts. Export the reviewed checkpoint to ONNX and place the model and matching
JSON configuration under `training/m39_models` for integration verification.

After review, create the private Colab upload archive:

```powershell
.venv\Scripts\python.exe tools\package_m39_voice_dataset.py `
  --dataset training\m39_dataset `
  --output training\m39_dataset\m39-piper-dataset.zip
```

Upload `M39_Piper_Training.ipynb` to Google Colab, select a T4 GPU runtime, run
all cells, and download `jarvis-piper-m39.zip`. Do not publish the private
dataset or training checkpoint.

Copy the downloaded archive to `training/m39_models` for local verification.
For Home Assistant acceptance testing, upload it unchanged to
`/share/jarvis_voice/jarvis-piper-m39.zip`. The public add-on loads the model
from shared storage so the trained voice is not published in Git.
