"""Tests for secure session management."""
from __future__ import annotations

import time
import unittest

from dcc.security.sessions import (
    Session,
    SessionError,
    SessionExpiredError,
    SessionInvalidError,
    SessionManager,
    SessionRevokedError,
    SessionStatus,
    TokenPair,
    generate_session_id,
    generate_token,
    hash_token,
)


class TokenGenerationTests(unittest.TestCase):
    def test_generate_token_returns_url_safe_string(self):
        token = generate_token()
        self.assertIsInstance(token, str)
        self.assertGreater(len(token), 0)
        # URL-safe base64 uses A-Z, a-z, 0-9, -, _
        import re
        self.assertRegex(token, r"^[A-Za-z0-9_-]+$")

    def test_generate_token_produces_unique_values(self):
        tokens = {generate_token() for _ in range(100)}
        self.assertEqual(len(tokens), 100)

    def test_generate_session_id_returns_uuid(self):
        sid = generate_session_id()
        self.assertRegex(sid, r"^[0-9a-f-]{36}$")

    def test_hash_token_is_deterministic_and_hex(self):
        token = "test-token-123"
        h1 = hash_token(token)
        h2 = hash_token(token)
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)
        self.assertRegex(h1, r"^[0-9a-f]{64}$")

    def test_hash_token_differs_for_different_tokens(self):
        self.assertNotEqual(hash_token("a"), hash_token("b"))


class SessionTests(unittest.TestCase):
    def test_session_creation_defaults(self):
        s = Session(session_id="s1", tenant_id="t1", user_id="u1")
        self.assertEqual(s.status, SessionStatus.ACTIVE)
        self.assertIsNotNone(s.created_at)
        self.assertIsNotNone(s.last_activity_at)

    def test_is_access_token_valid(self):
        s = Session(
            session_id="s1", tenant_id="t1", user_id="u1",
            access_token_expires_at=time.time() + 100,
        )
        self.assertTrue(s.is_access_token_valid())

    def test_is_access_token_valid_expired(self):
        s = Session(
            session_id="s1", tenant_id="t1", user_id="u1",
            access_token_expires_at=time.time() - 1,
        )
        self.assertFalse(s.is_access_token_valid())

    def test_is_access_token_valid_revoked(self):
        s = Session(
            session_id="s1", tenant_id="t1", user_id="u1",
            status=SessionStatus.REVOKED,
            access_token_expires_at=time.time() + 100,
        )
        self.assertFalse(s.is_access_token_valid())

    def test_touch_updates_last_activity(self):
        s = Session(session_id="s1", tenant_id="t1", user_id="u1")
        old = s.last_activity_at
        time.sleep(0.01)
        s.touch()
        self.assertGreater(s.last_activity_at, old)


class SessionManagerCreationTests(unittest.TestCase):
    def setUp(self):
        self.mgr = SessionManager(access_token_ttl=900, refresh_token_ttl=604800)

    def test_create_session_returns_session_and_tokens(self):
        session, tokens = self.mgr.create_session("tenant-1", "user-1")
        self.assertIsInstance(session, Session)
        self.assertIsInstance(tokens, TokenPair)
        self.assertEqual(session.tenant_id, "tenant-1")
        self.assertEqual(session.user_id, "user-1")
        self.assertEqual(session.status, SessionStatus.ACTIVE)
        self.assertTrue(tokens.access_token)
        self.assertTrue(tokens.refresh_token)
        self.assertNotEqual(tokens.access_token, tokens.refresh_token)

    def test_create_session_stores_hashes_not_raw_tokens(self):
        session, tokens = self.mgr.create_session("tenant-1", "user-1")
        self.assertEqual(session.access_token_hash, hash_token(tokens.access_token))
        self.assertEqual(session.refresh_token_hash, hash_token(tokens.refresh_token))
        self.assertNotEqual(session.access_token_hash, tokens.access_token)

    def test_create_session_with_metadata(self):
        session, _ = self.mgr.create_session(
            "tenant-1", "user-1",
            ip_address="127.0.0.1",
            user_agent="test-agent",
            metadata={"key": "value"},
        )
        self.assertEqual(session.ip_address, "127.0.0.1")
        self.assertEqual(session.user_agent, "test-agent")
        self.assertEqual(session.metadata, {"key": "value"})

    def test_create_session_requires_tenant_id(self):
        with self.assertRaises(ValueError):
            self.mgr.create_session("", "user-1")

    def test_create_session_requires_user_id(self):
        with self.assertRaises(ValueError):
            self.mgr.create_session("tenant-1", "")


