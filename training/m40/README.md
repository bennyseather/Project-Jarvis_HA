# M40 clean Brian voice training

M40 replaces the noisy M39 training set with 14 permission-confirmed Brian
recordings. The private dataset contains 826 accepted clips, 5,023.33 seconds
of speech at 22,050 Hz, and no clipping flags. Source audio, transcripts,
checkpoints, and exported models remain excluded from Git.

The private Colab upload archive is generated at:

`training/m40_dataset/m40-piper-dataset.zip`

Upload `M40_Piper_Training.ipynb` and the private dataset archive to a Google
Colab T4 GPU runtime. Run every cell from top to bottom. M40 uses batch size 16
and 60 epochs, producing roughly 3,100 optimization steps—enough to improve on
M39 without repeating its 250-epoch over-training pattern.

Download `jarvis-piper-m40.zip` when training completes. Keep the model private
and place it under `training/m40_models` for integration verification. Home
Assistant will load the accepted package from `/share/jarvis_voice` after the
M40 integration release.

If Colab GPU quota is unavailable, upload `M40_Piper_Training_Kaggle.ipynb` to
Kaggle, enable a GPU accelerator and Internet, and attach the private dataset
ZIP with **Add Input**. The resulting model is written to
`/kaggle/working/jarvis-piper-m40.zip` for download from notebook outputs.

For a persistent RunPod GPU, upload the private archive and
`train_runpod.py` to `/workspace/jarvis-m40`, then run the script inside
`tmux` or with `nohup`. The defaults retain clips up to 10 seconds/180
characters and use batch size 2 on a 24 GB RTX 4090. Checkpoints, logs, and
the exported `jarvis-piper-m40.zip` remain under `/workspace/jarvis-m40`.
