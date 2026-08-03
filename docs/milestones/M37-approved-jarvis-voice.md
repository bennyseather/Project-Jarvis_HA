# M37 - Approved Jarvis Voice Integration

## Outcome

Project Jarvis Voice ships the owner-approved v5 Chatterbox reference and a
dedicated runtime profile matching the accepted crisp, staccato and balanced
synthetic/metallic sound. The finishing layer remains bounded below the grainy
quantisation boundary and generated reply audio remains memory-only.

## Architecture

Chatterbox Nano remains the primary warm, serialized CPU engine. Its bundled
mono 24 kHz reference is copied into the app image instead of being regenerated
during every image build. Each generated sentence receives bounded delivery
acceleration, long-pause compression, a light synthetic presence pass and a
controlled metallic pass. Kokoro and Piper remain ordered automatic fallbacks.

The `jarvis_v5` chain has one user strength control. Internally it caps the
synthetic mix at 0.20 and the metallic mix at 0.61. Long silence runs of at
least 100 ms are shortened to the configured 25 ms default without removing
speech samples. The implementation is deterministic PCM16 processing and does
not add another model or network dependency.

## Migration and boundaries

An installation using the exact legacy 0.27.2 default profile, strength, gain
and pitch migrates to v5 at startup. Any explicit custom profile or level is
preserved. Home Assistant continues to own pipelines, devices, permissions and
audio routing. This milestone changes voice presentation only and grants no new
home-control, research, memory or orchestration capability.

The source permission record is retained by the project owner. Repository
documentation records the non-commercial open-source scope and reference hash
without publishing personal signature material.

## Acceptance

Automated coverage verifies the reference format and hash, deterministic and
bounded v5 output, pause compression, legacy-default migration, preservation of
custom profiles, versioned discovery and retained Kokoro/Piper fallbacks. Home
Assistant acceptance uses both Try voice and a wake-word follow-up to confirm
the profile remains crisp and intelligible on short and longer replies.
