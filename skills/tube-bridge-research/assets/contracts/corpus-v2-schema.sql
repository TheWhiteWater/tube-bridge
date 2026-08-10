-- tube-bridge Corpus v2 persisted-format contract.
-- Requires SQLite with FTS5 and JSON1. Dense snapshots additionally require
-- sqlite-vec 0.1.9 and the dynamic vec0 table template frozen in the contract.

PRAGMA foreign_keys = ON;
PRAGMA user_version = 2;
PRAGMA application_id = 1413633586; -- TBV2

CREATE TABLE corpus_schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
) STRICT;

INSERT INTO corpus_schema_meta (key, value) VALUES
    ('storage_format', 'tube-bridge-corpus-v2'),
    ('storage_schema_version', '2'),
    ('media_time_unit', 'integer_milliseconds_from_video_start'),
    ('wall_clock_unit', 'integer_unix_epoch_milliseconds'),
    ('hash_algorithm', 'sha256_canonical_json'),
    ('dense_extension', 'sqlite-vec-0.1.9');

-- The active generation is the only read cohort. It is nullable before first
-- successful build and during explicit corpus deletion.
CREATE TABLE corpora (
    corpus_id TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    active_generation_id TEXT,
    created_at_ms INTEGER NOT NULL CHECK (created_at_ms >= 0),
    updated_at_ms INTEGER NOT NULL CHECK (updated_at_ms >= created_at_ms),
    FOREIGN KEY (corpus_id, active_generation_id)
        REFERENCES corpus_generations(corpus_id, generation_id)
        ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
) STRICT;

-- Content identity only. Provider and mutable track observations live in
-- transcript_fetches, allowing identical content from multiple observations.
CREATE TABLE transcript_versions (
    transcript_version_id TEXT PRIMARY KEY,
    source_sha256 TEXT NOT NULL UNIQUE
        CHECK (length(source_sha256) = 64 AND source_sha256 NOT GLOB '*[^0-9a-f]*'),
    source_schema_version INTEGER NOT NULL CHECK (source_schema_version = 2),
    video_id TEXT NOT NULL,
    selected_language TEXT NOT NULL,
    track_kind TEXT NOT NULL CHECK (track_kind IN ('manual', 'generated')),
    segment_count INTEGER NOT NULL CHECK (segment_count > 0),
    start_ms INTEGER NOT NULL CHECK (start_ms >= 0),
    end_ms INTEGER NOT NULL CHECK (end_ms >= start_ms),
    status TEXT NOT NULL CHECK (status IN ('building', 'ready')),
    validated_at_ms INTEGER,
    validation_sha256 TEXT
        CHECK (validation_sha256 IS NULL OR
            (length(validation_sha256) = 64 AND validation_sha256 NOT GLOB '*[^0-9a-f]*')),
    created_at_ms INTEGER NOT NULL CHECK (created_at_ms >= 0),
    CHECK (
        (status = 'building' AND validated_at_ms IS NULL AND validation_sha256 IS NULL)
        OR (status = 'ready' AND validated_at_ms >= created_at_ms
            AND validation_sha256 IS NOT NULL)
    ),
    CHECK (transcript_version_id = 'trv_' || source_sha256),
    UNIQUE (transcript_version_id, source_sha256),
    UNIQUE (transcript_version_id, video_id, source_sha256)
) STRICT;

-- Fetch observations are append-only while the source exists. They are deleted
-- only as owned provenance when explicit GC deletes an unreferenced source.
CREATE TABLE transcript_fetches (
    fetch_id TEXT PRIMARY KEY,
    transcript_version_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    provider_track_id TEXT,
    requested_language TEXT,
    language_name TEXT,
    is_translatable INTEGER CHECK (is_translatable IN (0, 1)),
    spoken_language TEXT,
    translation_source_language TEXT,
    selection_policy_version TEXT NOT NULL,
    selection_reason TEXT NOT NULL,
    retrieval_mode TEXT NOT NULL CHECK (retrieval_mode IN ('live', 'cache')),
    origin_fetch_id TEXT,
    fetched_at_ms INTEGER NOT NULL CHECK (fetched_at_ms >= 0),
    warnings_json TEXT NOT NULL DEFAULT '[]'
        CHECK (json_valid(warnings_json) AND json_type(warnings_json) = 'array'),
    provider_metadata_json TEXT NOT NULL DEFAULT '{}'
        CHECK (json_valid(provider_metadata_json) AND json_type(provider_metadata_json) = 'object'),
    CHECK (
        length(fetch_id) = 38 AND substr(fetch_id, 1, 6) = 'fetch_'
        AND substr(fetch_id, 7) NOT GLOB '*[^0-9a-f]*'
    ),
    CHECK (
        (retrieval_mode = 'live' AND origin_fetch_id IS NULL)
        OR (retrieval_mode = 'cache' AND origin_fetch_id IS NOT NULL)
    ),
    UNIQUE (fetch_id, transcript_version_id),
    FOREIGN KEY (transcript_version_id)
        REFERENCES transcript_versions(transcript_version_id) ON DELETE CASCADE,
    FOREIGN KEY (origin_fetch_id, transcript_version_id)
        REFERENCES transcript_fetches(fetch_id, transcript_version_id) ON DELETE CASCADE
) STRICT;

CREATE TABLE source_segments (
    transcript_version_id TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    segment_ordinal INTEGER NOT NULL CHECK (segment_ordinal >= 0),
    segment_id TEXT NOT NULL UNIQUE,
    start_ms INTEGER NOT NULL CHECK (start_ms >= 0),
    end_ms INTEGER NOT NULL CHECK (end_ms >= start_ms),
    text_original TEXT NOT NULL,
    PRIMARY KEY (transcript_version_id, segment_ordinal),
    CHECK (
        segment_id = 'seg_' || source_sha256 || '_' || printf('%08d', segment_ordinal)
    ),
    FOREIGN KEY (transcript_version_id, source_sha256)
        REFERENCES transcript_versions(transcript_version_id, source_sha256)
        ON DELETE CASCADE
) STRICT;

CREATE TABLE projection_versions (
    projection_version_id TEXT PRIMARY KEY,
    corpus_id TEXT NOT NULL,
    video_id TEXT NOT NULL,
    transcript_version_id TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    projection_schema_version INTEGER NOT NULL CHECK (projection_schema_version = 2),
    build_key_sha256 TEXT NOT NULL
        CHECK (length(build_key_sha256) = 64 AND build_key_sha256 NOT GLOB '*[^0-9a-f]*'),
    processor_name TEXT NOT NULL,
    processor_version TEXT NOT NULL,
    model_name TEXT,
    model_version TEXT,
    processing_config_json TEXT NOT NULL
        CHECK (json_valid(processing_config_json) AND json_type(processing_config_json) = 'object'),
    processing_config_sha256 TEXT NOT NULL
        CHECK (length(processing_config_sha256) = 64 AND processing_config_sha256 NOT GLOB '*[^0-9a-f]*'),
    status TEXT NOT NULL CHECK (status IN ('building', 'ready', 'failed', 'retired')),
    created_at_ms INTEGER NOT NULL CHECK (created_at_ms >= 0),
    completed_at_ms INTEGER,
    failure_reason TEXT,
    CHECK (
        length(projection_version_id) = 36
        AND substr(projection_version_id, 1, 4) = 'prj_'
        AND substr(projection_version_id, 5) NOT GLOB '*[^0-9a-f]*'
    ),
    CHECK ((model_name IS NULL) = (model_version IS NULL)),
    CHECK (
        (status = 'building' AND completed_at_ms IS NULL AND failure_reason IS NULL)
        OR (status = 'ready' AND completed_at_ms >= created_at_ms AND failure_reason IS NULL)
        OR (status = 'failed' AND completed_at_ms >= created_at_ms
            AND length(failure_reason) BETWEEN 1 AND 2000)
        OR (status = 'retired' AND completed_at_ms >= created_at_ms AND failure_reason IS NULL)
    ),
    UNIQUE (
        projection_version_id, corpus_id, video_id,
        transcript_version_id, source_sha256
    ),
    FOREIGN KEY (corpus_id) REFERENCES corpora(corpus_id) ON DELETE CASCADE,
    FOREIGN KEY (transcript_version_id, video_id, source_sha256)
        REFERENCES transcript_versions(transcript_version_id, video_id, source_sha256)
        ON DELETE RESTRICT
) STRICT;

