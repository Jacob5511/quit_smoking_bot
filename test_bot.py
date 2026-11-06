import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from bot import (
    BotConfig,
    ModerationStore,
    Profile,
    get_sender,
    is_keyword_spam,
    load_bot_configs,
    profile_for_chat,
)


class ConfigurationTests(unittest.TestCase):
    def test_chat_can_override_default_profile(self):
        profiles = {"default": Profile("default"), "other": Profile("other")}
        config = BotConfig("one", "token", 1, "default", {"-1007": "other"})
        self.assertEqual(profile_for_chat(config, profiles, -1007).name, "other")
        self.assertEqual(profile_for_chat(config, profiles, -1008).name, "default")

    def test_bot_secrets_are_loaded_indirectly(self):
        raw = json.dumps([{
            "name": "one",
            "token_env": "TEST_BOT_TOKEN",
            "admin_id_env": "TEST_ADMIN_ID",
            "default_profile": "default",
        }])
        with patch.dict(os.environ, {
            "BOTS_CONFIG_JSON": raw,
            "TEST_BOT_TOKEN": "secret",
            "TEST_ADMIN_ID": "42",
        }, clear=False):
            configs = load_bot_configs({"default": Profile("default")})
        self.assertEqual(configs[0].token, "secret")
        self.assertEqual(configs[0].admin_id, 42)

    def test_duplicate_token_starts_only_one_poller(self):
        raw = json.dumps([
            {
                "name": "smoking",
                "token_env": "SMOKING_TOKEN",
                "admin_id_env": "ADMIN_ID",
                "default_profile": "quit_smoking",
            },
            {
                "name": "drinking",
                "token_env": "DRINKING_TOKEN",
                "admin_id_env": "ADMIN_ID",
                "default_profile": "quit_drinking",
            },
        ])
        with patch.dict(os.environ, {
            "BOTS_CONFIG_JSON": raw,
            "SMOKING_TOKEN": "same-secret",
            "DRINKING_TOKEN": "same-secret",
            "ADMIN_ID": "42",
        }, clear=False):
            configs = load_bot_configs({
                "quit_smoking": Profile("quit_smoking"),
                "quit_drinking": Profile("quit_drinking"),
            })
        self.assertEqual(len(configs), 1)
        self.assertEqual(configs[0].default_profile, "quit_smoking")

    def test_keyword_matching_is_case_insensitive(self):
        profile = Profile("test", keywords=("Работа",))
        self.assertTrue(is_keyword_spam("РАБОТА из дома", profile))
        self.assertFalse(is_keyword_spam("обычный разговор", profile))

    def test_bot_account_is_a_supported_sender(self):
        message = Mock()
        message.sender_chat = None
        message.from_user = Mock(
            id=77,
            is_bot=True,
            full_name="Spam Bot",
            username="spam_bot",
        )
        sender = get_sender(message)
        self.assertEqual((sender.kind, sender.id), ("bot", 77))

    def test_channel_identity_takes_priority_over_fallback_user(self):
        message = Mock()
        message.sender_chat = Mock(
            id=-1009,
            title="Spam Channel",
            full_name="Spam Channel",
            username="spam_channel",
        )
        message.from_user = Mock(id=1087968824, is_bot=True)
        sender = get_sender(message)
        self.assertEqual((sender.kind, sender.id), ("sender_chat", -1009))


class StoreTests(unittest.TestCase):
    def test_chat_profile_override_survives_reopening_database(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / "moderation.db")
            store = ModerationStore(path)
            store.set_chat_profile("bot", -1007, "quit_drinking")
            store.close()
            reopened = ModerationStore(path)
            self.assertEqual(reopened.get_chat_profile("bot", -1007), "quit_drinking")
            config = BotConfig("bot", "token", 1, "quit_smoking")
            profiles = {
                "quit_smoking": Profile("quit_smoking"),
                "quit_drinking": Profile("quit_drinking"),
            }
            self.assertEqual(
                profile_for_chat(config, profiles, -1007, reopened).name,
                "quit_drinking",
            )
            reopened.close()

    def test_action_survives_reopening_database(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / "moderation.db")
            store = ModerationStore(path)
            action_id = store.add(
                "bot", -100, "sender_chat", -200, "channel", "message", 100
            )
            store.close()
            reopened = ModerationStore(path)
            pending = reopened.get_pending(action_id, "bot")
            self.assertEqual(pending["sender_id"], -200)
            self.assertEqual(pending["sender_type"], "sender_chat")
            reopened.finish(action_id, "unblocked")
            self.assertIsNone(reopened.get_pending(action_id, "bot"))
            reopened.close()

    def test_expired_review_is_finalized_only_once(self):
        with tempfile.TemporaryDirectory() as folder:
            store = ModerationStore(str(Path(folder) / "moderation.db"))
            action_id = store.add("bot", -100, "user", 7, "user", "spam", 10)
            store.attach_admin_message(action_id, 42, 99)
            expired = store.expired_pending("bot", 10)
            self.assertEqual(expired[0]["admin_message_id"], 99)
            self.assertTrue(store.finish_if_pending(action_id, "kept_muted"))
            self.assertFalse(store.finish_if_pending(action_id, "unblocked"))
            self.assertEqual(store.expired_pending("bot", 11), [])
            store.close()


if __name__ == "__main__":
    unittest.main()

