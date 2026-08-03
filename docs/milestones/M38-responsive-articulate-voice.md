# M38 - Responsive and Articulate Jarvis Voice

Status: complete

M38 keeps the approved Chatterbox Nano Jarvis v5 identity while removing the
repeated reference-conditioning cost from every segment. Conditioning is cached
once per app process and a short startup generation warms the CPU execution path.

Long replies use bounded sentence and clause segmentation with protection for
decimals and common abbreviations. The default crisp articulation preset reduces
generation variation and repetition, while a subtle low-mid finishing layer and
lower pitch factor make the voice slightly darker without reducing speed.

The Wyoming description exposes conditioning, warm-up, most recent segment and
time-to-first-audio diagnostics. Chatterbox remains serialized and bounded by the
configured timeout, with Kokoro and Piper retained as fallbacks.

The acceptance target on the i5-8500/64 GB Home Assistant host is approximately
one to four seconds to first audio after startup warm-up. Real latency remains
dependent on reply length and Home Assistant's playback pipeline.