CREATE TABLE projection_nodes (
    projection_version_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    node_kind TEXT NOT NULL CHECK (node_kind IN ('video', 'chapter', 'topic', 'passage')),
    parent_node_id TEXT,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    start_segment_ordinal INTEGER NOT NULL CHECK (start_segment_ordinal >= 0),
    end_segment_ordinal INTEGER NOT NULL CHECK (end_segment_ordinal >= start_segment_ordinal),
    start_ms INTEGER NOT NULL CHECK (start_ms >= 0),
    end_ms INTEGER NOT NULL CHECK (end_ms >= start_ms),
    title TEXT,
    normalized_text TEXT,
    summary_text TEXT,
    keywords_json TEXT NOT NULL DEFAULT '[]'
        CHECK (json_valid(keywords_json) AND json_type(keywords_json) = 'array'),
    confidence_label TEXT NOT NULL
        CHECK (confidence_label IN ('observed', 'low', 'medium', 'high', 'unknown')),
    provenance_json TEXT NOT NULL
        CHECK (json_valid(provenance_json) AND json_type(provenance_json) = 'object'),
    PRIMARY KEY (projection_version_id, node_id),
    UNIQUE (projection_version_id, parent_node_id, ordinal),
    CHECK (
        length(node_id) = 37 AND substr(node_id, 1, 5) = 'node_'
        AND substr(node_id, 6) NOT GLOB '*[^0-9a-f]*'
    ),
    CHECK (
        (node_kind = 'video' AND parent_node_id IS NULL)
        OR (node_kind <> 'video' AND parent_node_id IS NOT NULL)
    ),
    FOREIGN KEY (projection_version_id)
        REFERENCES projection_versions(projection_version_id) ON DELETE CASCADE,
    FOREIGN KEY (projection_version_id, parent_node_id)
        REFERENCES projection_nodes(projection_version_id, node_id)
        ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED
) STRICT;

CREATE TABLE projection_relations (
    relation_id TEXT PRIMARY KEY,
    from_projection_version_id TEXT NOT NULL,
    from_node_id TEXT NOT NULL,
    to_projection_version_id TEXT NOT NULL,
    to_node_id TEXT NOT NULL,
    relation_kind TEXT NOT NULL CHECK (
        relation_kind IN ('supports', 'example', 'contrast', 'contradicts', 'elaborates', 'similar')
    ),
    confidence_label TEXT NOT NULL
        CHECK (confidence_label IN ('observed', 'low', 'medium', 'high', 'unknown')),
    provenance_json TEXT NOT NULL
        CHECK (json_valid(provenance_json) AND json_type(provenance_json) = 'object'),
    created_at_ms INTEGER NOT NULL CHECK (created_at_ms >= 0),
    CHECK (
        length(relation_id) = 36 AND substr(relation_id, 1, 4) = 'rel_'
        AND substr(relation_id, 5) NOT GLOB '*[^0-9a-f]*'
    ),
    UNIQUE (
        from_projection_version_id, from_node_id,
        to_projection_version_id, to_node_id, relation_kind
    ),
    FOREIGN KEY (from_projection_version_id, from_node_id)
        REFERENCES projection_nodes(projection_version_id, node_id) ON DELETE CASCADE,
    FOREIGN KEY (to_projection_version_id, to_node_id)
        REFERENCES projection_nodes(projection_version_id, node_id) ON DELETE CASCADE
) STRICT;

-- One immutable cohort joins every selected source/projection with exactly one
-- lexical and one dense index. corpora.active_generation_id is the sole switch.
CREATE TABLE corpus_generations (
    generation_id TEXT NOT NULL,
    corpus_id TEXT NOT NULL,
    build_key_sha256 TEXT NOT NULL
        CHECK (length(build_key_sha256) = 64 AND build_key_sha256 NOT GLOB '*[^0-9a-f]*'),
    source_manifest_sha256 TEXT NOT NULL
        CHECK (length(source_manifest_sha256) = 64 AND source_manifest_sha256 NOT GLOB '*[^0-9a-f]*'),
    force_run_id TEXT,
    status TEXT NOT NULL CHECK (status IN ('building', 'ready', 'failed', 'retired')),
    created_at_ms INTEGER NOT NULL CHECK (created_at_ms >= 0),
    completed_at_ms INTEGER,
    failure_reason TEXT,
    PRIMARY KEY (corpus_id, generation_id),
    CHECK (
        length(generation_id) = 36 AND substr(generation_id, 1, 4) = 'gen_'
        AND substr(generation_id, 5) NOT GLOB '*[^0-9a-f]*'
    ),
    CHECK (force_run_id IS NULL OR
        (length(force_run_id) = 32 AND force_run_id NOT GLOB '*[^0-9a-f]*')),
    CHECK (
        (status = 'building' AND completed_at_ms IS NULL AND failure_reason IS NULL)
        OR (status = 'ready' AND completed_at_ms >= created_at_ms AND failure_reason IS NULL)
        OR (status = 'failed' AND completed_at_ms >= created_at_ms
            AND length(failure_reason) BETWEEN 1 AND 2000)
        OR (status = 'retired' AND completed_at_ms >= created_at_ms AND failure_reason IS NULL)
    ),
    FOREIGN KEY (corpus_id) REFERENCES corpora(corpus_id) ON DELETE CASCADE
) STRICT;

CREATE TABLE corpus_generation_members (
    corpus_id TEXT NOT NULL,
    generation_id TEXT NOT NULL,
    video_id TEXT NOT NULL,
    transcript_version_id TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    fetch_id TEXT NOT NULL,
    projection_version_id TEXT NOT NULL,
    PRIMARY KEY (corpus_id, generation_id, video_id),
    UNIQUE (corpus_id, generation_id, video_id, projection_version_id),
    FOREIGN KEY (corpus_id, generation_id)
        REFERENCES corpus_generations(corpus_id, generation_id) ON DELETE CASCADE,
    FOREIGN KEY (transcript_version_id, video_id, source_sha256)
        REFERENCES transcript_versions(transcript_version_id, video_id, source_sha256)
        ON DELETE RESTRICT,
    FOREIGN KEY (fetch_id, transcript_version_id)
        REFERENCES transcript_fetches(fetch_id, transcript_version_id) ON DELETE RESTRICT,
    FOREIGN KEY (
        projection_version_id, corpus_id, video_id,
        transcript_version_id, source_sha256
    ) REFERENCES projection_versions(
        projection_version_id, corpus_id, video_id,
        transcript_version_id, source_sha256
    ) ON DELETE RESTRICT
) STRICT;

