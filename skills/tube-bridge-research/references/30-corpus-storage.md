# Corpus v2 storage contract

**Status:** accepted and frozen for implementation; not released runtime behavior.<br>
**Physical schema:** [`../assets/contracts/corpus-v2-schema.sql`](../assets/contracts/corpus-v2-schema.sql)<br>
**Frozen tests:** `tests/test_corpus_v2_storage_contract.py`

Corpus v2 uses one durable SQLite file at `${TUBE_BRIDGE_CACHE}/corpus-v2.db` with `PRAGMA user_version = 2`. JSON directories are not primary storage. The current flat `corpus.db` is not altered in place.

## Frozen decision

| Concern | Decision |
|---|---|
| Durable engine | SQLite, WAL, foreign keys, JSON1, FTS5 |
| Durable file | `corpus-v2.db` |
| Disposable cache | `cache.db`; never the Corpus v2 source of truth |
| Source | immutable selected-track content plus ordered source segments |
| Processing | immutable contiguous temporal projection: `video / chapter / topic / passage` |
| Search | one lexical and one dense snapshot per corpus generation |
| Activation | one atomic `active_generation_id` pointer switch |
| Dense format | sqlite-vec 0.1.9, float32, cosine distance, L2-normalized vectors |
| Time | media offsets and wall-clock timestamps are separate integer milliseconds |
| Hashing | lowercase SHA-256 over canonical JSON |
| Failure | failed builds never replace the active generation |
| Migration | resumable side-by-side v1 snapshot, item ledger, explicit read-authority cutover |
| Retention | no automatic v2 GC |

## Authority and cohort model

Data has three authority layers:

```text
transcript_versions + source_segments        durable evidence source
                ↓ exact identity
projection_versions + projection_nodes       rebuildable working representation
                ↓ generation membership
lexical index + dense index                  rebuildable search accelerators
```

A **corpus generation** is the complete immutable read cohort:

```text
generation
├── exact source/projection member for every video
├── exactly one lexical index over that same projection set
└── exactly one dense index over that same projection set
```

`corpora.active_generation_id` is the only runtime read pointer. There are no independently active projection, lexical, or dense pointers. Hybrid retrieval therefore cannot combine incompatible snapshots.

Generated summaries, normalized text, relations, FTS rows, vectors, and scores are derived. They must resolve to source segment ranges and must not be presented as source evidence.

## SQLite contract

Runtime opens the database with:

```sql
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA user_version = 2;
```

The SQL file is executable without sqlite-vec so metadata and lexical contracts can be inspected. Dense build/search additionally loads exactly the release-pinned sqlite-vec 0.1.9 extension.

All build material is computed before taking the write lock. Final persistence, validation transitions, vector-table creation, and generation activation run inside one `BEGIN IMMEDIATE` transaction. SQLite DDL is transactional, so a crash rolls back dynamic vector tables as well as relational rows.

Runtime exposes persistence through this frozen boundary:

```python
CorpusV2Store.open(path) -> CorpusV2Store
store.add_or_refresh(corpus_id, source_record, force_reembed=False) -> generation_id
store.search(corpus_id, query, top_k) -> source-linked results
store.delete_corpus(corpus_id) -> None
store.gc_generation(corpus_id, generation_id) -> None
store.gc_source(transcript_version_id) -> None
store.migrate_v1(v1_path) -> migration_run_id
store.cutover(migration_run_id) -> None
```

Methods own transactions; callers do not receive a writable connection. Before any write, every store connection registers four mandatory SQLite UDFs used directly by READY triggers:

```text
tube_validate_source(transcript_version_id) -> validation_sha256
tube_validate_projection(projection_version_id) -> 1 or error
tube_validate_index(index_version_id) -> validation_sha256
tube_validate_generation(corpus_id, generation_id) -> 1 or error
```

The frozen test file is the executable reference implementation. The production functions must perform the same canonical hash, build-key, document, vector, and membership comparisons with explicit exceptions—not optimization-removable Python assertions. Missing functions, exceptions, or unequal returns abort the READY transition; supplying an arbitrary validation hash cannot pass.

