# WikiTree Intelligence Database Schema

Version 1 PostgreSQL schema for the WikiTree Intelligence workbench.

## Design Principles

- **PostgreSQL only** - No additional graph database in v1
- **Immutable review receipts** - Preserve decision history
- **Explicit state machines** - Import jobs and reviews have defined state transitions
- **JSONB for flexibility** - Use for checkpoints, evidence, and structured details
- **Canonical person model** - `people` is the source of truth for all workflows
- **External identities** - Link local people to GEDCOM/WikiTree via `external_identities`
- **Cached searches** - Store WikiTree search results without polluting identity tables
- **Graph via SQL** - Use `relationships` table with recursive queries for traversal
- **PostgreSQL job leasing** - Worker coordination without external queue

## Table Categories

### Authentication & Session Management

- `app_users` - Google-authenticated users
- `wikitree_connections` - Per-user WikiTree auth and scope

**Note on sessions:** v1 uses Starlette `SessionMiddleware` with signed cookies (no database table needed). Database-backed sessions can be added later if hosting multi-user version.

### Import Jobs & Staging

- `import_jobs` - Top-level GEDCOM import state
- `import_job_stages` - Stage-level checkpoints and retry state

### Canonical Data Model

- `people` - Canonical local person records
- `person_names` - Structured names and alternates
- `person_facts` - Birth, death, places, notes
- `relationships` - Graph edges (parent, child, spouse, sibling)
- `sources` - Normalized source records and provenance

### External System Integration

- `external_identities` - Links to GEDCOM/WikiTree profiles
- `wikitree_dump_versions` - Weekly dump tracking
- `wikitree_dump_people` - Cached WikiTree public profiles
- `wikitree_dump_marriages` - Cached WikiTree marriages

### Search & Matching

- `wikitree_search_runs` - Cached search attempts with query plans
- `wikitree_search_candidates` - Unconfirmed ranked search results
- `match_reviews` - Human-confirmed matching decisions
- `evidence_packets` - Frozen evidence for each review
- `sync_review_items` - Later enrichment queue for matched profiles

## Table Definitions

### app_users

Google-authenticated application users.

```sql
CREATE TABLE app_users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  google_subject TEXT NOT NULL UNIQUE,
  email TEXT NOT NULL,
  display_name TEXT,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_app_users_email ON app_users(email);
```

**Usage:**
- One row per Google account
- `google_subject` is the stable Google user ID (from JWT `sub` claim)
- All user-owned data references this table

**Session Management:**
- v1 uses Starlette `SessionMiddleware` with signed, httpOnly cookies
- No database table needed - session data (user_id) stored in encrypted cookie
- Simpler for local-first, can migrate to database sessions if hosting multi-user version

---

### wikitree_connections

Per-user WikiTree authentication state and visibility scope.

```sql
CREATE TABLE wikitree_connections (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
  wikitree_user_key TEXT,
  status TEXT NOT NULL CHECK (status IN ('connected', 'disconnected', 'expired', 'failed')),
  session_ref TEXT,
  connected_at TIMESTAMP WITH TIME ZONE,
  expires_at TIMESTAMP WITH TIME ZONE,
  last_verified_at TIMESTAMP WITH TIME ZONE,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_wikitree_connections_user ON wikitree_connections(user_id);
```

**Usage:**
- Stores WikiTree OAuth tokens or session material for private-data access
- `wikitree_user_key` is the WikiTree user ID or handle
- `status` tracks connection health
- Backend refreshes tokens and updates `last_verified_at`

---

### import_jobs

Top-level GEDCOM import job state and metadata.

```sql
CREATE TABLE import_jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
  source_type TEXT NOT NULL CHECK (source_type IN ('gedcom', 'wikitree-export', 'manual')),
  original_filename TEXT NOT NULL,
  stored_path TEXT NOT NULL,
  file_size_bytes BIGINT NOT NULL,
  content_sha256 TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('uploaded', 'queued', 'in_progress', 'paused', 'completed', 'failed', 'cancelled')),
  current_stage TEXT,
  claimed_by TEXT,
  claimed_at TIMESTAMP WITH TIME ZONE,
  upload_completed_at TIMESTAMP WITH TIME ZONE,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  started_at TIMESTAMP WITH TIME ZONE,
  completed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_import_jobs_user_id ON import_jobs(user_id);
CREATE INDEX idx_import_jobs_status ON import_jobs(status);
CREATE INDEX idx_import_jobs_claimed_by ON import_jobs(claimed_by);
```

