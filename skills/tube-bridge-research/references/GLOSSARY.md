# Glossary

**Agent Plugin** — the portable package boundary that co-locates manifest, MCP configuration, skills, runtime, and supporting resources.

**Adversary gate** — an independent method review that attacks frame, evidence, hypotheses, feasibility, and confidence before synthesis. PASS means fit to present, not guaranteed truth.

**ASR** — automatically generated speech recognition subtitles. Useful but prone to errors in names, numbers, punctuation, and speaker boundaries.

**Corpus** — a named local collection of selected video transcript representations used for repeated search.

**Corpus v2** — the frozen SQLite dual-representation storage contract: immutable transcript versions, versioned temporal projections, and rebuildable lexical/dense indexes. It is not yet released runtime behavior.

**Claim class** — one of OBSERVATION, FACT, SOURCE-CLAIM, INFERENCE, or UNKNOWN, used to prevent testimony and interpretation from silently becoming fact.

**Dense retrieval** — semantic retrieval using vector embeddings. Good for paraphrases; weaker for exact names, numbers, and quotations.

**Derived projection** — rebuildable data produced from a preserved source transcript, such as normalized units, chunks, summaries, hierarchy, embeddings, or relations.

**Distinguishing prediction** — an expected observation that differs across competing hypotheses and can therefore change their relative standing.

**Embedding** — a numeric representation used to rank semantic similarity. It is an index artifact, not evidence or probability.

**Evidence span** — a bounded source range identified by video, subtitle track provenance, and start/end time.

**FRAME-LOCK** — the explicit object, current question, process/verdict register, and research boundary preserved throughout an investigation.

**Lexical retrieval** — token or text matching used for exact terms, phrases, names, and numbers.

**Manual track** — subtitles supplied or edited by a human process. Manual status does not prove that the track is the video's original language.

**Processed node** — a future addressable unit in a derived working projection, linked to source segments and a time range.

**Provenance** — information needed to identify where data came from and how it was selected or generated, including source, language, track type, hashes, versions, configuration, model, and timestamps.

**Source lineage** — the origin and downstream repetition path of a claim. It reveals when several videos are not independent confirmations.

**SOURCE-CLAIM** — an assertion made by a speaker, channel, report, or institution. It is evidence of that source's position until independently established as a bounded FACT.

**Source transcript** — the complete ordered subtitle segments with original text and timing for one selected track. This is the canonical transcript evidence layer.

**Temporal hierarchy** — a structure whose within-video nodes preserve chronological, contiguous source ranges at multiple levels such as utterance, topic, chapter, and video.

**Track selection** — the explicit choice of a subtitle language and manual/generated variant. It is part of source capture, not a cosmetic display preference.

**UNKNOWN** — a named gap that available evidence has not resolved. It must not be filled with plausible narrative.

**Working projection** — a compact, versioned representation used for overview, navigation, and retrieval while remaining rebuildable from source data.
