"""Database models using SQLModel (Pydantic + SQLAlchemy).

These models serve as:
- API request/response models (Pydantic)
- Database tables (SQLAlchemy ORM)
- Single source of truth for the schema
"""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Enum as SQLEnum
from sqlmodel import JSON, Column, Field, SQLModel

from api.state_machines import (
    ImportJobStageStatus,
    ImportJobStatus,
    MatchReviewStatus,
)

# ============================================================================
# Authentication & Session Management
# ============================================================================


class AppUser(SQLModel, table=True):
    """Google-authenticated application user."""

    __tablename__ = 'app_users'  # pyrefly: ignore[bad-override]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    google_subject: str = Field(unique=True, index=True)
    email: str = Field(index=True)
    display_name: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class WikiTreeConnection(SQLModel, table=True):
    """Per-user WikiTree authentication state."""

    __tablename__ = 'wikitree_connections'  # pyrefly: ignore[bad-override]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key='app_users.id', index=True, unique=True)
    wikitree_user_key: str | None = None
    status: str  # connected | disconnected | expired | failed
    session_ref: str | None = None
    connected_at: datetime | None = None
    expires_at: datetime | None = None
    last_verified_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# Import Jobs & Staging
# ============================================================================


class ImportJob(SQLModel, table=True):
    """GEDCOM import job state and metadata."""

    __tablename__ = 'import_jobs'  # pyrefly: ignore[bad-override]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key='app_users.id', index=True)
    source_type: str  # gedcom | wikitree-export | manual
    original_filename: str
    stored_path: str
    file_size_bytes: int
    content_sha256: str
    status: str = Field(
        sa_column=Column(SQLEnum(ImportJobStatus), index=True, nullable=False)
    )
    current_stage: str | None = None
    claimed_by: str | None = Field(default=None, index=True)
    claimed_at: datetime | None = None
    upload_completed_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ImportJobStage(SQLModel, table=True):
    """Stage-level checkpoint and retry state."""

    __tablename__ = 'import_job_stages'  # pyrefly: ignore[bad-override]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    import_job_id: UUID = Field(foreign_key='import_jobs.id', index=True)
    stage_name: str  # parse | normalize | search | match | review
    status: str = Field(
        sa_column=Column(
            SQLEnum(ImportJobStageStatus), index=True, nullable=False
        )
    )
    checkpoint_json: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSON)
    )
    lease_expires_at: datetime | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    retry_count: int = 0


# ============================================================================
# Canonical Data Model
# ============================================================================


class Person(SQLModel, table=True):
    """Canonical person record used by all workflows."""

    __tablename__ = 'people'  # pyrefly: ignore[bad-override]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    primary_name: str = Field(index=True)
    birth_year: int | None = Field(default=None, index=True)
    death_year: int | None = None
    is_living: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class PersonName(SQLModel, table=True):
    """Structured name with normalization for fuzzy matching."""

    __tablename__ = 'person_names'  # pyrefly: ignore[bad-override]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    person_id: UUID = Field(foreign_key='people.id', index=True)
    name_type: str  # primary | birth | married | alternate | aka
    full_name: str
    given_names: str | None = None
    surname: str | None = Field(default=None, index=True)
    normalized_name: str = Field(index=True)


class PersonFact(SQLModel, table=True):
    """Fact like birth, death, place, occupation."""

    __tablename__ = 'person_facts'  # pyrefly: ignore[bad-override]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    person_id: UUID = Field(foreign_key='people.id', index=True)
    fact_type: str = Field(
        index=True
    )  # birth | death | christening | burial | occupation | ...
    fact_value_json: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSON)
    )
    date_text: str | None = None
    place_text: str | None = None
    source_id: UUID | None = Field(
        default=None, foreign_key='sources.id', index=True
    )


class Relationship(SQLModel, table=True):
    """Directed edge between two people."""

    __tablename__ = 'relationships'  # pyrefly: ignore[bad-override]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    from_person_id: UUID = Field(foreign_key='people.id', index=True)
    to_person_id: UUID = Field(foreign_key='people.id', index=True)
    relationship_type: str = Field(
        index=True
    )  # parent | child | spouse | sibling | partner
    source_id: UUID | None = Field(default=None, foreign_key='sources.id')
    is_inferred: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Source(SQLModel, table=True):
    """Citation record with provenance tracking."""

    __tablename__ = 'sources'  # pyrefly: ignore[bad-override]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    import_job_id: UUID | None = Field(
        default=None, foreign_key='import_jobs.id', index=True
    )
    source_type: str = Field(
        index=True
    )  # gedcom | wikitree | manual | user_note
    citation_text: str | None = None
    source_detail_json: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSON)
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# External System Integration
# ============================================================================


class ExternalIdentity(SQLModel, table=True):
    """Links local people to external systems (GEDCOM, WikiTree)."""

    __tablename__ = 'external_identities'  # pyrefly: ignore[bad-override]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    person_id: UUID = Field(foreign_key='people.id', index=True)
    import_job_id: UUID | None = Field(
        default=None, foreign_key='import_jobs.id', index=True
    )
    provider: str = Field(
        index=True
    )  # gedcom | wikitree | familysearch | findagrave | other
    external_key: str = Field(index=True)
    visibility_scope: str | None = None
    imported_at: datetime = Field(default_factory=datetime.utcnow)
    last_seen_at: datetime = Field(default_factory=datetime.utcnow)


