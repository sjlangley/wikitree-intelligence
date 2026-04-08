"""State machine definitions for import jobs and match reviews.

Defines valid states and allowed transitions for:
- Import job lifecycle
- Import stage lifecycle
- Match review lifecycle
"""

from enum import StrEnum

# ============================================================================
# Import Job States
# ============================================================================


class ImportJobStatus(StrEnum):
    """Valid states for import job lifecycle."""

    UPLOADED = 'uploaded'
    QUEUED = 'queued'
    IN_PROGRESS = 'in_progress'
    PAUSED = 'paused'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'


IMPORT_JOB_TRANSITIONS: dict[ImportJobStatus, set[ImportJobStatus]] = {
    ImportJobStatus.UPLOADED: {ImportJobStatus.QUEUED},
    ImportJobStatus.QUEUED: {
        ImportJobStatus.IN_PROGRESS,
        ImportJobStatus.CANCELLED,
    },
    ImportJobStatus.IN_PROGRESS: {
        ImportJobStatus.PAUSED,
        ImportJobStatus.COMPLETED,
        ImportJobStatus.FAILED,
    },
    ImportJobStatus.PAUSED: {
        ImportJobStatus.IN_PROGRESS,
        ImportJobStatus.CANCELLED,
    },
    ImportJobStatus.COMPLETED: set(),  # Terminal state
    ImportJobStatus.FAILED: set(),  # Terminal state
    ImportJobStatus.CANCELLED: set(),  # Terminal state
}


def is_valid_import_job_transition(from_status: str, to_status: str) -> bool:
    """Check if a state transition is valid for import jobs.

    Args:
        from_status: Current status string
        to_status: Desired status string

    Returns:
        True if transition is allowed
    """
    try:
        from_state = ImportJobStatus(from_status)
        to_state = ImportJobStatus(to_status)
    except ValueError:
        return False
    return to_state in IMPORT_JOB_TRANSITIONS[from_state]


def get_import_job_terminal_states() -> set[str]:
    """Get terminal states for import jobs (no outgoing transitions).

    Returns:
        Set of terminal status string values
    """
    return {
        status.value
        for status, transitions in IMPORT_JOB_TRANSITIONS.items()
        if not transitions
    }


# ============================================================================
# Import Job Stage States
# ============================================================================


class ImportJobStageStatus(StrEnum):
    """Valid states for import job stage lifecycle."""

    PENDING = 'pending'
    IN_PROGRESS = 'in_progress'
    RETRYING = 'retrying'
    COMPLETED = 'completed'
    FAILED = 'failed'


IMPORT_JOB_STAGE_TRANSITIONS: dict[
    ImportJobStageStatus, set[ImportJobStageStatus]
] = {
    ImportJobStageStatus.PENDING: {ImportJobStageStatus.IN_PROGRESS},
    ImportJobStageStatus.IN_PROGRESS: {
        ImportJobStageStatus.COMPLETED,
        ImportJobStageStatus.FAILED,
        ImportJobStageStatus.RETRYING,
    },
    ImportJobStageStatus.RETRYING: {
        ImportJobStageStatus.IN_PROGRESS,
        ImportJobStageStatus.FAILED,
    },
    ImportJobStageStatus.COMPLETED: set(),  # Terminal state
    ImportJobStageStatus.FAILED: {ImportJobStageStatus.RETRYING},
}


def is_valid_import_job_stage_transition(
    from_status: str, to_status: str
) -> bool:
    """Check if a state transition is valid for import job stages.

    Args:
        from_status: Current status string
        to_status: Desired status string

    Returns:
        True if transition is allowed
    """
    try:
        from_state = ImportJobStageStatus(from_status)
        to_state = ImportJobStageStatus(to_status)
    except ValueError:
        return False
    return to_state in IMPORT_JOB_STAGE_TRANSITIONS[from_state]


def get_import_job_stage_terminal_states() -> set[str]:
    """Get terminal states for import job stages.

    Returns:
        Set of terminal status string values (currently only 'completed')
    """
    return {
        status.value
        for status, transitions in IMPORT_JOB_STAGE_TRANSITIONS.items()
        if not transitions
    }


# ============================================================================
# Match Review States
# ============================================================================


class MatchReviewStatus(StrEnum):
    """Valid states for match review lifecycle."""

    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    DEFERRED = 'deferred'
    AUTO_DERIVED = 'auto_derived'


MATCH_REVIEW_TRANSITIONS: dict[MatchReviewStatus, set[MatchReviewStatus]] = {
    MatchReviewStatus.PENDING: {
        MatchReviewStatus.APPROVED,
        MatchReviewStatus.REJECTED,
        MatchReviewStatus.DEFERRED,
    },
    MatchReviewStatus.APPROVED: set(),  # Terminal state
    MatchReviewStatus.REJECTED: set(),  # Terminal state
    MatchReviewStatus.DEFERRED: {
        MatchReviewStatus.APPROVED,
        MatchReviewStatus.REJECTED,
    },
    MatchReviewStatus.AUTO_DERIVED: set(),  # Terminal state
}


def is_valid_match_review_transition(from_status: str, to_status: str) -> bool:
    """Check if a state transition is valid for match reviews.

    Args:
        from_status: Current status string
        to_status: Desired status string

    Returns:
        True if transition is allowed
    """
    try:
        from_state = MatchReviewStatus(from_status)
        to_state = MatchReviewStatus(to_status)
    except ValueError:
        return False
    return to_state in MATCH_REVIEW_TRANSITIONS[from_state]


def get_match_review_terminal_states() -> set[str]:
    """Get terminal states for match reviews.

    Returns:
        Set of terminal status string values
    """
    return {
        status.value
        for status, transitions in MATCH_REVIEW_TRANSITIONS.items()
        if not transitions
    }