Every connection also installs the tested authorizer callback. Outside a scoped build/GC context it denies INSERT/UPDATE/DELETE/CREATE-VTABLE/DROP-VTABLE for both the primary `^vec_[0-9a-f]{32}$` table and sqlite-vec shadow tables matching `^vec_[0-9a-f]{32}_.*$`. On database open and before serving search, the store revalidates the active generation's membership, document manifests, vec0 table definitions, vector row sets, and vector manifests. A mismatch fails closed and requires rebuild; it is never silently accepted.

## IDs

Generated IDs use lowercase UUIDv4 hex without dashes:

| Entity | Format |
|---|---|
| transcript | `trv_<64-char-source-sha256>` |
| source segment | `seg_<source-sha256>_<8-digit-zero-based-ordinal>` |
| fetch | `fetch_<32-hex>` |
| projection | `prj_<32-hex>` |
| node | `node_<32-hex>` |
| relation | `rel_<32-hex>` |
| generation | `gen_<32-hex>` |
| index | `idx_<32-hex>` |
| migration run | `mig_<32-hex>` |

Generated table/row IDs are not derived from user input. Existing `corpus_id` validation remains restricted to `^[A-Za-z0-9_-]{1,128}$`.

## Time

Two domains are never mixed:

- source/node `start_ms` and `end_ms`: integer milliseconds from video start;
- `created_at_ms`, `fetched_at_ms`, `completed_at_ms`, and cutover timestamps: Unix epoch integer milliseconds.

Convert non-negative transcript seconds using:

```python
(Decimal(str(seconds)) * Decimal(1000)).quantize(
    Decimal("1"), rounding=ROUND_HALF_UP
)
```

For a segment, calculate `start_ms` from `start` and `end_ms` from `start + duration`. Original provider order is authoritative when times tie. The frozen tests include half-up boundary vectors.

## Canonical JSON and hashes

Canonical JSON bytes are:

```python
json.dumps(
    value,
    ensure_ascii=False,
    sort_keys=True,
    separators=(",", ":"),
).encode("utf-8")
```

Do not normalize Unicode, trim source strings, rewrite whitespace, or include floats in a source-hash envelope.

### Source hash

The exact envelope is:

```json
{
  "schema": "tube-bridge.transcript-source.v2",
  "video_id": "video123",
  "selected_language": "en",
  "track_kind": "manual|generated",
  "segments": [
    {"ordinal": 0, "start_ms": 0, "end_ms": 1250, "text": "exact fetched text"}
  ]
}
```

`source_sha256` is SHA-256 of those canonical bytes. `transcript_version_id` must equal `trv_` plus that hash.

Provider identity, requested language, provider track ID, translatability, spoken-language assessment, translation metadata, fetch warnings, and fetch time are **observation provenance**, not content identity. They are typed fields in `transcript_fetches` and are deliberately excluded from the source hash. Identical content observed through two providers is one content version with two fetch observations.

### Configuration and build keys

Configuration hashes use the same canonical JSON rule.

Projection build key:

```json
{
  "schema": "tube-bridge.projection-build.v2",
  "source_sha256": "...",
  "processor_name": "...",
  "processor_version": "...",
  "model_name": null,
  "model_version": null,
  "processing_config_sha256": "..."
}
```

The source manifest is a list sorted by binary UTF-8 `video_id`:

```json
[
  {
    "video_id": "...",
    "transcript_version_id": "...",
    "source_sha256": "...",
    "projection_version_id": "..."
  }
]
```

`force_run_id` is a typed nullable field on the generation row and is included verbatim in the build envelope.

Generation build key:

```json
{
  "schema": "tube-bridge.corpus-generation.v2",
  "source_manifest_sha256": "...",
  "lexical_config_sha256": "...",
  "dense_config_sha256": "...",
  "force_run_id": null
}
```

Normal operation uses `force_run_id=null`. `force_reembed=true` supplies a fresh UUIDv4 string, producing a new generation and dense snapshot without mutating source or projection content.

Index build key:

```json
{
  "schema": "tube-bridge.index-build.v2",
  "generation_id": "...",
  "index_kind": "lexical|dense",
  "config_sha256": "..."
}
```

Partial unique indexes reject concurrent equivalent BUILDING/READY projections or generations. FAILED and RETIRED records do not block a new attempt. Frozen tests include independent known SHA-256 vectors for projection, normal/forced generation, and index envelopes; fixture-generated keys alone are not the oracle.

## Layer 1 — immutable source

### `transcript_versions`