class SessionManagerValidationTests(unittest.TestCase):
    def setUp(self):
        self.mgr = SessionManager(access_token_ttl=900, refresh_token_ttl=604800)
        self.session, self.tokens = self.mgr.create_session("tenant-1", "user-1")

    def test_validate_access_token_success(self):
        session = self.mgr.validate_access_token(self.tokens.access_token)
        self.assertEqual(session.session_id, self.session.session_id)

    def test_validate_access_token_invalid(self):
        with self.assertRaises(SessionInvalidError):
            self.mgr.validate_access_token("nonexistent-token")

    def test_validate_access_token_expired(self):
        mgr = SessionManager(access_token_ttl=0.01, refresh_token_ttl=604800)
        _, tokens = mgr.create_session("tenant-1", "user-1")
        time.sleep(0.02)
        with self.assertRaises(SessionExpiredError):
            mgr.validate_access_token(tokens.access_token)

    def test_validate_access_token_revoked(self):
        self.mgr.revoke_session(self.session.session_id)
        with self.assertRaises((SessionRevokedError, SessionInvalidError)):
            self.mgr.validate_access_token(self.tokens.access_token)


class SessionManagerRefreshTests(unittest.TestCase):
    def setUp(self):
        self.mgr = SessionManager(access_token_ttl=900, refresh_token_ttl=604800)
        self.session, self.tokens = self.mgr.create_session("tenant-1", "user-1")

    def test_refresh_returns_new_tokens(self):
        session, new_tokens = self.mgr.refresh_session(self.tokens.refresh_token)
        self.assertEqual(session.session_id, self.session.session_id)
        self.assertNotEqual(new_tokens.access_token, self.tokens.access_token)
        self.assertNotEqual(new_tokens.refresh_token, self.tokens.refresh_token)

    def test_refresh_invalidates_old_refresh_token(self):
        self.mgr.refresh_session(self.tokens.refresh_token)
        with self.assertRaises(SessionInvalidError):
            self.mgr.refresh_session(self.tokens.refresh_token)

    def test_refresh_invalidates_old_access_token(self):
        self.mgr.refresh_session(self.tokens.refresh_token)
        with self.assertRaises(SessionInvalidError):
            self.mgr.validate_access_token(self.tokens.access_token)

    def test_refresh_with_invalid_token(self):
        with self.assertRaises(SessionInvalidError):
            self.mgr.refresh_session("nonexistent-refresh")

    def test_refresh_expired(self):
        mgr = SessionManager(access_token_ttl=900, refresh_token_ttl=0.01)
        _, tokens = mgr.create_session("tenant-1", "user-1")
        time.sleep(0.02)
        with self.assertRaises(SessionExpiredError):
            mgr.refresh_session(tokens.refresh_token)


class SessionManagerRevocationTests(unittest.TestCase):
    def setUp(self):
        self.mgr = SessionManager(access_token_ttl=900, refresh_token_ttl=604800)
        self.session, self.tokens = self.mgr.create_session("tenant-1", "user-1")

    def test_revoke_session(self):
        revoked = self.mgr.revoke_session(self.session.session_id)
        self.assertEqual(revoked.status, SessionStatus.REVOKED)

    def test_revoke_nonexistent_session(self):
        with self.assertRaises(SessionInvalidError):
            self.mgr.revoke_session("nonexistent")

    def test_revoke_all_user_sessions(self):
        _, tokens2 = self.mgr.create_session("tenant-1", "user-1")
        count = self.mgr.revoke_all_user_sessions("user-1")
        self.assertEqual(count, 2)
        with self.assertRaises(SessionInvalidError):
            self.mgr.validate_access_token(self.tokens.access_token)
        with self.assertRaises(SessionInvalidError):
            self.mgr.validate_access_token(tokens2.access_token)

    def test_revoke_all_tenant_sessions(self):
        self.mgr.create_session("tenant-1", "user-2")
        self.mgr.create_session("tenant-2", "user-3")
        count = self.mgr.revoke_all_tenant_sessions("tenant-1")
        self.assertEqual(count, 2)


