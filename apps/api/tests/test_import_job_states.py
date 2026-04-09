"""Tests for import job state machine transitions."""

from api.state_machines import (
    IMPORT_JOB_STAGE_TRANSITIONS,
    IMPORT_JOB_TRANSITIONS,
    get_import_job_stage_terminal_states,
    get_import_job_terminal_states,
    is_valid_import_job_stage_transition,
    is_valid_import_job_transition,
)


class TestImportJobStates:
    """Test import job state transitions."""

    def test_uploaded_to_queued(self):
        """Test valid transition from uploaded to queued."""
        assert is_valid_import_job_transition('uploaded', 'queued')

    def test_queued_to_in_progress(self):
        """Test valid transition from queued to in_progress."""
        assert is_valid_import_job_transition('queued', 'in_progress')

    def test_queued_to_cancelled(self):
        """Test valid transition from queued to cancelled."""
        assert is_valid_import_job_transition('queued', 'cancelled')

    def test_in_progress_to_completed(self):
        """Test valid transition from in_progress to completed."""
        assert is_valid_import_job_transition('in_progress', 'completed')

    def test_in_progress_to_paused(self):
        """Test valid transition from in_progress to paused."""
        assert is_valid_import_job_transition('in_progress', 'paused')

    def test_in_progress_to_failed(self):
        """Test valid transition from in_progress to failed."""
        assert is_valid_import_job_transition('in_progress', 'failed')

    def test_paused_to_in_progress(self):
        """Test valid transition from paused to in_progress."""
        assert is_valid_import_job_transition('paused', 'in_progress')

    def test_paused_to_cancelled(self):
        """Test valid transition from paused to cancelled."""
        assert is_valid_import_job_transition('paused', 'cancelled')

    def test_invalid_uploaded_to_completed(self):
        """Test invalid jump from uploaded to completed."""
        assert not is_valid_import_job_transition('uploaded', 'completed')

    def test_invalid_queued_to_completed(self):
        """Test invalid jump from queued to completed."""
        assert not is_valid_import_job_transition('queued', 'completed')

    def test_invalid_completed_to_in_progress(self):
        """Test completed is terminal - cannot restart."""
        assert not is_valid_import_job_transition('completed', 'in_progress')

    def test_invalid_failed_to_in_progress(self):
        """Test failed is terminal - cannot restart."""
        assert not is_valid_import_job_transition('failed', 'in_progress')

    def test_invalid_cancelled_to_in_progress(self):
        """Test cancelled is terminal - cannot restart."""
        assert not is_valid_import_job_transition('cancelled', 'in_progress')

    def test_invalid_unknown_from_state(self):
        """Test transition from unknown state returns False."""
        assert not is_valid_import_job_transition('unknown', 'queued')

    def test_invalid_unknown_to_state(self):
        """Test transition to unknown state returns False."""
        assert not is_valid_import_job_transition('uploaded', 'unknown')

    def test_terminal_states(self):
        """Test terminal states have no outgoing transitions."""
        terminal = get_import_job_terminal_states()
        assert terminal == {'completed', 'failed', 'cancelled'}

        for state in terminal:
            assert IMPORT_JOB_TRANSITIONS[state] == set()

    def test_all_states_have_transitions_defined(self):
        """Test all states are present in transition map."""
        expected_states = {
            'uploaded',
            'queued',
            'in_progress',
            'paused',
            'completed',
            'failed',
            'cancelled',
        }
        assert set(IMPORT_JOB_TRANSITIONS.keys()) == expected_states


class TestImportJobStageStates:
    """Test import job stage state transitions."""

    def test_pending_to_in_progress(self):
        """Test valid transition from pending to in_progress."""
        assert is_valid_import_job_stage_transition('pending', 'in_progress')

    def test_in_progress_to_completed(self):
        """Test valid transition from in_progress to completed."""
        assert is_valid_import_job_stage_transition('in_progress', 'completed')

    def test_in_progress_to_failed(self):
        """Test valid transition from in_progress to failed."""
        assert is_valid_import_job_stage_transition('in_progress', 'failed')

    def test_in_progress_to_retrying(self):
        """Test valid transition from in_progress to retrying."""
        assert is_valid_import_job_stage_transition('in_progress', 'retrying')

    def test_failed_to_retrying(self):
        """Test valid transition from failed to retrying."""
        assert is_valid_import_job_stage_transition('failed', 'retrying')

    def test_retrying_to_in_progress(self):
        """Test valid transition from retrying to in_progress."""
        assert is_valid_import_job_stage_transition('retrying', 'in_progress')

    def test_retrying_to_failed(self):
        """Test valid transition from retrying to failed."""
        assert is_valid_import_job_stage_transition('retrying', 'failed')

    def test_invalid_pending_to_completed(self):
        """Test invalid jump from pending to completed."""
        assert not is_valid_import_job_stage_transition('pending', 'completed')

    def test_invalid_completed_to_in_progress(self):
        """Test completed is terminal - cannot restart."""
        assert not is_valid_import_job_stage_transition(
            'completed', 'in_progress'
        )

    def test_invalid_completed_to_retrying(self):
        """Test completed stages cannot be retried."""
        assert not is_valid_import_job_stage_transition('completed', 'retrying')

    def test_invalid_unknown_from_state(self):
        """Test transition from unknown state returns False."""
        assert not is_valid_import_job_stage_transition(
            'unknown', 'in_progress'
        )

    def test_invalid_unknown_to_state(self):
        """Test transition to unknown state returns False."""
        assert not is_valid_import_job_stage_transition('pending', 'unknown')

    def test_terminal_states(self):
        """Test terminal states have no outgoing transitions."""
        terminal = get_import_job_stage_terminal_states()
        assert terminal == {'completed'}

        for state in terminal:
            assert IMPORT_JOB_STAGE_TRANSITIONS[state] == set()

    def test_failed_is_not_terminal(self):
        """Test failed stages can be retried (not terminal)."""
        assert 'failed' not in get_import_job_stage_terminal_states()
        assert 'retrying' in IMPORT_JOB_STAGE_TRANSITIONS['failed']

    def test_all_states_have_transitions_defined(self):
        """Test all states are present in transition map."""
        expected_states = {
            'pending',
            'in_progress',
            'retrying',
            'completed',
            'failed',
        }
        assert set(IMPORT_JOB_STAGE_TRANSITIONS.keys()) == expected_states
