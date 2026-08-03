# Project Jarvis Roadmap

## Approved Future Direction

Future candidate: voice activation and wake-word routing for Jarvis, subject to
a separate privacy, microphone ownership, false-activation, and Home Assistant
voice-pipeline architecture review.

### M30 - Episodic Conversation Continuity (complete)

- M30.1 Typed episodic policy and lifecycle complete
- M30.2 Local low-sensitivity summary generation complete
- M30.3 Explicit and sensitive-confirmed summary flow complete
- M30.4 Bounded retrieval and conversational continuity complete
- M30.5 Expiry, pinning, capacity, and hard deletion complete
- M30.6 Inspectable natural-language management controls complete
- M30.7 Privacy regression, packaging, and release complete

### M29 - Adaptive Jarvis Personality (complete)

- M29.1 Context-sensitive character and presentation layer complete
- M29.2 Explicit relationship continuity controls complete
- M29.3 Adaptive text and bounded voice response styles complete
- M29.4 Bounded initiative and social-intelligence guidance complete
- M29.5 Restrained original wit and repetition controls complete
- M29.6 British synthetic voice presentation guidance complete
- M29.7 Inspectability, safety regression, packaging, and release complete

### M27 - Open Knowledge and Live Research (complete)

- M27.1 Typed research policy and provider-neutral routing complete
- M27.2 OpenAI native web-search integration complete
- M27.3 Bounded source extraction and conversational continuity complete
- M27.4 Automatic and explicit research controls complete
- M27.5 Explicit research-memory consent and deletion complete
- M27.6 Home Assistant packaging, acceptance, and release complete

### M26 - Jarvis Personality and Social Continuity (complete)

- M26.1 Typed personality profile and safety boundaries complete
- M26.2 Context-sensitive British-English expression complete
- M26.3 Durable explicit social preferences complete
- M26.4 Natural interaction guidance and restrained variation complete
- M26.5 Inspect, adjust, reset, and delete controls complete
- M26.6 Voice guidance, acceptance, documentation, and release complete

### M25 - Contextual Goal-Based Orchestration (complete)

- M25.1 Goal and outcome contracts complete
- M25.2 Durable, user-controlled home goal vocabulary complete
- M25.3 Current-state-aware plan construction complete
- M25.4 Ambiguity, confidence, evidence, and explanation complete
- M25.5 M24 execution and confirmation integration complete
- M25.6 Acceptance, documentation, packaging, and release complete

### M24 - Compound Home Orchestration (complete)

- M24.1 Compound plan contracts and bounded policy complete
- M24.2 Deterministic multi-action decomposition complete
- M24.3 Topology resolution and existing authorization integration complete
- M24.4 Parallel, sequential, conditional, and exclusion execution complete
- M24.5 Combined confirmation, correction, and partial recovery complete
- M24.6 Runtime acceptance, packaging, and release complete

### M23 - Whole-Home Situational Intelligence (complete)

- M23.1 Home topology contracts complete
- M23.2 Bounded topology assembly complete
- M23.3 Compound status reasoning complete
- M23.4 Spatial and conversational continuity complete
- M23.5 Temporal situational reasoning complete
- M23.6 Runtime integration, acceptance, packaging, and release complete

### M22 - Proactive Assistance and Routine Intelligence (complete)

- M22.1 Proactive assistance contracts and deterministic policy complete
- M22.2 Bounded opportunity detection complete
- M22.3 Inspectable routine candidates complete
- M22.4 Home Assistant notification and opt-in voice delivery complete
- M22.5 Natural controls, explanations, suppression, and action routing complete
- M22.6 Migration, acceptance, packaging, and release complete

### Detour D1 - Jarvis Command Center (complete)

- D1.1 Original visual system and responsive layout complete
- D1.2 Desktop and portrait Home Assistant themes complete
- D1.3 Five-view native Sections dashboard complete
- D1.4 Preferred-pipeline Assist and voice controls complete
- D1.5 Original visual assets and preview complete
- D1.6 Installation package, documentation, validation, and release complete
- D2.1 Squared Jarvis HUD theme and shared design tokens complete
- D2.2 Visual card-editor framework complete
- D2.3 Entity control card collection complete
- D2.4 Original Jarvis icon set and automatic mapping complete
- D2.5 Component catalog and local coverage audit complete
- D2.6 Packaging, documentation, compatibility, and release complete
- D1.7 Interactive Jarvis voice and action cards complete