**Usage:**
- One row per GEDCOM upload
- `stored_path` references file in shared volume (not in database)
- `status` tracks job lifecycle
- Worker claims job via `claimed_by` and `claimed_at` (PostgreSQL-based leasing)
- `current_stage` indicates which pipeline stage is active

---

### import_job_stages

Stage-level checkpoints, retry state, and progress metadata.

```sql
CREATE TABLE import_job_stages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  import_job_id UUID NOT NULL REFERENCES import_jobs(id) ON DELETE CASCADE,
  stage_name TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('pending', 'in_progress', 'completed', 'failed', 'retrying')),
  checkpoint_json JSONB,
  lease_expires_at TIMESTAMP WITH TIME ZONE,
  error_message TEXT,
  started_at TIMESTAMP WITH TIME ZONE,
  completed_at TIMESTAMP WITH TIME ZONE,
  retry_count INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX idx_import_job_stages_job_id ON import_job_stages(import_job_id);
CREATE INDEX idx_import_job_stages_status ON import_job_stages(status);
```

**Usage:**
- One row per stage: `parse`, `normalize`, `search`, `match`, `review`
- `checkpoint_json` stores batch progress for resumability
- `lease_expires_at` prevents abandoned work from blocking progress
- Worker updates `checkpoint_json` after each batch for incremental commits

---

### people

Canonical local person records used by all workflows.

```sql
CREATE TABLE people (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  primary_name TEXT NOT NULL,
  birth_year INTEGER,
  death_year INTEGER,
  is_living BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_people_primary_name ON people(primary_name);
CREATE INDEX idx_people_birth_year ON people(birth_year);
CREATE INDEX idx_people_is_living ON people(is_living);
```

**Usage:**
- One row per unique person across GEDCOM imports and WikiTree matches
- `primary_name` is display name (denormalized for convenience)
- Merge candidates can be identified and resolved via `external_identities`

---

### person_names

Structured and normalized names for one person.

```sql
CREATE TABLE person_names (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  person_id UUID NOT NULL REFERENCES people(id) ON DELETE CASCADE,
  name_type TEXT NOT NULL CHECK (name_type IN ('primary', 'birth', 'married', 'alternate', 'aka')),
  full_name TEXT NOT NULL,
  given_names TEXT,
  surname TEXT,
  normalized_name TEXT NOT NULL
);

CREATE INDEX idx_person_names_person_id ON person_names(person_id);
CREATE INDEX idx_person_names_normalized ON person_names(normalized_name);
CREATE INDEX idx_person_names_surname ON person_names(surname);
```

**Usage:**
- Multiple names per person (birth name, married name, alternates)
- `normalized_name` is lowercase, stripped, for fuzzy matching
- `name_type` distinguishes primary vs alternates

---

### person_facts

Facts like birth, death, places, notes, and relationship-adjacent metadata.

```sql
CREATE TABLE person_facts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  person_id UUID NOT NULL REFERENCES people(id) ON DELETE CASCADE,
  fact_type TEXT NOT NULL CHECK (fact_type IN ('birth', 'death', 'christening', 'burial', 'occupation', 'residence', 'note', 'other')),
  fact_value_json JSONB,
  date_text TEXT,
  place_text TEXT,
  source_id UUID REFERENCES sources(id) ON DELETE SET NULL
);

CREATE INDEX idx_person_facts_person_id ON person_facts(person_id);
CREATE INDEX idx_person_facts_type ON person_facts(fact_type);
CREATE INDEX idx_person_facts_source ON person_facts(source_id);
```

**Usage:**
- One row per fact
- `fact_value_json` stores structured details (JSONB for flexibility)
- `date_text` and `place_text` are human-readable versions
- `source_id` links to provenance

---

### relationships

Directed edges between people (parent, child, spouse, sibling).

```sql
CREATE TABLE relationships (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  from_person_id UUID NOT NULL REFERENCES people(id) ON DELETE CASCADE,
  to_person_id UUID NOT NULL REFERENCES people(id) ON DELETE CASCADE,
  relationship_type TEXT NOT NULL CHECK (relationship_type IN ('parent', 'child', 'spouse', 'sibling', 'partner')),
  source_id UUID REFERENCES sources(id) ON DELETE SET NULL,
  is_inferred BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_relationships_from ON relationships(from_person_id);
CREATE INDEX idx_relationships_to ON relationships(to_person_id);
CREATE INDEX idx_relationships_type ON relationships(relationship_type);
CREATE INDEX idx_relationships_both ON relationships(from_person_id, to_person_id);
```

