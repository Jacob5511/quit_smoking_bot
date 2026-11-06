import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch
from types import SimpleNamespace

from bot import (
    BotConfig,
    ModerationStore,
    Profile,
    get_sender,
    is_keyword_spam,
    is_ai_spam,
    load_bot_configs,
    profile_for_chat,
    validate_bot_identity,
    build_application,
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

    def test_duplicate_token_is_rejected_instead_of_losing_a_profile(self):
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
            with self.assertRaisesRegex(ValueError, "share a token"):
                load_bot_configs({
                    "quit_smoking": Profile("quit_smoking"),
                    "quit_drinking": Profile("quit_drinking"),
                })

    def test_test_bot_credential_cannot_start_as_production(self):
        config = BotConfig("smoking", "secret", 1, "quit_smoking", expected_username="easy_brosit_kurit_bot")
        with self.assertRaisesRegex(ValueError, "Wrong bot"):
            validate_bot_identity(config, "Test_before_production_bot")
        validate_bot_identity(config, "easy_brosit_kurit_bot")

    def test_distinct_bots_share_one_admin_but_keep_profiles(self):
        raw = json.dumps([
            {"name": "smoking", "token_env": "TEST_SMOKING", "admin_id_env": "TEST_ADMIN",
             "default_profile": "quit_smoking", "expected_username": "easy_brosit_kurit_bot"},
            {"name": "drinking", "token_env": "TEST_DRINKING", "admin_id_env": "TEST_ADMIN",
             "default_profile": "quit_drinking", "expected_username": "brosit_pit_bot"},
        ])
        with patch.dict(os.environ, {"BOTS_CONFIG_JSON": raw, "TEST_SMOKING": "one",
                                    "TEST_DRINKING": "two", "TEST_ADMIN": "42"}):
            configs = load_bot_configs({name: Profile(name) for name in ("quit_smoking", "quit_drinking")})
        self.assertEqual(len(configs), 2)
        self.assertEqual([c.admin_id for c in configs], [42, 42])
        self.assertEqual([c.default_profile for c in configs], ["quit_smoking", "quit_drinking"])
        self.assertEqual(configs[1].expected_username, "brosit_pit_bot")

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


class ClassificationTests(unittest.IsolatedAsyncioTestCase):
    async def test_spam_verdict_uses_non_thinking_mode(self):
        client = Mock()
        client.chat.completions.create = AsyncMock(return_value=SimpleNamespace(choices=[
            SimpleNamespace(message=SimpleNamespace(content="SPAM"), finish_reason="stop")
        ]))
        self.assertTrue(await is_ai_spam(client, "test", "example", "sender", Profile("test")))
        request = client.chat.completions.create.call_args.kwargs
        self.assertEqual(request["extra_body"], {"thinking": {"type": "disabled"}})
        self.assertGreaterEqual(request["max_tokens"], 16)

    async def test_empty_verdict_is_reported_as_failure(self):
        client = Mock()
        client.chat.completions.create = AsyncMock(return_value=SimpleNamespace(choices=[
            SimpleNamespace(message=SimpleNamespace(content=None), finish_reason="length")
        ]))
        with self.assertLogs("bot", level="ERROR") as logs:
            self.assertFalse(await is_ai_spam(client, "test", "example", "sender", Profile("test")))
        self.assertIn("no valid verdict", logs.output[0])


class CommandTests(unittest.IsolatedAsyncioTestCase):
    async def test_start_and_status_reply_and_report_group_permissions(self):
        with tempfile.TemporaryDirectory() as folder:
            store = ModerationStore(str(Path(folder) / "moderation.db"))
            config = BotConfig("smoking", "12345:fake", 42, "quit_smoking")
            app = build_application(config, {"quit_smoking": Profile("quit_smoking")}, Mock(), "test", store, 4320)
            handler = next(h for h in app.handlers[0] if getattr(h, "commands", None) == frozenset({"start", "status"}))
            message = SimpleNamespace(chat_id=-100, chat=SimpleNamespace(type="supergroup"), reply_text=AsyncMock())
            bot = SimpleNamespace(username="easy_brosit_kurit_bot", id=5,
                                  get_chat_member=AsyncMock(return_value=SimpleNamespace(status="administrator", can_delete_messages=True, can_restrict_members=True)))
            await handler.callback(SimpleNamespace(effective_message=message), SimpleNamespace(bot=bot))
            reply = message.reply_text.call_args.args[0]
            self.assertIn("@easy_brosit_kurit_bot", reply)
            self.assertIn("Delete messages: True", reply)
            self.assertIn("Restrict members: True", reply)
            store.close()


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