A transcript version is inserted BUILDING, receives its complete ordered segments, passes source validation, and then becomes READY. Only READY sources may be used by projections. The validator recomputes the exact source envelope/hash, checks ID equality, segment count, dense ordinals, first/last range, and monotonic starts, then stores `validated_at_ms` plus the SHA-256 of:

```json
{
  "schema": "tube-bridge.source-validation.v2",
  "transcript_version_id": "...",
  "source_sha256": "...",
  "checks": "pass"
}
```

This table contains only stable content identity:

- video ID;
- actual selected language;
- manual/generated track kind;
- source hash and schema version;
- segment count and media range.

### `transcript_fetches`

Every live observation records provider, provider track ID when available, requested language, language name, track properties, selection-policy version/reason, fetch time, warnings, and provider metadata.

A cache observation uses `retrieval_mode=cache` and must reference a LIVE `origin_fetch_id` for the same transcript version. Cache-to-cache chains and cross-content origins are rejected. A cache hit never impersonates a new network fetch. Fetch rows are append-only while their source exists.

The `fetch_id` stored in a generation member identifies the observation whose bytes were canonicalized for that member. It is provenance, not generation identity, and is excluded from source-manifest/build hashes. A later identical fetch appends provenance but does not invalidate or mutate an existing generation.

### `source_segments`

Each ordered row stores:

```text
transcript_version_id
source_sha256
segment_ordinal
segment_id
start_ms
end_ms
text_original
```

`text_original` is exact fetched text. Segments may be inserted only while their transcript is BUILDING. After READY, source rows cannot be appended or updated, and direct deletion of one fetch or segment is rejected while its transcript parent exists. Explicit source GC deletes one unreferenced `transcript_version`; only that parent deletion may cascade its complete fetch and segment set as a unit.

## Layer 2 — projection

A projection is bound through composite foreign keys to one corpus, video, transcript version, and matching source hash. It is inserted BUILDING, validated, then transitions to READY. READY projection identity, nodes, and relations cannot be updated or individually deleted; whole-artifact cascade during explicit GC is the only deletion path. A changed source, processor, model, or configuration creates a new version.

### Frozen hierarchy

```text
video                     exactly one root
├── chapter               optional, parent video
│   └── topic             optional, parent chapter
│       └── passage       mandatory leaf
├── topic                 allowed when chapters are unjustified
└── passage               allowed when both higher levels are unjustified
```

For any parent, children use one node kind only; levels are not mixed under the same parent. Sibling ordinals are dense `0..n-1` and define previous/next navigation. Navigation is derived from parent plus ordinal and is not stored as duplicate relation rows.

Nodes are inserted once in parent-before-child order and cannot be updated or individually deleted even during BUILDING; processing computes final boundaries before persistence. Whole-projection cascade is the only deletion path. Before READY, the schema guard independently re-verifies:

1. exactly one video root;
2. at least one passage;
3. every node range resolves to real first/last source segments;
4. node times equal those segment boundaries;
5. passages partition every source segment exactly once without gaps or overlap;
6. child ranges remain inside parent ranges;
7. parent-child kinds follow the frozen hierarchy;
8. only passages are leaves and passages have no children;
9. sibling kind is uniform and sibling ordinals are dense.

Chapter/topic boundaries may be absent. The processor must not fabricate levels merely to fill the tree.

### Derived node fields

- `normalized_text`: derived text; nullable where unnecessary.
- `title`: navigation label, not a quotation by default.
- `summary_text`: generated/algorithmic summary, never replacement evidence.
- `keywords_json`: JSON array of derived terms.
- `confidence_label`: `observed`, `low`, `medium`, `high`, or `unknown`.
- `provenance_json`: JSON object identifying processing stage, processor/model, configuration hash, and source-range basis.

Confidence labels describe a derived boundary or artifact, not calibrated truth probability.

### Relations

Schema v2 allows only:

```text
supports, example, contrast, contradicts, elaborates, similar
```

Within-video hierarchy remains contiguous. Non-contiguous and cross-video associations live only in the derived relation table with explicit provenance.

## Layer 3 — lexical and dense indexes

Every index snapshots the projection set of exactly one generation. Composite foreign keys prevent documents from another corpus, generation, or unlisted projection from entering it. READY transition requires index membership to equal generation membership. READY generation members, index members, and search documents are immutable; individual update/delete is rejected while the owning generation/index exists. Explicit whole-generation/index GC provides the bounded deletion path.