**Usage:**
- Graph edges for traversal
- Directed: parent→child, child→parent stored as two rows
- `is_inferred` distinguishes explicit vs derived relationships
- Use recursive SQL for multi-hop traversal

---

### sources

Normalized source records and provenance references.

```sql
CREATE TABLE sources (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_type TEXT NOT NULL CHECK (source_type IN ('gedcom', 'wikitree', 'document', 'manual', 'other')),
  citation_text TEXT NOT NULL,
  source_detail_json JSONB,
  imported_from TEXT,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_sources_type ON sources(source_type);
```

**Usage:**
- One row per source citation
- `citation_text` is human-readable citation
- `source_detail_json` stores structured metadata
- `imported_from` tracks original file or system

---

### external_identities

Links from canonical local people to external systems (GEDCOM, WikiTree).

```sql
CREATE TABLE external_identities (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  person_id UUID NOT NULL REFERENCES people(id) ON DELETE CASCADE,
  provider TEXT NOT NULL CHECK (provider IN ('gedcom', 'wikitree', 'familysearch', 'findagrave', 'other')),
  external_key TEXT NOT NULL,
  visibility_scope TEXT,
  imported_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  last_seen_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_external_identities_person ON external_identities(person_id);
CREATE INDEX idx_external_identities_provider ON external_identities(provider, external_key);
CREATE UNIQUE INDEX idx_external_identities_unique ON external_identities(provider, external_key, person_id);
```

**Usage:**
- Links local `people` to GEDCOM `@I123@` IDs and WikiTree `Smith-123` profiles
- Only confirmed matches go here (not search candidates)
- `visibility_scope` stores privacy level from WikiTree

---

### wikitree_dump_versions

Tracks WikiTree weekly database dump versions.

```sql
CREATE TABLE wikitree_dump_versions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  dump_date DATE NOT NULL UNIQUE,
  downloaded_at TIMESTAMP WITH TIME ZONE,
  loaded_at TIMESTAMP WITH TIME ZONE,
  record_count BIGINT,
  marriage_count BIGINT,
  status TEXT NOT NULL CHECK (status IN ('downloading', 'loading', 'ready', 'failed')),
  is_current BOOLEAN NOT NULL DEFAULT FALSE,
  error_message TEXT,
  file_size_bytes BIGINT,
  file_sha256 TEXT,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_wikitree_dump_versions_current ON wikitree_dump_versions(is_current);
CREATE INDEX idx_wikitree_dump_versions_status ON wikitree_dump_versions(status);
```

**Usage:**
- One row per weekly dump
- Only one dump should have `is_current = TRUE`
- Ingestion app creates row when download starts, updates when loaded
- API/worker queries current dump for search

---

### wikitree_dump_people

Local cache of WikiTree public profiles from weekly dumps.

```sql
CREATE TABLE wikitree_dump_people (
  user_id INTEGER NOT NULL,
  dump_version_id UUID NOT NULL REFERENCES wikitree_dump_versions(id) ON DELETE CASCADE,
  wikitree_id TEXT NOT NULL,
  first_name TEXT,
  last_name_birth TEXT,
  last_name_current TEXT,
  birth_date TEXT,
  death_date TEXT,
  birth_location TEXT,
  death_location TEXT,
  father_id INTEGER,
  mother_id INTEGER,
  gender TEXT,
  privacy_level INTEGER,
  photo_url TEXT,
  is_connected BOOLEAN,
  PRIMARY KEY (user_id, dump_version_id)
);

CREATE INDEX idx_wikitree_dump_people_wikitree_id ON wikitree_dump_people(wikitree_id);
CREATE INDEX idx_wikitree_dump_people_name ON wikitree_dump_people(first_name, last_name_birth);
CREATE INDEX idx_wikitree_dump_people_birth ON wikitree_dump_people(birth_date, birth_location);
CREATE INDEX idx_wikitree_dump_people_parents ON wikitree_dump_people(father_id, mother_id);
CREATE INDEX idx_wikitree_dump_people_version ON wikitree_dump_people(dump_version_id);
```

**Usage:**
- Loaded by ingestion app from WikiTree TSV dumps
- `user_id` is WikiTree's internal integer ID
- Fast local search without API calls
- Privacy-aware: private profiles show decades instead of exact dates

---

### wikitree_dump_marriages

Local cache of WikiTree marriage relationships from weekly dumps.

