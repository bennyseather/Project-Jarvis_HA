# M35 - High-Quality Local Jarvis Neural Voice

## Outcome

Project Jarvis Voice uses Chatterbox Nano as an optional warm CPU engine on
the amd64 Home Assistant host. Sentence-sized generation begins Wyoming audio
delivery after the first segment, with Kokoro and Piper retained as ordered
fallbacks. The target is one to four seconds to first audio for ordinary short
replies on the approved i5-8500T and 64 GiB host.

## Voice and privacy

The included reference is generated from the permissively licensed Kokoro
British voice using original Project Jarvis text. It contains no actor or
copyrighted-media recording. User audio is never stored. Chatterbox's standard
watermark remains intact before the bounded Jarvis finishing layer.

Every native or externally routed spoken response removes source sections,
Markdown links, and URL addresses at the final Home Assistant voice boundary.
Typed Assist responses and internal structured research sources remain intact.

## Operational boundaries

Only one neural synthesis runs at a time. The model is warmed at startup,
generation is timeout-bounded, and failures fall through to Kokoro and then
Piper. Home Assistant continues to own pipelines and audio routing.

The Wyoming boundary is deliberately host-independent. A later dedicated AI
computer may run the language model, voice service, or both without coupling
their lifecycle to the dedicated Home Assistant computer.