### Detour D3 - Complete Jarvis Dashboard System (complete)

- D3.1 Shared Jarvis design tokens and responsive foundation complete
- D3.2 Thirty-three visual-editor-compatible cards complete
- D3.3 Container-aware desktop and NSPanel behavior complete
- D3.4 Room summaries and polished room-detail views complete
- D3.5 Expanded reusable icon and component catalog complete
- D3.6 Compatibility, performance, documentation, and release complete
- D3.7 Jarvis Entity, Shortcut, Progress, and Home/Away badges complete

### M20 - Voice Experience (complete)

- Use Home Assistant's existing Assist speech-to-text and text-to-speech pipeline.
- Use the microphone presented by the Home Assistant mobile app on the device
  named `NSPanel Upstairs` as the initial acceptance-test input.
- Route spoken Jarvis responses to the Home Assistant media-player device named
  `Loftstue Group` as the initial acceptance-test output.
- Resolve and record the exact Home Assistant device and entity identifiers
  during M20 discovery; friendly names are acceptance references, not durable
  authorization identifiers.
- Treat remote speaker routing as an explicit Home Assistant TTS output step,
  because a conversation agent returns text and does not itself choose the
  pipeline's playback device.
- Prevent duplicate speech from both the NSPanel and `Loftstue Group`.
- Give Jarvis an original, refined voice presentation with a measured
  British-inspired cadence, calm delivery, precise wording, warmth, and subtle
  dry wit.
- Do not clone a performer's voice, reproduce film dialogue, or claim to be the
  copyrighted fictional character.
- Keep spoken answers concise and natural, with voice-friendly clarification
  and confirmation flows.
- M20.1 Voice topology and validated configuration complete
- M20.2 Source-device-bound external TTS routing complete
- M20.3 Spoken response formatting and local fallback complete
- M20.4 Session-bound natural voice confirmations complete
- M20.5 Original voice-character guidance complete
- M20.6 Automated acceptance, packaging, and release complete

### M21 - Reflective Learning and Companion Continuity (complete)

- Develop ongoing reflection across conversations using bounded, inspectable
  memories.
- Connect related facts, preferences, people, rooms, routines, and projects.
- Track uncertainty, contradictions, unresolved topics, and useful follow-ups.
- Gradually refine interaction style from explicit feedback.
- Consolidate duplicate memories without retaining deleted history.
- Keep all learned information inspectable, correctable, and permanently
  deletable by the user.
- Never autonomously rewrite Jarvis code, expand permissions, or change privacy
  and safety policy.
- Present continuity and self-reflection honestly without claiming
  consciousness or subjective awareness.
- M21.1 Reflection contracts and durable storage complete
- M21.2 Related-context linking and bounded retrieval complete
- M21.3 Uncertainty, contradiction, and follow-up tracking complete
- M21.4 Explicit interaction-style learning complete
- M21.5 Consolidation and natural user controls complete
- M21.6 Migration, runtime integration, acceptance tests, and release complete

## EPIC 19 - Persistent Conversation Memory and Character

- M19.1 Durable Conversation Identity and Short-Term Retention complete
- M19.2 Repeated User Context Promotion complete
- M19.3 Durable Long-Term Memory Upgrade Safety complete
- M19.4 Natural Memory Controls complete
- M19.5 Central Jarvis Character Profile complete
- M19.6 Acceptance, Packaging, and Release complete

## EPIC 18 – Home Status Responses

- M18 Bounded Area and Group Status ✓

## EPIC 17 – Home Understanding

- M17 Natural Names, Areas, and Groups complete

## EPIC 16 – Immediate All-Device Control

- M16.1 Durable All-Device Policy ✓
- M16.2 Immediate Device Action Gateway ✓
- M16.3 Audit, Exclusion, and Acceptance ✓

## EPIC 15 – Everyday Assist Experience

- M15.1 Assist Command Routing ✓
- M15.2 Clear Outcomes and Recovery ✓
- M15.3 Privacy-Bounded Confirmed Action Audit ✓
- M15.4 Operational Diagnostics and Acceptance ✓

## EPIC 0 – Foundation (Active)

- Documentation
- Architecture
- Development workflow

## EPIC 1 – Context