CREATE TABLE index_versions (
    index_version_id TEXT PRIMARY KEY,
    corpus_id TEXT NOT NULL,
    generation_id TEXT NOT NULL,
    index_kind TEXT NOT NULL CHECK (index_kind IN ('lexical', 'dense')),
    build_key_sha256 TEXT NOT NULL
        CHECK (length(build_key_sha256) = 64 AND build_key_sha256 NOT GLOB '*[^0-9a-f]*'),
    status TEXT NOT NULL CHECK (status IN ('building', 'ready', 'failed', 'retired')),
    config_json TEXT NOT NULL
        CHECK (json_valid(config_json) AND json_type(config_json) = 'object'),
    config_sha256 TEXT NOT NULL
        CHECK (length(config_sha256) = 64 AND config_sha256 NOT GLOB '*[^0-9a-f]*'),
    document_manifest_sha256 TEXT NOT NULL
        CHECK (length(document_manifest_sha256) = 64
            AND document_manifest_sha256 NOT GLOB '*[^0-9a-f]*'),
    vector_manifest_sha256 TEXT,
    embedding_model TEXT,
    embedding_model_version TEXT,
    embedding_dimension INTEGER,
    distance_metric TEXT,
    vector_dtype TEXT,
    l2_normalized INTEGER CHECK (l2_normalized IN (0, 1)),
    sqlite_vec_version TEXT,
    vector_table_name TEXT UNIQUE,
    validated_at_ms INTEGER,
    validation_sha256 TEXT
        CHECK (validation_sha256 IS NULL OR
            (length(validation_sha256) = 64 AND validation_sha256 NOT GLOB '*[^0-9a-f]*')),
    created_at_ms INTEGER NOT NULL CHECK (created_at_ms >= 0),
    completed_at_ms INTEGER,
    failure_reason TEXT,
    CHECK (
        length(index_version_id) = 36 AND substr(index_version_id, 1, 4) = 'idx_'
        AND substr(index_version_id, 5) NOT GLOB '*[^0-9a-f]*'
    ),
    CHECK (
        (status = 'building' AND completed_at_ms IS NULL AND failure_reason IS NULL
            AND validated_at_ms IS NULL AND validation_sha256 IS NULL)
        OR (status = 'ready' AND completed_at_ms >= created_at_ms AND failure_reason IS NULL
            AND validated_at_ms BETWEEN created_at_ms AND completed_at_ms
            AND validation_sha256 IS NOT NULL)
        OR (status = 'failed' AND completed_at_ms >= created_at_ms
            AND length(failure_reason) BETWEEN 1 AND 2000)
        OR (status = 'retired' AND completed_at_ms >= created_at_ms AND failure_reason IS NULL
            AND validated_at_ms IS NOT NULL AND validation_sha256 IS NOT NULL)
    ),
    CHECK (
        (index_kind = 'lexical' AND vector_manifest_sha256 IS NULL
            AND embedding_model IS NULL AND embedding_model_version IS NULL
            AND embedding_dimension IS NULL AND distance_metric IS NULL
            AND vector_dtype IS NULL AND l2_normalized IS NULL
            AND sqlite_vec_version IS NULL AND vector_table_name IS NULL)
        OR
        (index_kind = 'dense' AND vector_manifest_sha256 IS NOT NULL
            AND length(vector_manifest_sha256) = 64
            AND vector_manifest_sha256 NOT GLOB '*[^0-9a-f]*'
            AND embedding_model IS NOT NULL AND embedding_model_version IS NOT NULL
            AND embedding_dimension > 0 AND distance_metric = 'cosine'
            AND vector_dtype = 'float32' AND l2_normalized = 1
            AND sqlite_vec_version = '0.1.9'
            AND vector_table_name = 'vec_' || substr(index_version_id, 5))
    ),
    UNIQUE (corpus_id, generation_id, index_kind),
    UNIQUE (corpus_id, generation_id, index_version_id),
    UNIQUE (corpus_id, generation_id, index_kind, build_key_sha256),
    FOREIGN KEY (corpus_id, generation_id)
        REFERENCES corpus_generations(corpus_id, generation_id) ON DELETE CASCADE
) STRICT;

CREATE TABLE index_projection_members (
    corpus_id TEXT NOT NULL,
    generation_id TEXT NOT NULL,
    index_version_id TEXT NOT NULL,
    video_id TEXT NOT NULL,
    projection_version_id TEXT NOT NULL,
    PRIMARY KEY (corpus_id, generation_id, index_version_id, video_id),
    UNIQUE (corpus_id, generation_id, index_version_id, video_id, projection_version_id),
    FOREIGN KEY (corpus_id, generation_id, index_version_id)
        REFERENCES index_versions(corpus_id, generation_id, index_version_id)
        ON DELETE CASCADE,
    FOREIGN KEY (corpus_id, generation_id, video_id, projection_version_id)
        REFERENCES corpus_generation_members(
            corpus_id, generation_id, video_id, projection_version_id
        ) ON DELETE CASCADE
) STRICT;

CREATE TABLE search_documents (
    row_id INTEGER PRIMARY KEY,
    corpus_id TEXT NOT NULL,
    generation_id TEXT NOT NULL,
    index_version_id TEXT NOT NULL,
    video_id TEXT NOT NULL,
    projection_version_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    text_role TEXT NOT NULL
        CHECK (text_role IN ('source_span', 'normalized', 'title', 'summary')),
    text TEXT NOT NULL,
    start_ms INTEGER NOT NULL CHECK (start_ms >= 0),
    end_ms INTEGER NOT NULL CHECK (end_ms >= start_ms),
    UNIQUE (index_version_id, document_id),
    FOREIGN KEY (
        corpus_id, generation_id, index_version_id,
        video_id, projection_version_id
    ) REFERENCES index_projection_members(
        corpus_id, generation_id, index_version_id,
        video_id, projection_version_id
    ) ON DELETE CASCADE,
    FOREIGN KEY (projection_version_id, node_id)
        REFERENCES projection_nodes(projection_version_id, node_id) ON DELETE CASCADE
) STRICT;

CREATE VIRTUAL TABLE search_documents_fts USING fts5(
    text,
    content = 'search_documents',
    content_rowid = 'row_id',
    tokenize = 'unicode61'
);

CREATE TRIGGER search_documents_ai AFTER INSERT ON search_documents
WHEN EXISTS (
    SELECT 1 FROM index_versions
    WHERE index_version_id = new.index_version_id AND index_kind = 'lexical'
)
BEGIN
    INSERT INTO search_documents_fts(rowid, text) VALUES (new.row_id, new.text);
END;

CREATE TRIGGER search_documents_ad AFTER DELETE ON search_documents
WHEN EXISTS (
    SELECT 1 FROM index_versions
    WHERE index_version_id = old.index_version_id AND index_kind = 'lexical'
)
BEGIN
    INSERT INTO search_documents_fts(search_documents_fts, rowid, text)
    VALUES ('delete', old.row_id, old.text);
END;

CREATE TRIGGER search_documents_au AFTER UPDATE ON search_documents
WHEN EXISTS (
    SELECT 1 FROM index_versions
    WHERE index_version_id = old.index_version_id AND index_kind = 'lexical'
)
BEGIN
    INSERT INTO search_documents_fts(search_documents_fts, rowid, text)
    VALUES ('delete', old.row_id, old.text);
    INSERT INTO search_documents_fts(rowid, text) VALUES (new.row_id, new.text);
END;

-- Durable resumable v1 -> v2 migration and global read cutover.
CREATE TABLE migration_runs (
    migration_run_id TEXT PRIMARY KEY,
    source_snapshot_path TEXT NOT NULL,
    source_snapshot_sha256 TEXT NOT NULL
        CHECK (length(source_snapshot_sha256) = 64
            AND source_snapshot_sha256 NOT GLOB '*[^0-9a-f]*'),
    status TEXT NOT NULL CHECK (status IN ('running', 'ready', 'cutover', 'failed')),
    started_at_ms INTEGER NOT NULL CHECK (started_at_ms >= 0),
    completed_at_ms INTEGER,
    failure_reason TEXT,
    CHECK (
        length(migration_run_id) = 36
        AND substr(migration_run_id, 1, 4) = 'mig_'
        AND substr(migration_run_id, 5) NOT GLOB '*[^0-9a-f]*'
    ),
    CHECK (
        (status = 'running' AND completed_at_ms IS NULL AND failure_reason IS NULL)
        OR (status IN ('ready', 'cutover')
            AND completed_at_ms >= started_at_ms AND failure_reason IS NULL)
        OR (status = 'failed' AND completed_at_ms >= started_at_ms
            AND length(failure_reason) BETWEEN 1 AND 2000)
    )
) STRICT;

CREATE TABLE migration_items (
    migration_run_id TEXT NOT NULL,
    corpus_id TEXT NOT NULL,
    video_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'migrated', 'blocked', 'skipped')),
    target_generation_id TEXT,
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    status_reason TEXT,
    updated_at_ms INTEGER NOT NULL CHECK (updated_at_ms >= 0),
    PRIMARY KEY (migration_run_id, corpus_id, video_id),
    CHECK (
        (status = 'migrated' AND target_generation_id IS NOT NULL AND status_reason IS NULL)
        OR (status IN ('blocked', 'skipped') AND target_generation_id IS NULL
            AND length(status_reason) BETWEEN 1 AND 2000)
        OR (status = 'pending' AND target_generation_id IS NULL)
    ),
    FOREIGN KEY (migration_run_id)
        REFERENCES migration_runs(migration_run_id) ON DELETE CASCADE
) STRICT;

