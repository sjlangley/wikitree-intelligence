"""Tests for match review state machine transitions."""

from api.state_machines import (
    MATCH_REVIEW_TRANSITIONS,
    get_match_review_terminal_states,
    is_valid_match_review_transition,
)


class TestMatchReviewStates:
    """Test match review state transitions."""

    def test_pending_to_approved(self):
        """Test valid transition from pending to approved."""
        assert is_valid_match_review_transition('pending', 'approved')

    def test_pending_to_rejected(self):
        """Test valid transition from pending to rejected."""
        assert is_valid_match_review_transition('pending', 'rejected')

    def test_pending_to_deferred(self):
        """Test valid transition from pending to deferred."""
        assert is_valid_match_review_transition('pending', 'deferred')

    def test_deferred_to_approved(self):
        """Test valid transition from deferred to approved."""
        assert is_valid_match_review_transition('deferred', 'approved')

    def test_deferred_to_rejected(self):
        """Test valid transition from deferred to rejected."""
        assert is_valid_match_review_transition('deferred', 'rejected')

    def test_invalid_approved_to_rejected(self):
        """Test approved is terminal - cannot change decision."""
        assert not is_valid_match_review_transition('approved', 'rejected')

    def test_invalid_approved_to_pending(self):
        """Test approved is terminal - cannot revert."""
        assert not is_valid_match_review_transition('approved', 'pending')

    def test_invalid_rejected_to_approved(self):
        """Test rejected is terminal - cannot change decision."""
        assert not is_valid_match_review_transition('rejected', 'approved')

    def test_invalid_rejected_to_pending(self):
        """Test rejected is terminal - cannot revert."""
        assert not is_valid_match_review_transition('rejected', 'pending')

    def test_invalid_auto_derived_to_approved(self):
        """Test auto_derived is terminal - system-generated."""
        assert not is_valid_match_review_transition('auto_derived', 'approved')

    def test_invalid_auto_derived_to_rejected(self):
        """Test auto_derived is terminal - system-generated."""
        assert not is_valid_match_review_transition('auto_derived', 'rejected')

    def test_invalid_pending_to_auto_derived(self):
        """Test auto_derived cannot be set manually from pending."""
        assert not is_valid_match_review_transition('pending', 'auto_derived')

    def test_invalid_deferred_to_pending(self):
        """Test deferred cannot go back to pending."""
        assert not is_valid_match_review_transition('deferred', 'pending')

    def test_invalid_unknown_from_state(self):
        """Test transition from unknown state returns False."""
        assert not is_valid_match_review_transition('unknown', 'approved')

    def test_invalid_unknown_to_state(self):
        """Test transition to unknown state returns False."""
        assert not is_valid_match_review_transition('pending', 'unknown')

    def test_terminal_states(self):
        """Test terminal states have no outgoing transitions."""
        terminal = get_match_review_terminal_states()
        assert terminal == {'approved', 'rejected', 'auto_derived'}

        for state in terminal:
            assert MATCH_REVIEW_TRANSITIONS[state] == set()

    def test_deferred_is_not_terminal(self):
        """Test deferred reviews can be revisited."""
        assert 'deferred' not in get_match_review_terminal_states()
        assert MATCH_REVIEW_TRANSITIONS['deferred'] == {
            'approved',
            'rejected',
        }

    def test_all_states_have_transitions_defined(self):
        """Test all states are present in transition map."""
        expected_states = {
            'pending',
            'approved',
            'rejected',
            'deferred',
            'auto_derived',
        }
        assert set(MATCH_REVIEW_TRANSITIONS.keys()) == expected_states

    def test_immutable_decisions(self):
        """Test that approved/rejected decisions are immutable."""
        # Once approved, cannot change
        assert not is_valid_match_review_transition('approved', 'rejected')
        assert not is_valid_match_review_transition('approved', 'deferred')

        # Once rejected, cannot change
        assert not is_valid_match_review_transition('rejected', 'approved')
        assert not is_valid_match_review_transition('rejected', 'deferred')

    def test_deferred_workflow(self):
        """Test deferred reviews can eventually be decided."""
        # Can defer from pending
        assert is_valid_match_review_transition('pending', 'deferred')

        # Can later approve or reject deferred
        assert is_valid_match_review_transition('deferred', 'approved')
        assert is_valid_match_review_transition('deferred', 'rejected')

        # Cannot defer again (no self-loop)
        assert not is_valid_match_review_transition('deferred', 'deferred')