class WikiTreeDumpVersion(SQLModel, table=True):
    """Tracks WikiTree weekly database dump versions."""

    __tablename__ = 'wikitree_dump_versions'  # pyrefly: ignore[bad-override]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    dump_date: datetime = Field(unique=True, sa_column_kwargs={'type_': 'DATE'})
    downloaded_at: datetime | None = None
    loaded_at: datetime | None = None
    record_count: int | None = None
    marriage_count: int | None = None
    status: str = Field(index=True)  # downloading | loading | ready | failed
    is_current: bool = Field(default=False, index=True)
    error_message: str | None = None
    file_size_bytes: int | None = None
    file_sha256: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class WikiTreeDumpPerson(SQLModel, table=True):
    """Local cache of WikiTree public profiles from weekly dumps."""

    __tablename__ = 'wikitree_dump_people'  # pyrefly: ignore[bad-override]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: int = Field(index=True)  # WikiTree User ID (integer)
    wikitree_id: str = Field(unique=True, index=True)  # WikiTree-123 format
    first_name: str | None = Field(default=None, index=True)
    middle_name: str | None = None
    last_name_birth: str | None = Field(default=None, index=True)
    last_name_current: str | None = None
    birth_date: str | None = Field(default=None, index=True)
    death_date: str | None = None
    birth_location: str | None = Field(default=None, index=True)
    death_location: str | None = None
    father_id: int | None = Field(default=None, index=True)
    mother_id: int | None = Field(default=None, index=True)
    gender: str | None = None
    privacy_level: int | None = None  # 10-60
    photo_url: str | None = None
    is_connected: bool = Field(default=False)
    extended_data: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSON)
    )
    dump_version_id: UUID | None = Field(
        default=None, foreign_key='wikitree_dump_versions.id', index=True
    )


class WikiTreeDumpMarriage(SQLModel, table=True):
    """Cached WikiTree marriages from weekly dumps."""

    __tablename__ = 'wikitree_dump_marriages'  # pyrefly: ignore[bad-override]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id1: int = Field(index=True)
    user_id2: int = Field(index=True)
    marriage_date: str | None = None
    marriage_location: str | None = None
    dump_version_id: UUID | None = Field(
        default=None, foreign_key='wikitree_dump_versions.id', index=True
    )


# ============================================================================
# Search & Matching
# ============================================================================


class WikiTreeSearchRun(SQLModel, table=True):
    """Cached per-person WikiTree search attempts with query plans."""

    __tablename__ = 'wikitree_search_runs'  # pyrefly: ignore[bad-override]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    import_job_id: UUID | None = Field(
        default=None, foreign_key='import_jobs.id', index=True
    )
    user_id: UUID = Field(foreign_key='app_users.id', index=True)
    subject_person_id: UUID = Field(foreign_key='people.id', index=True)
    used_dump_version_id: UUID | None = Field(
        default=None, foreign_key='wikitree_dump_versions.id'
    )
    used_api_call: bool = Field(default=False)
    status: str  # pending | searching | completed | failed
    outcome: str | None = (
        None  # exact_match | candidates_found | no_match | error
    )
    query_plan_json: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSON)
    )
    api_status_json: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSON)
    )
    searched_at: datetime | None = None
    expires_at: datetime | None = None


class WikiTreeSearchCandidate(SQLModel, table=True):
    """Ranked candidate summaries returned from a search run."""

    __tablename__ = 'wikitree_search_candidates'  # pyrefly: ignore[bad-override]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    search_run_id: UUID = Field(
        foreign_key='wikitree_search_runs.id', index=True
    )
    matched_person_id: UUID | None = Field(
        default=None, foreign_key='people.id'
    )
    rank: int
    wikitree_key: str = Field(index=True)
    score: float  # 0.00 - 1.00
    classification: str  # exact | likely | possible | unlikely
    summary_json: dict[str, Any] = Field(sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)


class MatchReview(SQLModel, table=True):
    """Snapshot-backed review receipts for matching decisions."""

    __tablename__ = 'match_reviews'  # pyrefly: ignore[bad-override]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    import_job_id: UUID | None = Field(
        default=None, foreign_key='import_jobs.id', index=True
    )
    user_id: UUID = Field(foreign_key='app_users.id', index=True)
    subject_person_id: UUID = Field(foreign_key='people.id', index=True)
    candidate_person_id: UUID | None = Field(
        default=None, foreign_key='people.id', index=True
    )
    status: MatchReviewStatus = Field(
        sa_column=Column(SQLEnum(MatchReviewStatus), index=True, nullable=False)
    )
    classification: str  # exact | likely | possible | unlikely | no_match
    score: float | None = None
    derived_from_review_id: UUID | None = Field(
        default=None, foreign_key='match_reviews.id'
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    decided_at: datetime | None = None


class EvidencePacket(SQLModel, table=True):
    """Frozen evidence summaries attached to a review record."""

    __tablename__ = 'evidence_packets'  # pyrefly: ignore[bad-override]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    match_review_id: UUID = Field(foreign_key='match_reviews.id', index=True)
    summary_json: dict[str, Any] = Field(sa_column=Column(JSON))
    provenance_json: dict[str, Any] = Field(sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SyncReviewItem(SQLModel, table=True):
    """Later enrichment queue items for already-matched profiles."""

    __tablename__ = 'sync_review_items'  # pyrefly: ignore[bad-override]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key='app_users.id', index=True)
    person_id: UUID = Field(foreign_key='people.id', index=True)
    match_review_id: UUID | None = Field(
        default=None, foreign_key='match_reviews.id'
    )
    status: str = Field(
        index=True
    )  # pending | in_progress | completed | skipped
    diff_json: dict[str, Any] = Field(sa_column=Column(JSON))
    provenance_json: dict[str, Any] = Field(sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    reviewed_at: datetime | None = None