CREATE TABLE corpus_runtime_state (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    read_authority TEXT NOT NULL CHECK (read_authority IN ('v1', 'v2')),
    active_migration_run_id TEXT,
    cutover_at_ms INTEGER,
    FOREIGN KEY (active_migration_run_id)
        REFERENCES migration_runs(migration_run_id) ON DELETE RESTRICT
) STRICT;

INSERT INTO corpus_runtime_state VALUES (1, 'v1', NULL, NULL);

CREATE TRIGGER migration_run_insert_guard
BEFORE INSERT ON migration_runs
WHEN new.status <> 'running'
BEGIN
    SELECT RAISE(ABORT, 'migration run must be inserted RUNNING');
END;
CREATE TRIGGER migration_run_ready_guard
BEFORE UPDATE OF status ON migration_runs
WHEN new.status = 'ready'
BEGIN
    SELECT CASE WHEN old.status <> 'running'
        THEN RAISE(ABORT, 'only RUNNING migration can become READY') END;
    SELECT CASE WHEN EXISTS (
        SELECT 1 FROM migration_items
        WHERE migration_run_id = new.migration_run_id
          AND status IN ('pending', 'blocked')
    ) THEN RAISE(ABORT, 'pending or blocked migration items prevent READY') END;
END;
CREATE TRIGGER migration_item_target_insert_guard
BEFORE INSERT ON migration_items
WHEN new.status = 'migrated' AND NOT EXISTS (
    SELECT 1 FROM corpus_generations
    WHERE corpus_id = new.corpus_id AND generation_id = new.target_generation_id
)
BEGIN
    SELECT RAISE(ABORT, 'migrated item requires existing target generation');
END;
CREATE TRIGGER migration_item_target_update_guard
BEFORE UPDATE OF status, target_generation_id ON migration_items
WHEN new.status = 'migrated' AND NOT EXISTS (
    SELECT 1 FROM corpus_generations
    WHERE corpus_id = new.corpus_id AND generation_id = new.target_generation_id
)
BEGIN
    SELECT RAISE(ABORT, 'migrated item requires existing target generation');
END;

CREATE TABLE v2_mutations (
    mutation_id INTEGER PRIMARY KEY,
    migration_run_id TEXT NOT NULL,
    mutation_kind TEXT NOT NULL CHECK (
        mutation_kind IN ('corpus_insert', 'corpus_update', 'corpus_delete',
                          'artifact_insert', 'generation_delete', 'source_delete')
    ),
    corpus_id TEXT,
    occurred_at_ms INTEGER NOT NULL CHECK (occurred_at_ms >= 0),
    FOREIGN KEY (migration_run_id)
        REFERENCES migration_runs(migration_run_id) ON DELETE RESTRICT
) STRICT;

CREATE UNIQUE INDEX uq_live_projection_build
    ON projection_versions(corpus_id, video_id, build_key_sha256)
    WHERE status IN ('building', 'ready');
CREATE UNIQUE INDEX uq_live_generation_build
    ON corpus_generations(corpus_id, build_key_sha256)
    WHERE status IN ('building', 'ready');

-- Append-only source rows. Explicit source GC deletes a whole unreferenced
-- transcript_version; owned fetches and segments then cascade.
CREATE TRIGGER transcript_insert_status_guard
BEFORE INSERT ON transcript_versions
WHEN new.status <> 'building'
BEGIN
    SELECT RAISE(ABORT, 'transcript must be inserted BUILDING');
END;
CREATE TRIGGER transcript_identity_update_guard
BEFORE UPDATE OF transcript_version_id, source_sha256, source_schema_version,
    video_id, selected_language, track_kind, segment_count, start_ms, end_ms,
    created_at_ms ON transcript_versions
BEGIN
    SELECT RAISE(ABORT, 'transcript identity is immutable');
END;
CREATE TRIGGER transcript_status_transition_guard
BEFORE UPDATE OF status ON transcript_versions
WHEN NOT (old.status = 'building' AND new.status = 'ready')
BEGIN
    SELECT RAISE(ABORT, 'invalid transcript status transition');
END;
CREATE TRIGGER transcript_ready_guard
BEFORE UPDATE OF status ON transcript_versions
WHEN new.status = 'ready'
BEGIN
    SELECT CASE WHEN (SELECT COUNT(*) FROM source_segments s
                      WHERE s.transcript_version_id = new.transcript_version_id)
                     <> new.segment_count
        THEN RAISE(ABORT, 'source segment count mismatch') END;
    SELECT CASE WHEN (SELECT MIN(segment_ordinal) FROM source_segments
                      WHERE transcript_version_id = new.transcript_version_id) <> 0
        OR (SELECT MAX(segment_ordinal) FROM source_segments
            WHERE transcript_version_id = new.transcript_version_id) <> new.segment_count - 1
        THEN RAISE(ABORT, 'source segment ordinals must be dense') END;
    SELECT CASE WHEN (SELECT start_ms FROM source_segments
                      WHERE transcript_version_id = new.transcript_version_id
                        AND segment_ordinal = 0) <> new.start_ms
        OR (SELECT end_ms FROM source_segments
            WHERE transcript_version_id = new.transcript_version_id
              AND segment_ordinal = new.segment_count - 1) <> new.end_ms
        THEN RAISE(ABORT, 'source media range mismatch') END;
    SELECT CASE WHEN EXISTS (
        SELECT 1 FROM source_segments current
        JOIN source_segments following
          ON following.transcript_version_id = current.transcript_version_id
         AND following.segment_ordinal = current.segment_ordinal + 1
        WHERE current.transcript_version_id = new.transcript_version_id
          AND following.start_ms < current.start_ms
    ) THEN RAISE(ABORT, 'source segment starts must be monotonic') END;
    SELECT CASE WHEN new.validation_sha256 IS NULL
        OR new.validation_sha256 <> tube_validate_source(new.transcript_version_id)
        THEN RAISE(ABORT, 'source validation hash mismatch') END;
END;
CREATE TRIGGER transcript_fetches_no_update
BEFORE UPDATE ON transcript_fetches BEGIN
    SELECT RAISE(ABORT, 'transcript_fetches are append-only');
END;
CREATE TRIGGER source_segments_insert_guard
BEFORE INSERT ON source_segments
WHEN COALESCE((SELECT status FROM transcript_versions
               WHERE transcript_version_id = new.transcript_version_id), 'missing') <> 'building'
BEGIN
    SELECT RAISE(ABORT, 'source segments require BUILDING transcript');
END;
CREATE TRIGGER source_segments_no_update
BEFORE UPDATE ON source_segments BEGIN
    SELECT RAISE(ABORT, 'source_segments are immutable');
END;
CREATE TRIGGER source_segments_no_partial_delete
BEFORE DELETE ON source_segments
WHEN EXISTS (SELECT 1 FROM transcript_versions
             WHERE transcript_version_id = old.transcript_version_id)
BEGIN
    SELECT RAISE(ABORT, 'delete the whole transcript version, not source segments');
END;
CREATE TRIGGER transcript_fetches_no_partial_delete
BEFORE DELETE ON transcript_fetches
WHEN EXISTS (SELECT 1 FROM transcript_versions
             WHERE transcript_version_id = old.transcript_version_id)
BEGIN
    SELECT RAISE(ABORT, 'delete the whole transcript version, not fetch provenance');
END;
CREATE TRIGGER transcript_cache_origin_guard
BEFORE INSERT ON transcript_fetches
WHEN new.retrieval_mode = 'cache' AND NOT EXISTS (
    SELECT 1 FROM transcript_fetches origin
    WHERE origin.fetch_id = new.origin_fetch_id
      AND origin.transcript_version_id = new.transcript_version_id
      AND origin.retrieval_mode = 'live'
)
BEGIN
    SELECT RAISE(ABORT, 'cache origin must be LIVE for the same transcript');