### Search-document materialization

The exact source-span assembly is:

```python
"\n".join(segment.text_original for segment in inclusive_source_range)
```

Do not trim, deduplicate overlapping caption text, or replace internal newlines. A normalized document is emitted only when its UTF-8 text differs byte-for-byte from source-span text.

`document_id` is `doc_<node-uuid-hex>_<text_role>`. The document manifest is sorted by `document_id`; each entry contains `document_id`, projection/node IDs, text role, start/end milliseconds, and lowercase SHA-256 of exact UTF-8 document text. Its canonical JSON SHA-256 is persisted as `document_manifest_sha256`.

Lexical snapshot documents:

- one `source_span` for every passage;
- one `normalized` document when different;
- one `title` for every non-empty title;
- one `summary` for every non-empty video/chapter/topic summary.

Dense snapshot documents:

- exactly one passage document: `normalized` when present and different, otherwise `source_span`;
- one `summary` for every non-empty video/chapter/topic summary;
- titles are not embedded separately in baseline v2.

### Lexical physical format

FTS5 uses the external-content `search_documents_fts` table with:

```text
tokenizer = unicode61
content = search_documents
content_rowid = row_id
```

Only documents belonging to a lexical index are inserted into FTS. Query results join FTS row ID to `search_documents`, node, projection, and source span.

### Dense physical format

Baseline compatibility is frozen to sqlite-vec 0.1.9. For dense index `idx_<32hex>` and dimension `D`, validate the generated table name against `^vec_[0-9a-f]{32}$` and create exactly:

```sql
CREATE VIRTUAL TABLE vec_<32hex>
USING vec0(embedding float[D] distance_metric=cosine);
```

Embedding procedure:

1. obtain the model output in index document order;
2. reject wrong dimension, NaN, infinity, or zero norm;
3. L2-normalize in float64 arithmetic;
4. cast each component to float32;
5. store the float32 vector;
6. normalize query vectors identically.

`search_documents.row_id` is the vec0 row ID. The vector manifest is sorted by `document_id`; each entry contains `document_id` and SHA-256 of the stored little-endian float32 vector bytes. Its canonical JSON SHA-256 is persisted as `vector_manifest_sha256`.

`index_versions` has typed `distance_metric`, `vector_dtype`, `l2_normalized`, `sqlite_vec_version`, model/version, dimension, and table-name fields in addition to canonical config JSON. Before dense READY, validation requires:

- table SQL matches the frozen template and dimension;
- vector row-ID set exactly equals eligible dense-document row-ID set;
- no missing or extra vectors;
- every vector has dimension `D`, finite float32 values, and L2 norm within `1e-5` of 1;
- embedding model, immutable model version/revision, dimension, metric, dtype, normalization flag, and sqlite-vec version are present in `config_json` and typed index columns.

Dense build, vector insertion, validation, and status transition occur in one transaction. The validator persists `validated_at_ms` and the SHA-256 of this canonical report:

```json
{
  "schema": "tube-bridge.index-validation.v2",
  "index_version_id": "...",
  "document_manifest_sha256": "...",
  "vector_manifest_sha256": "...|null",
  "checks": "pass"
}
```

READY requires that timestamp/hash. On error, rollback removes the dynamic table. Explicit index/generation GC drops the validated table name before deleting its metadata.

## Corpus generation build and activation

To add or refresh one video:

1. read the current active generation, or an empty member set;
2. deterministically select and fetch the subtitle track;
3. build/reuse immutable source and projection versions;
4. form the desired full source manifest by replacing that video entry;
5. compute lexical/dense configurations and generation build key;
6. if the active generation has the same build key, return `already_indexed`;
7. compute projection artifacts, search documents, and embeddings outside the write lock;
8. acquire `BEGIN IMMEDIATE` and re-read the active generation;
9. if another writer already activated the desired build key, return its result;
10. insert BUILDING projection/generation/index rows and their children;
11. validate projections, both indexes, and exact membership equality;
12. transition projection and indexes to READY, then generation to READY;
13. atomically switch `corpora.active_generation_id`;
14. retire the previous generation, its indexes, and projections not reused by the new generation;
15. commit.

A failed rebuild or transaction leaves the old active generation unchanged. A bounded FAILED record may be written in a separate short transaction after rollback. Failed rows never become active.