```sql
CREATE TABLE wikitree_dump_marriages (
  user_id1 INTEGER NOT NULL,
  user_id2 INTEGER NOT NULL,
  dump_version_id UUID NOT NULL REFERENCES wikitree_dump_versions(id) ON DELETE CASCADE,
  marriage_date TEXT,
  marriage_location TEXT,
  PRIMARY KEY (user_id1, user_id2, dump_version_id)
);

CREATE INDEX idx_wikitree_dump_marriages_version ON wikitree_dump_marriages(dump_version_id);
```

**Usage:**
- Loaded by ingestion app from WikiTree marriage dumps
- Links spouses by WikiTree user IDs
- Used for relationship-based search improvements

---

### wikitree_search_runs

Cached per-person WikiTree search attempts with query plans and outcomes.

```sql
CREATE TABLE wikitree_search_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  import_job_id UUID REFERENCES import_jobs(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
  subject_person_id UUID NOT NULL REFERENCES people(id) ON DELETE CASCADE,
  used_dump_version_id UUID REFERENCES wikitree_dump_versions(id) ON DELETE SET NULL,
  used_api_call BOOLEAN NOT NULL DEFAULT FALSE,
  status TEXT NOT NULL CHECK (status IN ('pending', 'searching', 'completed', 'failed')),
  outcome TEXT CHECK (outcome IN ('exact_match', 'candidates_found', 'no_match', 'error')),
  query_plan_json JSONB,
  api_status_json JSONB,
  searched_at TIMESTAMP WITH TIME ZONE,
  expires_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_wikitree_search_runs_person ON wikitree_search_runs(subject_person_id);
CREATE INDEX idx_wikitree_search_runs_job ON wikitree_search_runs(import_job_id);
CREATE INDEX idx_wikitree_search_runs_user ON wikitree_search_runs(user_id);
```

**Usage:**
- One row per WikiTree search attempt for a person
- Hybrid search: local dump first, API supplement if needed
- `query_plan_json` records search strategy (dump vs API)
- `expires_at` for cache invalidation
- Does not create fake WikiTree people - stores unconfirmed candidates separately

---

### wikitree_search_candidates

Ranked candidate summaries returned from a search run.

```sql
CREATE TABLE wikitree_search_candidates (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  search_run_id UUID NOT NULL REFERENCES wikitree_search_runs(id) ON DELETE CASCADE,
  matched_person_id UUID REFERENCES people(id) ON DELETE SET NULL,
  rank INTEGER NOT NULL,
  wikitree_key TEXT NOT NULL,
  score NUMERIC(5,2) NOT NULL,
  classification TEXT NOT NULL CHECK (classification IN ('exact', 'likely', 'possible', 'unlikely')),
  summary_json JSONB NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_wikitree_search_candidates_run ON wikitree_search_candidates(search_run_id);
CREATE INDEX idx_wikitree_search_candidates_rank ON wikitree_search_candidates(search_run_id, rank);
CREATE INDEX idx_wikitree_search_candidates_wikitree_key ON wikitree_search_candidates(wikitree_key);
```

**Usage:**
- Ranked search results for review
- `wikitree_key` is WikiTree ID (e.g., `Smith-123`)
- `score` is confidence (0.00 - 1.00)
- `summary_json` stores name, dates, places for display
- `matched_person_id` populated after human confirmation

---

### match_reviews

Snapshot-backed review receipts for candidate matching decisions.

```sql
CREATE TABLE match_reviews (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  import_job_id UUID REFERENCES import_jobs(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
  subject_person_id UUID NOT NULL REFERENCES people(id) ON DELETE CASCADE,
  candidate_person_id UUID REFERENCES people(id) ON DELETE SET NULL,
  status TEXT NOT NULL CHECK (status IN ('pending', 'approved', 'rejected', 'deferred', 'auto_derived')),
  classification TEXT NOT NULL CHECK (classification IN ('exact', 'likely', 'possible', 'unlikely', 'no_match')),
  score NUMERIC(5,2),
  derived_from_review_id UUID REFERENCES match_reviews(id) ON DELETE SET NULL,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  decided_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_match_reviews_user ON match_reviews(user_id);
CREATE INDEX idx_match_reviews_subject ON match_reviews(subject_person_id);
CREATE INDEX idx_match_reviews_candidate ON match_reviews(candidate_person_id);
CREATE INDEX idx_match_reviews_status ON match_reviews(status);
CREATE INDEX idx_match_reviews_job ON match_reviews(import_job_id);
```