END;

-- READY/RETIRED rows can only be reached through validated transitions. A
-- direct FAILED insert is allowed for a bounded post-rollback failure record.
CREATE TRIGGER projection_insert_status_guard
BEFORE INSERT ON projection_versions
WHEN new.status NOT IN ('building', 'failed')
BEGIN
    SELECT RAISE(ABORT, 'projection must be inserted BUILDING or FAILED');
END;
CREATE TRIGGER projection_source_ready_guard
BEFORE INSERT ON projection_versions
WHEN new.status = 'building' AND NOT EXISTS (
    SELECT 1 FROM transcript_versions source
    WHERE source.transcript_version_id = new.transcript_version_id
      AND source.video_id = new.video_id
      AND source.source_sha256 = new.source_sha256
      AND source.status = 'ready'
)
BEGIN
    SELECT RAISE(ABORT, 'projection requires READY source transcript');
END;
CREATE TRIGGER index_insert_status_guard
BEFORE INSERT ON index_versions
WHEN new.status NOT IN ('building', 'failed')
BEGIN
    SELECT RAISE(ABORT, 'index must be inserted BUILDING or FAILED');
END;
CREATE TRIGGER generation_insert_status_guard
BEFORE INSERT ON corpus_generations
WHEN new.status NOT IN ('building', 'failed')
BEGIN
    SELECT RAISE(ABORT, 'generation must be inserted BUILDING or FAILED');
END;

-- Projection children may be written only while their projection is BUILDING.
CREATE TRIGGER projection_nodes_insert_guard
BEFORE INSERT ON projection_nodes
WHEN COALESCE((SELECT status FROM projection_versions
               WHERE projection_version_id = new.projection_version_id), 'missing') <> 'building'
BEGIN
    SELECT RAISE(ABORT, 'projection nodes require BUILDING projection');
END;
CREATE TRIGGER projection_nodes_update_guard
BEFORE UPDATE ON projection_nodes
BEGIN
    SELECT RAISE(ABORT, 'projection nodes are immutable after insert');
END;
CREATE TRIGGER projection_nodes_delete_guard
BEFORE DELETE ON projection_nodes
WHEN EXISTS (SELECT 1 FROM projection_versions
             WHERE projection_version_id = old.projection_version_id)
BEGIN
    SELECT RAISE(ABORT, 'delete the whole projection, not individual nodes');
END;
CREATE TRIGGER projection_nodes_parent_guard
BEFORE INSERT ON projection_nodes
WHEN new.node_kind <> 'video' AND (
    NOT EXISTS (
        SELECT 1 FROM projection_nodes p
        WHERE p.projection_version_id = new.projection_version_id
          AND p.node_id = new.parent_node_id
    )
    OR NOT EXISTS (
        SELECT 1 FROM projection_nodes p
        WHERE p.projection_version_id = new.projection_version_id
          AND p.node_id = new.parent_node_id
          AND (
              (new.node_kind = 'chapter' AND p.node_kind = 'video')
              OR (new.node_kind = 'topic' AND p.node_kind IN ('video', 'chapter'))
              OR (new.node_kind = 'passage' AND p.node_kind IN ('video', 'chapter', 'topic'))
          )
    )
)
BEGIN
    SELECT RAISE(ABORT, 'invalid or missing projection parent');
END;

CREATE TRIGGER projection_relations_insert_guard
BEFORE INSERT ON projection_relations
WHEN EXISTS (
    SELECT 1 FROM projection_versions
    WHERE projection_version_id IN (
        new.from_projection_version_id, new.to_projection_version_id
    ) AND status <> 'building'
)
BEGIN
    SELECT RAISE(ABORT, 'relations require BUILDING projections');
END;
CREATE TRIGGER projection_relations_update_guard
BEFORE UPDATE ON projection_relations BEGIN
    SELECT RAISE(ABORT, 'projection relations are immutable');
END;
CREATE TRIGGER projection_relations_delete_guard
BEFORE DELETE ON projection_relations
WHEN EXISTS (
    SELECT 1 FROM projection_versions
    WHERE projection_version_id = old.from_projection_version_id
) AND EXISTS (
    SELECT 1 FROM projection_versions
    WHERE projection_version_id = old.to_projection_version_id
)
BEGIN
    SELECT RAISE(ABORT, 'delete a whole endpoint projection, not individual relations');
END;
CREATE TRIGGER projection_identity_update_guard
BEFORE UPDATE OF projection_version_id, corpus_id, video_id,
    transcript_version_id, source_sha256, projection_schema_version,
    build_key_sha256, processor_name, processor_version, model_name,
    model_version, processing_config_json, processing_config_sha256,
    created_at_ms ON projection_versions
BEGIN
    SELECT RAISE(ABORT, 'projection identity is immutable');
END;

-- Validate the complete temporal tree before BUILDING -> READY.
CREATE TRIGGER projection_ready_guard
BEFORE UPDATE OF status ON projection_versions
WHEN new.status = 'ready'
BEGIN
    SELECT CASE WHEN old.status <> 'building'
        THEN RAISE(ABORT, 'only BUILDING projection can become READY') END;
    SELECT CASE WHEN (SELECT COUNT(*) FROM projection_nodes n
                      WHERE n.projection_version_id = new.projection_version_id
                        AND n.node_kind = 'video' AND n.parent_node_id IS NULL) <> 1
        THEN RAISE(ABORT, 'projection requires exactly one video root') END;
    SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM projection_nodes n
                                 WHERE n.projection_version_id = new.projection_version_id
                                   AND n.node_kind = 'passage')
        THEN RAISE(ABORT, 'projection requires passage leaves') END;
    SELECT CASE WHEN EXISTS (
        SELECT 1 FROM projection_nodes n
        LEFT JOIN source_segments first_seg
          ON first_seg.transcript_version_id = new.transcript_version_id
         AND first_seg.segment_ordinal = n.start_segment_ordinal
        LEFT JOIN source_segments last_seg
          ON last_seg.transcript_version_id = new.transcript_version_id
         AND last_seg.segment_ordinal = n.end_segment_ordinal
        WHERE n.projection_version_id = new.projection_version_id
          AND (first_seg.segment_id IS NULL OR last_seg.segment_id IS NULL
               OR n.start_ms <> first_seg.start_ms OR n.end_ms <> last_seg.end_ms)
    ) THEN RAISE(ABORT, 'node range/time does not resolve to source') END;
    SELECT CASE WHEN EXISTS (
        SELECT 1 FROM source_segments s
        WHERE s.transcript_version_id = new.transcript_version_id
          AND (SELECT COUNT(*) FROM projection_nodes p
               WHERE p.projection_version_id = new.projection_version_id
                 AND p.node_kind = 'passage'
                 AND s.segment_ordinal BETWEEN p.start_segment_ordinal
                                           AND p.end_segment_ordinal) <> 1
    ) THEN RAISE(ABORT, 'passages must partition source exactly once') END;
    SELECT CASE WHEN EXISTS (
        SELECT 1 FROM projection_nodes child
        LEFT JOIN projection_nodes parent
          ON parent.projection_version_id = child.projection_version_id
         AND parent.node_id = child.parent_node_id
        WHERE child.projection_version_id = new.projection_version_id
          AND child.node_kind <> 'video'
          AND (parent.node_id IS NULL
               OR (child.node_kind = 'chapter' AND parent.node_kind <> 'video')
               OR (child.node_kind = 'topic' AND parent.node_kind NOT IN ('video', 'chapter'))
               OR (child.node_kind = 'passage' AND parent.node_kind NOT IN ('video', 'chapter', 'topic')))
    ) THEN RAISE(ABORT, 'invalid projection parent hierarchy') END;
    SELECT CASE WHEN EXISTS (
        SELECT 1 FROM projection_nodes parent
        WHERE parent.projection_version_id = new.projection_version_id
          AND ((parent.node_kind = 'passage' AND EXISTS (
                  SELECT 1 FROM projection_nodes child
                  WHERE child.projection_version_id = parent.projection_version_id
                    AND child.parent_node_id = parent.node_id))
               OR (parent.node_kind <> 'passage' AND NOT EXISTS (
                  SELECT 1 FROM projection_nodes child
                  WHERE child.projection_version_id = parent.projection_version_id
                    AND child.parent_node_id = parent.node_id)))
    ) THEN RAISE(ABORT, 'only passage nodes may be leaves') END;
    SELECT CASE WHEN EXISTS (
        SELECT 1 FROM projection_nodes child
        JOIN projection_nodes parent
          ON parent.projection_version_id = child.projection_version_id
         AND parent.node_id = child.parent_node_id
        WHERE child.projection_version_id = new.projection_version_id
          AND (child.start_segment_ordinal < parent.start_segment_ordinal
               OR child.end_segment_ordinal > parent.end_segment_ordinal)
    ) THEN RAISE(ABORT, 'child range escapes parent') END;
    SELECT CASE WHEN EXISTS (
        SELECT 1 FROM projection_nodes n
        WHERE n.projection_version_id = new.projection_version_id
          AND n.parent_node_id IS NOT NULL
        GROUP BY n.parent_node_id
        HAVING COUNT(DISTINCT n.node_kind) <> 1
            OR MIN(n.ordinal) <> 0 OR MAX(n.ordinal) + 1 <> COUNT(*)
    ) THEN RAISE(ABORT, 'siblings require one level and dense ordinals') END;
    SELECT CASE WHEN tube_validate_projection(new.projection_version_id) <> 1
        THEN RAISE(ABORT, 'projection validator rejected build') END;
