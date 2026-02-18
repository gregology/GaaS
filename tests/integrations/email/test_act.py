from unittest.mock import MagicMock, call

from app.integrations.email.act import _execute_action, SIMPLE_ACTIONS


class TestExecuteAction:
    def _mock_email(self):
        email = MagicMock()
        email.archive = MagicMock()
        email.spam = MagicMock()
        email.unsubscribe = MagicMock()
        email.draft_reply = MagicMock()
        return email

    def test_archive_calls_email_archive(self):
        email = self._mock_email()
        _execute_action(email, "archive")
        email.archive.assert_called_once()

    def test_spam_calls_email_spam(self):
        email = self._mock_email()
        _execute_action(email, "spam")
        email.spam.assert_called_once()

    def test_unsubscribe_calls_email_unsubscribe(self):
        email = self._mock_email()
        _execute_action(email, "unsubscribe")
        email.unsubscribe.assert_called_once()

    def test_draft_reply_calls_with_content(self):
        email = self._mock_email()
        _execute_action(email, {"draft_reply": "Thanks, I'll review."})
        email.draft_reply.assert_called_once_with("Thanks, I'll review.")

    def test_unknown_string_action_skipped(self):
        email = self._mock_email()
        _execute_action(email, "delete_everything")
        email.archive.assert_not_called()
        email.spam.assert_not_called()
        email.unsubscribe.assert_not_called()
        email.draft_reply.assert_not_called()

    def test_unknown_dict_action_skipped(self):
        email = self._mock_email()
        _execute_action(email, {"send_email": "to everyone"})
        email.draft_reply.assert_not_called()

    def test_simple_actions_set_is_bounded(self):
        """The set of simple actions is explicitly defined and should not grow
        without deliberate review of reversibility tiers."""
        assert SIMPLE_ACTIONS == {"archive", "spam", "unsubscribe"}
