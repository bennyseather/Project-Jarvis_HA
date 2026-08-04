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