END;

CREATE TRIGGER projection_status_transition_guard
BEFORE UPDATE OF status ON projection_versions
WHEN NOT (
    (old.status = 'building' AND new.status IN ('ready', 'failed'))
    OR (old.status = 'ready' AND new.status = 'retired')
)
BEGIN
    SELECT RAISE(ABORT, 'invalid projection status transition');
END;

-- Generation and index contents are immutable outside BUILDING.
CREATE TRIGGER generation_members_write_guard
BEFORE INSERT ON corpus_generation_members
WHEN COALESCE((SELECT status FROM corpus_generations
               WHERE corpus_id = new.corpus_id AND generation_id = new.generation_id), 'missing') <> 'building'
BEGIN
    SELECT RAISE(ABORT, 'generation members require BUILDING generation');
END;
CREATE TRIGGER generation_members_update_guard
BEFORE UPDATE ON corpus_generation_members
BEGIN
    SELECT RAISE(ABORT, 'generation members are immutable');
END;
CREATE TRIGGER generation_members_delete_guard
BEFORE DELETE ON corpus_generation_members
WHEN EXISTS (SELECT 1 FROM corpus_generations
             WHERE corpus_id = old.corpus_id AND generation_id = old.generation_id)
BEGIN
    SELECT RAISE(ABORT, 'delete the generation, not individual members');
END;
CREATE TRIGGER generation_identity_update_guard
BEFORE UPDATE OF generation_id, corpus_id, build_key_sha256,
    source_manifest_sha256, created_at_ms ON corpus_generations
BEGIN
    SELECT RAISE(ABORT, 'generation identity is immutable');
END;

CREATE TRIGGER index_members_write_guard
BEFORE INSERT ON index_projection_members
WHEN COALESCE((SELECT status FROM index_versions
               WHERE index_version_id = new.index_version_id), 'missing') <> 'building'
BEGIN
    SELECT RAISE(ABORT, 'index members require BUILDING index');
END;
CREATE TRIGGER index_members_update_guard
BEFORE UPDATE ON index_projection_members
BEGIN
    SELECT RAISE(ABORT, 'index projection members are immutable');
END;
CREATE TRIGGER index_members_delete_guard
BEFORE DELETE ON index_projection_members
WHEN EXISTS (SELECT 1 FROM index_versions
             WHERE index_version_id = old.index_version_id)
BEGIN
    SELECT RAISE(ABORT, 'delete the index, not individual index members');
END;
CREATE TRIGGER search_documents_write_guard
BEFORE INSERT ON search_documents
WHEN COALESCE((SELECT status FROM index_versions
               WHERE index_version_id = new.index_version_id), 'missing') <> 'building'
BEGIN
    SELECT RAISE(ABORT, 'search documents require BUILDING index');
END;
CREATE TRIGGER search_documents_update_guard
BEFORE UPDATE ON search_documents
BEGIN
    SELECT RAISE(ABORT, 'search documents are immutable');
END;
CREATE TRIGGER search_documents_delete_guard
BEFORE DELETE ON search_documents
WHEN EXISTS (SELECT 1 FROM index_versions
             WHERE index_version_id = old.index_version_id)
BEGIN
    SELECT RAISE(ABORT, 'delete the index, not individual search documents');
END;
CREATE TRIGGER index_delete_guard
BEFORE DELETE ON index_versions
WHEN EXISTS (
    SELECT 1 FROM corpus_generations
    WHERE corpus_id = old.corpus_id AND generation_id = old.generation_id
)
BEGIN
    SELECT RAISE(ABORT, 'delete the whole generation, not an individual index');
END;
CREATE TRIGGER index_identity_update_guard
BEFORE UPDATE OF index_version_id, corpus_id, generation_id, index_kind,
    build_key_sha256, config_json, config_sha256, document_manifest_sha256,
    vector_manifest_sha256, embedding_model, embedding_model_version,
    embedding_dimension, distance_metric, vector_dtype, l2_normalized,
    sqlite_vec_version, vector_table_name, created_at_ms ON index_versions
BEGIN
    SELECT RAISE(ABORT, 'index identity is immutable');
END;

CREATE TRIGGER index_ready_guard
BEFORE UPDATE OF status ON index_versions
WHEN new.status = 'ready'
BEGIN
    SELECT CASE WHEN old.status <> 'building'
        THEN RAISE(ABORT, 'only BUILDING index can become READY') END;
    SELECT CASE WHEN EXISTS (
        SELECT projection_version_id FROM corpus_generation_members
        WHERE corpus_id = new.corpus_id AND generation_id = new.generation_id
        EXCEPT
        SELECT projection_version_id FROM index_projection_members
        WHERE corpus_id = new.corpus_id AND generation_id = new.generation_id
          AND index_version_id = new.index_version_id
    ) OR EXISTS (
        SELECT projection_version_id FROM index_projection_members
        WHERE corpus_id = new.corpus_id AND generation_id = new.generation_id
          AND index_version_id = new.index_version_id
        EXCEPT
        SELECT projection_version_id FROM corpus_generation_members
        WHERE corpus_id = new.corpus_id AND generation_id = new.generation_id
    ) THEN RAISE(ABORT, 'index projection set must equal generation projection set') END;
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM search_documents
        WHERE index_version_id = new.index_version_id
    ) THEN RAISE(ABORT, 'READY index requires search documents') END;
    SELECT CASE WHEN new.validation_sha256 IS NULL
        OR new.validation_sha256 <> tube_validate_index(new.index_version_id)
        THEN RAISE(ABORT, 'index validation hash mismatch') END;
END;

CREATE TRIGGER index_status_transition_guard
BEFORE UPDATE OF status ON index_versions
WHEN NOT (
    (old.status = 'building' AND new.status IN ('ready', 'failed'))
    OR (old.status = 'ready' AND new.status = 'retired')
)
BEGIN
    SELECT RAISE(ABORT, 'invalid index status transition');
END;