class SessionManagerLimitTests(unittest.TestCase):
    def test_max_sessions_per_user_enforced(self):
        mgr = SessionManager(access_token_ttl=900, refresh_token_ttl=604800, max_sessions_per_user=3)
        sessions = []
        for _ in range(5):
            s, _ = mgr.create_session("tenant-1", "user-1")
            sessions.append(s)
        # Oldest 2 should be revoked
        self.assertEqual(sessions[0].status, SessionStatus.REVOKED)
        self.assertEqual(sessions[1].status, SessionStatus.REVOKED)
        # Newest 3 should be active
        self.assertEqual(sessions[2].status, SessionStatus.ACTIVE)
        self.assertEqual(sessions[3].status, SessionStatus.ACTIVE)
        self.assertEqual(sessions[4].status, SessionStatus.ACTIVE)


class SessionManagerCleanupTests(unittest.TestCase):
    def test_cleanup_expired_sessions(self):
        mgr = SessionManager(access_token_ttl=0.01, refresh_token_ttl=0.01)
        s, _ = mgr.create_session("tenant-1", "user-1")
        time.sleep(0.02)
        removed = mgr.cleanup_expired()
        self.assertGreaterEqual(removed, 1)

    def test_cleanup_removes_revoked_sessions(self):
        mgr = SessionManager(access_token_ttl=900, refresh_token_ttl=604800)
        s, _ = mgr.create_session("tenant-1", "user-1")
        mgr.revoke_session(s.session_id)
        removed = mgr.cleanup_expired()
        self.assertGreaterEqual(removed, 1)


class SessionManagerAuditTests(unittest.TestCase):
    def test_audit_callback_called(self):
        events = []

        def audit(action, session):
            events.append((action, session.session_id))

        mgr = SessionManager(
            access_token_ttl=900,
            refresh_token_ttl=604800,
            audit_callback=audit,
        )
        s, tokens = mgr.create_session("tenant-1", "user-1")
        mgr.validate_access_token(tokens.access_token)
        mgr.refresh_session(tokens.refresh_token)
        mgr.revoke_session(s.session_id)

        actions = [a for a, _ in events]
        self.assertIn("session.created", actions)
        self.assertIn("session.validated", actions)
        self.assertIn("session.refreshed", actions)
        self.assertIn("session.revoked", actions)


class SessionManagerLookupTests(unittest.TestCase):
    def setUp(self):
        self.mgr = SessionManager(access_token_ttl=900, refresh_token_ttl=604800)

    def test_get_session(self):
        s, _ = self.mgr.create_session("tenant-1", "user-1")
        found = self.mgr.get_session(s.session_id)
        self.assertIsNotNone(found)
        self.assertEqual(found.session_id, s.session_id)

    def test_get_session_not_found(self):
        self.assertIsNone(self.mgr.get_session("nonexistent"))

    def test_list_user_sessions(self):
        self.mgr.create_session("tenant-1", "user-1")
        self.mgr.create_session("tenant-1", "user-1")
        self.mgr.create_session("tenant-1", "user-2")
        sessions = self.mgr.list_user_sessions("user-1")
        self.assertEqual(len(sessions), 2)

    def test_list_tenant_sessions(self):
        self.mgr.create_session("tenant-1", "user-1")
        self.mgr.create_session("tenant-1", "user-2")
        self.mgr.create_session("tenant-2", "user-3")
        sessions = self.mgr.list_tenant_sessions("tenant-1")
        self.assertEqual(len(sessions), 2)

    def test_session_count(self):
        self.mgr.create_session("tenant-1", "user-1")
        self.mgr.create_session("tenant-1", "user-2")
        self.assertEqual(self.mgr.session_count, 2)
        self.assertEqual(self.mgr.active_session_count, 2)


if __name__ == "__main__":
    unittest.main()