**Usage:**
- Immutable record of human matching decisions
- `status = 'approved'` means confirmed match
- `derived_from_review_id` for auto-derived matches (e.g., spouse of confirmed match)
- Review receipts preserve why decision was made at that time

---

### evidence_packets

Frozen evidence summaries and provenance attached to a review record.

```sql
CREATE TABLE evidence_packets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  match_review_id UUID NOT NULL REFERENCES match_reviews(id) ON DELETE CASCADE,
  summary_json JSONB NOT NULL,
  provenance_json JSONB NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_evidence_packets_review ON evidence_packets(match_review_id);
```

**Usage:**
- Frozen snapshot of evidence at time of review
- `summary_json` stores matched/conflicting fields
- `provenance_json` stores source references for each fact
- Never modified after creation (immutable audit trail)

**Evidence Packet Structure:**
```json
{
  "gedcom_person": {"name": "John Smith", "birth": "1850"},
  "wikitree_person": {"name": "John Smith", "birth": "1850"},
  "matched_fields": ["name", "birth_year", "father_name"],
  "conflicting_fields": [],
  "confidence": 0.95,
  "reviewer_notes": "Exact match on name, birth, and father"
}
```

---

### sync_review_items

Later enrichment queue items for already-matched profiles.

```sql
CREATE TABLE sync_review_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
  person_id UUID NOT NULL REFERENCES people(id) ON DELETE CASCADE,
  match_review_id UUID REFERENCES match_reviews(id) ON DELETE SET NULL,
  status TEXT NOT NULL CHECK (status IN ('pending', 'in_progress', 'completed', 'skipped')),
  diff_json JSONB NOT NULL,
  provenance_json JSONB NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  reviewed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_sync_review_items_user ON sync_review_items(user_id);
CREATE INDEX idx_sync_review_items_person ON sync_review_items(person_id);
CREATE INDEX idx_sync_review_items_status ON sync_review_items(status);
```

**Usage:**
- Queue for GEDCOM facts not yet in WikiTree
- `diff_json` stores facts to potentially add
- `provenance_json` stores source references
- Reviewed later after initial matching is complete

---

## State Machine Definitions

### Import Job Status

Valid states and transitions:

```
uploaded → queued → in_progress → completed
                   ↓            ↓
                 paused      failed
                   ↓
                cancelled
```

- `uploaded`: File received, metadata stored
- `queued`: Ready for worker to claim
- `in_progress`: Worker actively processing
- `paused`: User paused, resumable
- `completed`: All stages done
- `failed`: Unrecoverable error
- `cancelled`: User cancelled

### Import Job Stage Status

```
pending → in_progress → completed
            ↓        ↓
          failed   retrying
```

- `pending`: Not yet started
- `in_progress`: Worker processing
- `completed`: Stage done
- `failed`: Error, may retry
- `retrying`: Retry attempt in progress

### Match Review Status

```
pending → approved
       → rejected
       → deferred
       → auto_derived (system-generated)
```

- `pending`: Awaiting human decision
- `approved`: Confirmed match
- `rejected`: Not a match
- `deferred`: Decide later
- `auto_derived`: System inferred from other matches

## Migration Strategy

Migrations will be numbered and applied sequentially:

1. `001_initial_schema.sql` - Core tables (app_users through sources)
2. `002_external_identities.sql` - External system links
3. `003_wikitree_dump_tables.sql` - Dump cache tables
4. `004_search_and_matching.sql` - Search runs, candidates, reviews
5. `005_evidence_and_sync.sql` - Evidence packets and sync review

Each migration should be idempotent and include rollback instructions.

## Indexes and Performance

**High-traffic queries:**
- Person search by name: `idx_person_names_normalized`
- Relationship traversal: `idx_relationships_from`, `idx_relationships_to`
- WikiTree dump search: `idx_wikitree_dump_people_name`, `idx_wikitree_dump_people_birth`
- Job queue claiming: `idx_import_jobs_status`, `idx_import_jobs_claimed_by`

**Composite indexes for common filters:**
- `idx_relationships_both` for bidirectional lookups
- `idx_wikitree_dump_people_name` for first+last name searches

## Future Considerations

**Not in v1, but planned:**
- Full-text search indexes for person names and places
- Partitioning for `wikitree_dump_people` by dump version
- Materialized views for complex relationship queries
- Connection pooling configuration for worker processes
- Multi-tenant support (currently single-user local-first)

## References

- Design doc: [`office-hours-design.md`](./office-hours-design.md)
- Implementation plan: [`implementation-plan.md`](./implementation-plan.md)
- State machines: See PR2 in implementation plan