CREATE TRIGGER generation_ready_guard
BEFORE UPDATE OF status ON corpus_generations
WHEN new.status = 'ready'
BEGIN
    SELECT CASE WHEN old.status <> 'building'
        THEN RAISE(ABORT, 'only BUILDING generation can become READY') END;
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM corpus_generation_members
        WHERE corpus_id = new.corpus_id AND generation_id = new.generation_id
    ) THEN RAISE(ABORT, 'generation requires members') END;
    SELECT CASE WHEN EXISTS (
        SELECT 1 FROM corpus_generation_members gm
        JOIN projection_versions p
          ON p.projection_version_id = gm.projection_version_id
        WHERE gm.corpus_id = new.corpus_id AND gm.generation_id = new.generation_id
          AND p.status <> 'ready'
    ) THEN RAISE(ABORT, 'generation requires READY projections') END;
    SELECT CASE WHEN (SELECT COUNT(*) FROM index_versions i
                      WHERE i.corpus_id = new.corpus_id
                        AND i.generation_id = new.generation_id
                        AND i.status = 'ready') <> 2
        THEN RAISE(ABORT, 'generation requires READY lexical and dense indexes') END;
    SELECT CASE WHEN tube_validate_generation(new.corpus_id, new.generation_id) <> 1
        THEN RAISE(ABORT, 'generation validator rejected build') END;
END;

CREATE TRIGGER generation_active_delete_guard
BEFORE DELETE ON corpus_generations
WHEN EXISTS (
    SELECT 1 FROM corpora
    WHERE corpus_id = old.corpus_id AND active_generation_id = old.generation_id
)
BEGIN
    SELECT RAISE(ABORT, 'active generation cannot be deleted');
END;
CREATE TRIGGER generation_vector_cleanup_guard
BEFORE DELETE ON corpus_generations
WHEN EXISTS (
    SELECT 1 FROM index_versions i
    JOIN sqlite_master m ON m.type = 'table' AND m.name = i.vector_table_name
    WHERE i.corpus_id = old.corpus_id AND i.generation_id = old.generation_id
      AND i.index_kind = 'dense'
)
BEGIN
    SELECT RAISE(ABORT, 'drop generation vector table before metadata deletion');
END;
CREATE TRIGGER generation_status_transition_guard
BEFORE UPDATE OF status ON corpus_generations
WHEN NOT (
    (old.status = 'building' AND new.status IN ('ready', 'failed'))
    OR (old.status = 'ready' AND new.status = 'retired')
)
BEGIN
    SELECT RAISE(ABORT, 'invalid generation status transition');
END;

-- One atomic pointer switch activates the entire source/projection/index cohort.
CREATE TRIGGER corpus_generation_activation_guard
BEFORE UPDATE OF active_generation_id ON corpora
WHEN new.active_generation_id IS NOT NULL
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM corpus_generations g
        WHERE g.corpus_id = new.corpus_id
          AND g.generation_id = new.active_generation_id
          AND g.status = 'ready'
    ) THEN RAISE(ABORT, 'active generation must be READY') END;
END;

CREATE TRIGGER corpus_generation_retire_previous
AFTER UPDATE OF active_generation_id ON corpora
WHEN old.active_generation_id IS NOT NULL
 AND old.active_generation_id <> new.active_generation_id
BEGIN
    UPDATE corpus_generations SET status = 'retired'
    WHERE corpus_id = old.corpus_id AND generation_id = old.active_generation_id;
    UPDATE projection_versions SET status = 'retired'
    WHERE corpus_id = old.corpus_id
      AND projection_version_id IN (
          SELECT projection_version_id FROM corpus_generation_members
          WHERE corpus_id = old.corpus_id AND generation_id = old.active_generation_id
      )
      AND projection_version_id NOT IN (
          SELECT projection_version_id FROM corpus_generation_members
          WHERE corpus_id = new.corpus_id AND generation_id = new.active_generation_id
      ) AND status = 'ready';
    UPDATE index_versions SET status = 'retired'
    WHERE corpus_id = old.corpus_id AND generation_id = old.active_generation_id
      AND status = 'ready';
END;

-- Cutover is resumable and fail-closed. SKIPPED is an explicit operator choice;
-- PENDING or BLOCKED items prevent v2 authority.
CREATE TRIGGER corpus_runtime_state_no_delete
BEFORE DELETE ON corpus_runtime_state
BEGIN
    SELECT RAISE(ABORT, 'corpus runtime state singleton cannot be deleted');
END;
CREATE TRIGGER corpus_runtime_state_no_second_insert
BEFORE INSERT ON corpus_runtime_state
WHEN EXISTS (SELECT 1 FROM corpus_runtime_state WHERE singleton=1)
BEGIN
    SELECT RAISE(ABORT, 'corpus runtime state singleton already exists');
END;
CREATE TRIGGER migration_runs_cutover_immutable
BEFORE UPDATE ON migration_runs
WHEN EXISTS (
    SELECT 1 FROM corpus_runtime_state s
    WHERE s.read_authority = 'v2'
      AND s.active_migration_run_id = old.migration_run_id
) AND NOT (old.status = 'ready' AND new.status = 'cutover'
           AND new.migration_run_id = old.migration_run_id
           AND new.source_snapshot_path = old.source_snapshot_path
           AND new.source_snapshot_sha256 = old.source_snapshot_sha256
           AND new.started_at_ms = old.started_at_ms
           AND new.completed_at_ms = old.completed_at_ms
           AND new.failure_reason IS old.failure_reason)
BEGIN
    SELECT RAISE(ABORT, 'active cutover migration run is immutable');
END;
CREATE TRIGGER migration_runs_cutover_no_delete
BEFORE DELETE ON migration_runs
WHEN EXISTS (
    SELECT 1 FROM corpus_runtime_state s
    WHERE s.read_authority = 'v2'
      AND s.active_migration_run_id = old.migration_run_id
)
BEGIN
    SELECT RAISE(ABORT, 'active cutover migration run cannot be deleted');
END;
CREATE TRIGGER migration_items_cutover_no_insert
BEFORE INSERT ON migration_items
WHEN EXISTS (
    SELECT 1 FROM corpus_runtime_state s
    WHERE s.read_authority = 'v2'
      AND s.active_migration_run_id = new.migration_run_id
)
BEGIN
    SELECT RAISE(ABORT, 'active cutover migration items are immutable');
END;
CREATE TRIGGER migration_items_cutover_no_update
BEFORE UPDATE ON migration_items
WHEN EXISTS (
    SELECT 1 FROM corpus_runtime_state s
    WHERE s.read_authority = 'v2'
      AND s.active_migration_run_id = old.migration_run_id
)
BEGIN
    SELECT RAISE(ABORT, 'active cutover migration items are immutable');
END;
CREATE TRIGGER migration_items_cutover_no_delete
BEFORE DELETE ON migration_items
WHEN EXISTS (
    SELECT 1 FROM corpus_runtime_state s
    WHERE s.read_authority = 'v2'
      AND s.active_migration_run_id = old.migration_run_id
)
BEGIN
    SELECT RAISE(ABORT, 'active cutover migration items are immutable');
END;

CREATE TRIGGER corpus_v2_cutover_guard
BEFORE UPDATE OF read_authority ON corpus_runtime_state
WHEN old.read_authority = 'v1' AND new.read_authority = 'v2'
BEGIN
    SELECT CASE WHEN new.active_migration_run_id IS NULL OR NOT EXISTS (
        SELECT 1 FROM migration_runs r
        WHERE r.migration_run_id = new.active_migration_run_id
          AND r.status = 'ready'
          AND r.completed_at_ms IS NOT NULL
    ) THEN RAISE(ABORT, 'v2 cutover requires READY migration run') END;
    SELECT CASE WHEN new.cutover_at_ms IS NULL OR new.cutover_at_ms < (
        SELECT completed_at_ms FROM migration_runs
        WHERE migration_run_id = new.active_migration_run_id
    ) THEN RAISE(ABORT, 'v2 cutover requires valid cutover timestamp') END;
    SELECT CASE WHEN EXISTS (
        SELECT 1 FROM v2_mutations
        WHERE migration_run_id = new.active_migration_run_id
    ) THEN RAISE(ABORT, 'v2 cutover mutation ledger must start empty') END;
    SELECT CASE WHEN EXISTS (
        SELECT 1 FROM migration_items i
        WHERE i.migration_run_id = new.active_migration_run_id
          AND i.status IN ('pending', 'blocked')
    ) THEN RAISE(ABORT, 'pending or blocked migration items prevent cutover') END;
    SELECT CASE WHEN EXISTS (
        SELECT 1 FROM migration_items i
        LEFT JOIN corpus_generations g
          ON g.corpus_id = i.corpus_id AND g.generation_id = i.target_generation_id
        LEFT JOIN corpora c ON c.corpus_id = i.corpus_id
        LEFT JOIN corpus_generation_members gm
          ON gm.corpus_id = i.corpus_id
         AND gm.generation_id = i.target_generation_id
         AND gm.video_id = i.video_id
        WHERE i.migration_run_id = new.active_migration_run_id
          AND i.status = 'migrated'
          AND (g.status IS NULL OR g.status <> 'ready'
               OR c.active_generation_id <> i.target_generation_id
               OR gm.video_id IS NULL)
    ) THEN RAISE(ABORT, 'migrated item requires active READY target generation') END;