- M1.1 Request Classification ✅
- M1.2 Capability Registry ✅
- M1.3 Request Context ✅
- M1.4 Context Assembly ✅
- M1.5 Execution Pipeline ✅
- M1.6 Response Pipeline ✅

## Orchestration Foundation

- Request Identity & Lifecycle ✅

## EPIC 2 – Memory

- M2.1 Memory Contracts and Policy ✅
- M2.2 In-Memory Store ✅
- M2.3 Explicit Memory Writing ✅
- M2.4 Memory Retrieval ✅
- M2.5 Context Assembly Integration âœ…
- M2.6 Memory Management and Deletion âœ…

## EPIC 3 – Knowledge

- M3.1 Knowledge Contracts and Boundaries ✅
- M3.2 In-Memory Knowledge Store ✅
- M3.3 Explicit Knowledge Approval and Writing ✅
- M3.4 Knowledge Retrieval ✅
- M3.5 Knowledge Context Integration ✅

## EPIC 4 – Event Timeline

- M8.1 Event Timeline Contracts and Privacy Policy ✅
- M8.2 Ephemeral Timeline Store ✅
- M8.3 Home Assistant Event Subscription ✅
- M8.4 Timeline Retrieval and Console Context ✅
- M8.5 Safe Acceptance and Operational Documentation ✅

## EPIC 5 – Conversation Pipeline

Conversation Management

- M5.1 Safe Read-Only Assistant Slice ✅
- M5.5 Console Request Loop ✅
- M5.6 Provider Response Hardening ✅
- M5.7 Read-Only Entity Resolution ✅
- M5.8 General Home Assistant Capability Gateway ✅
- M5.9 Console Action Confirmation Flow ✅
- M5.10 Model Action Proposal Schema ✅
- M5.11 Action Authorization Configuration ✅
- M5.12 End-to-End Confirmed Action Flow ✅
- M5.13 Assistant Runtime Review and Commit ✅

## EPIC 6 – Learning

Learning & Adaptation

- M6.1 Learning Foundations ✅
- M6.2–M6.6 Explicit Learning Review ✅

## EPIC 7 – Runtime Integration and Acceptance

- M7.1 Bounded Memory and Knowledge Runtime Context ✅
- M7.2 Confirmed Action Gateway Runtime Composition ✅
- M7.3 Home Assistant Authorization Configuration Validation ✅
- M7.4 Safe Home Assistant Acceptance Test ✅
- M7.5 Conversation Quality ✅
- M7.6 Operational Readiness ✅

## EPIC 9 – Durable Storage and Restart Resilience

- M9.1 SQLite Storage Foundation ✅
- M9.2 Durable Explicit Memory ✅
- M9.3 Durable Curated Knowledge ✅
- M9.4 Runtime Restart Resilience ✅
- M9.5 Privacy and Operational Acceptance ✅

## EPIC 10 – Explicit Memory and Knowledge Experience

- M10.1 Console Command Grammar ✅
- M10.2 Explicit Memory Management ✅
- M10.3 Curated Knowledge Management ✅
- M10.4 Durable Runtime Wiring ✅
- M10.5 Privacy Acceptance and Documentation ✅

## EPIC 11 – Home Assistant Capability Context

- M11.1 Bounded Capability Snapshot ✅
- M11.2 Model Context Integration ✅
- M11.3 Entity and Service Clarification ✅
- M11.4 Service and Alias Validation ✅
- M11.5 Confirmed Action Acceptance ✅

## EPIC 12 – Home Assistant Access Enrollment

- M12.1 Discovery and Enrollment Boundary ✅
- M12.2 Read and Action Enrollment ✅
- M12.3 Alias Management ✅
- M12.4 Risk Classification Validation ✅
- M12.5 Operational Documentation and Tests ✅
## M28 - Hybrid Research and Cost-Aware Intelligence (complete)

- Local SearXNG search, bounded public-page retrieval, citations, tiered OpenAI
  synthesis, persistent budget controls, and an Ollama-ready provider boundary.

## M36 - Contextual Jarvis Personality (complete)

- Unified configurable British-English presentation, local-first identity context,
  protected exact responses, and inspectable per-conversation style diagnostics.

## M37 - Approved Jarvis Voice Integration (complete)

- Bundled approved v5 Chatterbox reference, calibrated crisp staccato finishing,
  safe legacy-default migration, and retained Kokoro/Piper fallbacks.