Concurrent writers are serialized at step 8. Build-key uniqueness and the mandatory re-read make add/refresh idempotent.

## Delete and explicit GC

No automatic garbage collection runs in v2.

### Delete corpus

One `BEGIN IMMEDIATE` transaction:

1. validate and collect all dense `vector_table_name` values for the corpus;
2. set `active_generation_id=NULL`;
3. drop every collected vec0 table;
4. delete the corpus, cascading generation, index, search-document, relation, projection, and membership rows;
5. rebuild FTS external content with `INSERT INTO search_documents_fts(search_documents_fts) VALUES('rebuild')`;
6. commit.

Any invalid vector table name aborts before SQL interpolation. A failure rolls back both relational and DDL changes.

### GC inactive generation

GC refuses the active generation. Individual `index_versions` deletion is blocked while its generation exists. GC first drops that generation's validated vec0 table; a schema guard refuses generation deletion while the table still exists. It then deletes the retired generation, deletes now-unreferenced projections as whole artifacts, rebuilds FTS, and commits. Cross-projection relations cascade when either endpoint projection is removed; individual relation deletion remains blocked while both endpoint projections exist. Projections still referenced by another generation remain protected by foreign keys.

### GC source

A source is collectible only when no generation member or projection references its transcript version. Deleting that `transcript_version` cascades its source segments and all owned live/cache fetch observations. `transcript_fetches` therefore remain append-only during source retention but are not permanent tombstones after explicit source GC.

## Side-by-side v1 migration

Migration never treats current overlapping chunks as source:

```text
corpus.db       current v1 database, retained unchanged
corpus-v2.db    new database and migration ledger
```

Current `corpus_chunks` are derived 80/20 windows. They cannot reconstruct original segment boundaries, ordering, selected track identity, or complete source text and must not be promoted.

### Durable migration run

1. checkpoint v1 WAL;
2. create `${TUBE_BRIDGE_CACHE}/migration/v1-<migration_run_id>.db` using SQLite backup API;
3. SHA-256 the closed snapshot and persist path/hash in `migration_runs`;
4. enumerate every v1 `corpus_added_videos` row into `migration_items` as PENDING;
5. process each item in its own transaction and persist attempts/status;
6. resume by selecting PENDING or BLOCKED items from the same run.

A legacy cache transcript is importable only when its cache key was an explicit language, returned language and manual/generated kind are present, all ordered segments are complete, and timestamps are valid. Legacy `__any__` rows are never trusted because the old selector may have chosen an unintended dub; refetch them with the corrected deterministic selection policy.

Item outcomes:

- `migrated`: validated v2 generation recorded, containing this exact `video_id`;
- `blocked`: neither admissible cache import nor refetch succeeded;
- `skipped`: explicit operator decision with reason;
- `pending`: not completed or retry requested.

A run becomes READY only when no item is PENDING or BLOCKED. `migration_items` and target generation IDs are the durable equivalence record.

### Cutover and recovery

`corpus_runtime_state.read_authority` begins as `v1`. Its singleton row cannot be deleted or replaced. One transaction changes it to `v2` only for a READY migration run with a non-null cutover time, no PENDING/BLOCKED items, and every MIGRATED item's target generation both READY and active in its target corpus; the run becomes CUTOVER. While v2 is authoritative, the active run, cutover time, migration run, and its item ledger are immutable. New runtime reads and writes only v2.

Runtime cutover is deliberately one-way: `v2 → v1` is always rejected, even before the first v2 mutation. This removes any false promise of lossless rollback after an unenumerated child write. The original v1 database and snapshot remain untouched as disaster-recovery evidence, but restoring them is an explicit offline operator action with acknowledged loss of later v2 state—not a runtime authority switch.

SQLite triggers append immutable `v2_mutations` rows for top-level and artifact changes after cutover. The ledger supports audit and forward recovery; it is not used to reopen v1 rollback. Ledger rows cannot be updated or deleted.

## Current runtime boundary

Released `corpus.py` still writes flat 80-second windows with 20-second overlap to `corpus.db` and one sqlite-vec table per corpus. It has no durable transcript source, temporal projection, FTS index, corpus generation, migration ledger, or atomic hybrid cohort. This frozen contract describes the implementation target, not current behavior.
