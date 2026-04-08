"""Database models using SQLModel (Pydantic + SQLAlchemy).

These models serve as:
- API request/response models (Pydantic)
- Database tables (SQLAlchemy ORM)
- Single source of truth for the schema
"""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlmodel import JSON, Column, Field, SQLModel

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
    status: str = Field(index=True)  # uploaded | queued | in_progress | ...
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
    status: str = Field(index=True)  # pending | in_progress | completed | ...
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
