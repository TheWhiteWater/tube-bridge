# Worked example: one-video source capture

**Status:** Synthetic example. Identifiers and statements are invented to demonstrate method, not to assert real-world facts.

## Question

> What limitation does the presenter claim for the prototype, and does the video establish that the limitation exists in production?

## FRAME-LOCK

- **Object:** claims made in one selected prototype demonstration video
- **Question:** presenter claim versus independently established production fact
- **Register:** verdict
- **Boundary:** English subtitle track, full video, no external sources available in this run

## Capture

`youtube_get_available_languages` returns:

| Language | Track |
|---|---|
| `ar` | manual |
| `en` | generated |

The video's metadata and spoken presentation are English. The v1.1.0 default selector would remain in the English ASR family rather than crossing to the Arabic manual dub, but the agent still requests the intended language explicitly for provenance:

```text
youtube_get_transcript(url="demo-video-A", lang="en", with_timestamps=true)
```

The response reports `language=en`, `is_generated=true`.

## Inventory

At `[12:40–12:57]`, the transcript says:

> “The current prototype overheats after roughly forty minutes under continuous load.”

Classification:

- **OBSERVATION:** the selected English generated track renders this wording at the recorded span.
- **FACT about the retrieval record:** tube-bridge returned `language=en`, `is_generated=true`, and the recorded text at that timestamp.
- **Probable semantic content:** because this is a same-language track and the sentence is coherent in context, the presenter likely communicated this meaning.
- **Probable wording:** the presenter may have used similar words, but generated ASR has not been checked against audio.
- **SOURCE-CLAIM:** the track attributes to the presenter a claim that the current prototype overheats after roughly forty minutes under continuous load.
- **INFERENCE:** production units may inherit the limitation.
- **UNKNOWN:** exact spoken wording, test conditions, measurement logs, production design changes, and independent reproduction.

## Correct synthesis

> At 12:40, the selected English generated subtitle track renders the presenter as saying that the prototype overheats after roughly forty minutes of continuous load. The current tools did not verify exact wording against audio, and no test data or independent production evidence was examined. Confidence is high about the subtitle rendering, medium that it captures the probable semantic content, lower for exact wording, and low about production behavior.

## Incorrect synthesis

> The product overheats after forty minutes.

The incorrect version silently promotes a generated subtitle rendering to exact speech, then promotes the resulting SOURCE-CLAIM to FACT and drops the prototype/production boundary.