END;

CREATE TRIGGER corpus_cutover_identity_guard
BEFORE UPDATE OF active_migration_run_id, cutover_at_ms ON corpus_runtime_state
WHEN old.read_authority = 'v2' AND (
    new.active_migration_run_id IS NOT old.active_migration_run_id
    OR new.cutover_at_ms IS NOT old.cutover_at_ms
)
BEGIN
    SELECT RAISE(ABORT, 'active migration run and cutover time are immutable in v2');
END;

CREATE TRIGGER corpus_v1_rollback_guard
BEFORE UPDATE OF read_authority ON corpus_runtime_state
WHEN old.read_authority = 'v2' AND new.read_authority = 'v1'
BEGIN
    SELECT RAISE(ABORT, 'v2 cutover is irreversible through runtime');
END;

CREATE TRIGGER corpus_cutover_mark_run
AFTER UPDATE OF read_authority ON corpus_runtime_state
WHEN old.read_authority = 'v1' AND new.read_authority = 'v2'
BEGIN
    UPDATE migration_runs SET status='cutover'
    WHERE migration_run_id = new.active_migration_run_id;
END;

-- These append-only events record post-cutover mutation history for audit and
-- forward recovery. They are not a switch back to v1.
CREATE TRIGGER v2_mutations_no_update
BEFORE UPDATE ON v2_mutations BEGIN
    SELECT RAISE(ABORT, 'v2 mutation ledger is append-only');
END;
CREATE TRIGGER v2_mutations_no_delete
BEFORE DELETE ON v2_mutations BEGIN
    SELECT RAISE(ABORT, 'v2 mutation ledger is append-only');
END;
CREATE TRIGGER count_v2_corpus_insert
AFTER INSERT ON corpora
WHEN (SELECT read_authority FROM corpus_runtime_state WHERE singleton=1) = 'v2'
BEGIN
    INSERT INTO v2_mutations(migration_run_id,mutation_kind,corpus_id,occurred_at_ms)
    SELECT active_migration_run_id,'corpus_insert',new.corpus_id,
           CAST(strftime('%s','now') AS INTEGER) * 1000
    FROM corpus_runtime_state WHERE singleton=1;
END;
CREATE TRIGGER count_v2_corpus_update
AFTER UPDATE ON corpora
WHEN (SELECT read_authority FROM corpus_runtime_state WHERE singleton=1) = 'v2'
BEGIN
    INSERT INTO v2_mutations(migration_run_id,mutation_kind,corpus_id,occurred_at_ms)
    SELECT active_migration_run_id,'corpus_update',new.corpus_id,
           CAST(strftime('%s','now') AS INTEGER) * 1000
    FROM corpus_runtime_state WHERE singleton=1;
END;
CREATE TRIGGER count_v2_corpus_delete
AFTER DELETE ON corpora
WHEN (SELECT read_authority FROM corpus_runtime_state WHERE singleton=1) = 'v2'
BEGIN
    INSERT INTO v2_mutations(migration_run_id,mutation_kind,corpus_id,occurred_at_ms)
    SELECT active_migration_run_id,'corpus_delete',old.corpus_id,
           CAST(strftime('%s','now') AS INTEGER) * 1000
    FROM corpus_runtime_state WHERE singleton=1;
END;
CREATE TRIGGER count_v2_transcript_insert
AFTER INSERT ON transcript_versions
WHEN (SELECT read_authority FROM corpus_runtime_state WHERE singleton=1) = 'v2'
BEGIN
    INSERT INTO v2_mutations(migration_run_id,mutation_kind,corpus_id,occurred_at_ms)
    SELECT active_migration_run_id,'artifact_insert',NULL,
           CAST(strftime('%s','now') AS INTEGER) * 1000
    FROM corpus_runtime_state WHERE singleton=1;
END;
CREATE TRIGGER count_v2_projection_insert
AFTER INSERT ON projection_versions
WHEN (SELECT read_authority FROM corpus_runtime_state WHERE singleton=1) = 'v2'
BEGIN
    INSERT INTO v2_mutations(migration_run_id,mutation_kind,corpus_id,occurred_at_ms)
    SELECT active_migration_run_id,'artifact_insert',new.corpus_id,
           CAST(strftime('%s','now') AS INTEGER) * 1000
    FROM corpus_runtime_state WHERE singleton=1;
END;
CREATE TRIGGER count_v2_generation_insert
AFTER INSERT ON corpus_generations
WHEN (SELECT read_authority FROM corpus_runtime_state WHERE singleton=1) = 'v2'
BEGIN
    INSERT INTO v2_mutations(migration_run_id,mutation_kind,corpus_id,occurred_at_ms)
    SELECT active_migration_run_id,'artifact_insert',new.corpus_id,
           CAST(strftime('%s','now') AS INTEGER) * 1000
    FROM corpus_runtime_state WHERE singleton=1;
END;
CREATE TRIGGER count_v2_index_insert
AFTER INSERT ON index_versions
WHEN (SELECT read_authority FROM corpus_runtime_state WHERE singleton=1) = 'v2'
BEGIN
    INSERT INTO v2_mutations(migration_run_id,mutation_kind,corpus_id,occurred_at_ms)
    SELECT active_migration_run_id,'artifact_insert',new.corpus_id,
           CAST(strftime('%s','now') AS INTEGER) * 1000
    FROM corpus_runtime_state WHERE singleton=1;
END;
CREATE TRIGGER count_v2_generation_delete
AFTER DELETE ON corpus_generations
WHEN (SELECT read_authority FROM corpus_runtime_state WHERE singleton=1) = 'v2'
BEGIN
    INSERT INTO v2_mutations(migration_run_id,mutation_kind,corpus_id,occurred_at_ms)
    SELECT active_migration_run_id,'generation_delete',old.corpus_id,
           CAST(strftime('%s','now') AS INTEGER) * 1000
    FROM corpus_runtime_state WHERE singleton=1;
END;
CREATE TRIGGER count_v2_source_delete
AFTER DELETE ON transcript_versions
WHEN (SELECT read_authority FROM corpus_runtime_state WHERE singleton=1) = 'v2'
BEGIN
    INSERT INTO v2_mutations(migration_run_id,mutation_kind,corpus_id,occurred_at_ms)
    SELECT active_migration_run_id,'source_delete',NULL,
           CAST(strftime('%s','now') AS INTEGER) * 1000
    FROM corpus_runtime_state WHERE singleton=1;
END;

CREATE INDEX idx_transcript_versions_video
    ON transcript_versions(video_id, selected_language, track_kind);
CREATE INDEX idx_source_segments_time
    ON source_segments(transcript_version_id, start_ms, end_ms);
CREATE INDEX idx_projection_versions_member
    ON projection_versions(corpus_id, video_id, status);
CREATE INDEX idx_projection_nodes_time
    ON projection_nodes(projection_version_id, start_ms, end_ms);
CREATE INDEX idx_projection_nodes_parent
    ON projection_nodes(projection_version_id, parent_node_id, ordinal);
CREATE INDEX idx_generation_members_projection
    ON corpus_generation_members(corpus_id, generation_id, projection_version_id);
CREATE INDEX idx_search_documents_index
    ON search_documents(index_version_id, projection_version_id, start_ms);
