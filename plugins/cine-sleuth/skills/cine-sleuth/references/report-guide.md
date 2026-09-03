# Host-Agent Report Guide

The assembled evidence is not a finished interpretation. The host agent should reason across chunks and author the report itself.

## Merge Invariants

- Use source media metadata as authoritative for duration and frame rate.
- Use script-generated global timestamps, not model arithmetic.
- A technical chunk boundary never creates a scene or shot by itself.
- Join a cut sentence only when overlap evidence or adjacent wording supports the join.
- Merge scene candidates when setting, time, characters, action, and sound remain continuous.
- Keep distinct repeated lines when their source times do not overlap.
- Keep observed facts separate from interpretations and retain uncertainty.
- If a source range lacks evidence, identify the gap instead of inventing content.

## Default Deliverable

Adapt depth to the user's request. A full 拉片 normally contains:

1. Source facts: duration, aspect ratio, frame rate, language, and content type.
2. Verbatim transcript with global timecodes and speaker labels.
3. Physical scene list with time ranges, setting, characters, action, and sound.
4. Shot table with time ranges, shot size, angle, movement, transition, visible text, narrative function, and one directly usable video-generation prompt for every shot.
5. Content or rhetorical sections, explicitly distinguished from physical scenes.
6. Narrative structure, pacing, visual system, sound design, and notable techniques.
7. Uncertain or unreadable items.

For transcript-only requests, omit interpretive sections. For short-form or advertising analysis, emphasize the hook, information density, retention devices, proof, emotional turn, and CTA.

## Per-shot Video-generation Prompts

- Preserve one prompt for every reported shot; do not collapse several visually different shots into one prompt.
- Keep prompts faithful to observed evidence while turning the evidence into fluent generation instructions.
- Include subject, action, setting, composition or shot size, camera angle, camera movement, lighting, color, visual style, and temporal motion when those details are visible.
- Preserve character and environment continuity across adjacent shots. If continuity cannot be confirmed, state only what is visible.
- Do not include timecodes, analysis labels, model names, unsupported identities, or explanations such as “this shot shows”.
- If the user asks only for transcript extraction, prompts may be omitted; otherwise they are part of the default full and shot-breakdown deliverables.
