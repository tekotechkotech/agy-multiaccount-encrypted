# -*- coding: utf-8 -*-
"""Unit tests for the Antigravity account-switch tool.

These tests exercise the public API in `account_switch.py` without touching
the real user token directory. The environment variables `AGY_TOKEN_DIR`,
`AGY_CURRENT_ACCOUNT_FILE`, `AGY_ACTIVE_TOKEN_FILE`, and `AGY_KEYS_DIR` are
overridden to point to an isolated temporary directory during testing.
"""

import os
import json
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

# Absolute import using the package namespace
from agy_account_switch.account_switch import (
    add_account,
    list_accounts,
    switch_account,
    remove_account,
    capture_account,
    login_account,
    _token_file_path,
)
from agy_account_switch.encryption import is_encrypted


class AccountSwitchTest(unittest.TestCase):
    def setUp(self):
        # Create an isolated temporary directory for tokens, current account, active token, and keys
        self.tmp_dir = Path(__file__).resolve().parent / "tmp"
        if self.tmp_dir.exists():
            shutil.rmtree(self.tmp_dir)
        self.tmp_dir.mkdir(parents=True, exist_ok=True)

        self.token_dir = self.tmp_dir / "tokens"
        self.token_dir.mkdir(parents=True, exist_ok=True)
        self.current_account_file = self.tmp_dir / "current_account.txt"
        self.active_token_file = self.tmp_dir / "antigravity-oauth-token"
        self.keys_dir = self.tmp_dir / "keys"
        self.keys_dir.mkdir(parents=True, exist_ok=True)

        os.environ["AGY_TOKEN_DIR"] = str(self.token_dir)
        os.environ["AGY_CURRENT_ACCOUNT_FILE"] = str(self.current_account_file)
        os.environ["AGY_ACTIVE_TOKEN_FILE"] = str(self.active_token_file)
        os.environ["AGY_KEYS_DIR"] = str(self.keys_dir)

    def tearDown(self):
        # Clean up temporary test files
        if self.tmp_dir.exists():
            shutil.rmtree(self.tmp_dir)

    def test_add_and_list(self):
        add_account("test1", "secret-token-1")
        add_account("test2", "secret-token-2")
        accounts = set(list_accounts())
        self.assertEqual(accounts, {"test1", "test2"})

        # Verify token file content and permissions
        token_path = _token_file_path("test1")
        self.assertTrue(token_path.is_file())
        self.assertEqual(token_path.read_text(encoding="utf-8").strip(), "secret-token-1")
        self.assertEqual(oct(token_path.stat().st_mode)[-3:], "600")

    def test_overwrite(self):
        add_account("test", "old-token")
        with self.assertRaises(FileExistsError):
            add_account("test", "new-token")
        add_account("test", "new-token", overwrite=True)
        token_path = _token_file_path("test")
        self.assertTrue(any(".bak." in p.name for p in token_path.parent.iterdir()))
        self.assertEqual(token_path.read_text(encoding="utf-8").strip(), "new-token")

    def test_switch_and_remove(self):
        add_account("active", "raw-secret-token")
        switch_account("active")

        # Current account file should be updated
        self.assertTrue(self.current_account_file.is_file())
        self.assertEqual(self.current_account_file.read_text(encoding="utf-8").strip(), "active")

        # Active OAuth token file should also be written
        self.assertTrue(self.active_token_file.is_file())
        self.assertEqual(self.active_token_file.read_text(encoding="utf-8").strip(), "raw-secret-token")
        self.assertEqual(oct(self.active_token_file.stat().st_mode)[-3:], "600")

        remove_account("active")
        self.assertFalse(_token_file_path("active").exists())
        # Backup of removed token should exist
        backups = list(self.token_dir.glob("*.bak.*"))
        self.assertTrue(backups)

    def test_add_encrypted_and_switch(self):
        secret = "my-super-secret-token-xyz-12345"
        add_account("secure-acct", secret, encrypt=True)

        token_path = _token_file_path("secure-acct")
        self.assertTrue(token_path.is_file())
        stored_content = token_path.read_text(encoding="utf-8").strip()

        # Token must be stored encrypted, not plaintext
        self.assertTrue(is_encrypted(stored_content))
        self.assertNotIn(secret, stored_content)
        self.assertEqual(oct(token_path.stat().st_mode)[-3:], "600")

        # Switch to the encrypted account
        switch_account("secure-acct")

        # Active token file must have the decrypted token
        self.assertTrue(self.active_token_file.is_file())
        decrypted_active = self.active_token_file.read_text(encoding="utf-8").strip()
        self.assertEqual(decrypted_active, secret)
        self.assertEqual(self.current_account_file.read_text(encoding="utf-8").strip(), "secure-acct")

    def test_invalid_account_name(self):
        with self.assertRaises(ValueError):
            add_account("", "some-token")
        with self.assertRaises(ValueError):
            add_account("invalid/name", "some-token")
        with self.assertRaises(ValueError):
            add_account("bad name", "some-token")

    def test_switch_nonexistent_account(self):
        with self.assertRaises(FileNotFoundError):
            switch_account("does-not-exist")

    def test_capture_account_with_json_and_email(self):
        token_payload = {
            "token": "ya29.sample_oauth_access_token_12345",
            "auth_method": "oauth",
            "id_token_email": "engineer@bomasix.sch.id",
        }
        self.active_token_file.write_text(json.dumps(token_payload), encoding="utf-8")

        result = capture_account("bomasix-eng")
        self.assertEqual(
            result,
            {
                "account": "bomasix-eng",
                "email": "engineer@bomasix.sch.id",
                "encrypted": False,
            },
        )

        # Check account was saved
        token_file = _token_file_path("bomasix-eng")
        self.assertTrue(token_file.is_file())
        self.assertEqual(oct(token_file.stat().st_mode)[-3:], "600")
        saved_data = json.loads(token_file.read_text(encoding="utf-8"))
        self.assertEqual(saved_data["id_token_email"], "engineer@bomasix.sch.id")

        # Current account indicator updated
        self.assertEqual(self.current_account_file.read_text(encoding="utf-8").strip(), "bomasix-eng")

    def test_capture_account_encrypted(self):
        token_payload = {
            "token": "ya29.encrypted_secret_token",
            "id_token_email": "admin@bomasix.sch.id",
        }
        token_str = json.dumps(token_payload)
        self.active_token_file.write_text(token_str, encoding="utf-8")

        result = capture_account("bomasix-admin", encrypt=True)
        self.assertEqual(result["account"], "bomasix-admin")
        self.assertEqual(result["email"], "admin@bomasix.sch.id")
        self.assertTrue(result["encrypted"])

        # Check storage is encrypted
        token_file = _token_file_path("bomasix-admin")
        self.assertTrue(token_file.is_file())
        stored_raw = token_file.read_text(encoding="utf-8").strip()
        self.assertTrue(is_encrypted(stored_raw))

        # Switch to it and ensure proper decryption into active file
        switch_account("bomasix-admin")
        self.assertEqual(self.active_token_file.read_text(encoding="utf-8").strip(), token_str)

    def test_capture_nonexistent_or_empty_token(self):
        if self.active_token_file.exists():
            self.active_token_file.unlink()

        # Non-existent file should raise FileNotFoundError
        with self.assertRaises(FileNotFoundError):
            capture_account("missing")

        # Empty file should raise ValueError
        self.active_token_file.write_text("   \n", encoding="utf-8")
        with self.assertRaises(ValueError):
            capture_account("empty")

    def test_capture_overwrite_behavior(self):
        token1 = json.dumps({"token": "first-token", "id_token_email": "first@example.com"})
        token2 = json.dumps({"token": "second-token", "id_token_email": "second@example.com"})

        self.active_token_file.write_text(token1, encoding="utf-8")
        capture_account("my-acct")

        # Overwrite without flag must fail
        self.active_token_file.write_text(token2, encoding="utf-8")
        with self.assertRaises(FileExistsError):
            capture_account("my-acct", overwrite=False)

        # Overwrite with flag must succeed and back up old token
        res = capture_account("my-acct", overwrite=True)
        self.assertEqual(res["email"], "second@example.com")
        token_file = _token_file_path("my-acct")
        saved = json.loads(token_file.read_text(encoding="utf-8"))
        self.assertEqual(saved["token"], "second-token")

        # Check backup exists
        backups = list(self.token_dir.glob("my-acct.token.bak.*"))
        self.assertTrue(len(backups) >= 1)

    def test_login_account_success(self):
        initial_token = "old-active-token"
        self.active_token_file.write_text(initial_token, encoding="utf-8")

        new_token_payload = json.dumps({
            "token": "new-login-token-999",
            "id_token_email": "logged_in@example.com",
        })

        def fake_subprocess_call(cmd):
            # Simulate browser login writing new active token
            self.active_token_file.write_text(new_token_payload, encoding="utf-8")
            return 0

        with patch("subprocess.call", side_effect=fake_subprocess_call):
            res = login_account("newly-logged", agy_bin="fake-agy")

        self.assertEqual(res["account"], "newly-logged")
        self.assertEqual(res["email"], "logged_in@example.com")
        self.assertEqual(self.current_account_file.read_text(encoding="utf-8").strip(), "newly-logged")

        # Token file was stored
        saved_file = _token_file_path("newly-logged")
        self.assertTrue(saved_file.is_file())
        self.assertEqual(saved_file.read_text(encoding="utf-8").strip(), new_token_payload)

    def test_login_account_failure_restores_backup(self):
        original_active = "original-precious-active-token"
        self.active_token_file.write_text(original_active, encoding="utf-8")

        def fake_aborted_call(cmd):
            # User closed browser, token not written
            return 1

        with patch("subprocess.call", side_effect=fake_aborted_call):
            with self.assertRaises(RuntimeError):
                login_account("aborted-login", agy_bin="fake-agy")

        # Original token must be restored
        self.assertTrue(self.active_token_file.is_file())
        self.assertEqual(self.active_token_file.read_text(encoding="utf-8"), original_active)
        # Account file should NOT exist
        self.assertFalse(_token_file_path("aborted-login").exists())

    def test_cli_capture_and_add_from_current(self):
        from agy_account_switch.agy_account_cli import main as cli_main

        token_payload = json.dumps({
            "token": "cli-captured-token-123",
            "id_token_email": "cli@example.com",
        })
        self.active_token_file.write_text(token_payload, encoding="utf-8")

        # 1. Test direct subcommand `capture <name>`
        cli_main(["capture", "cli-cap"])
        self.assertTrue(_token_file_path("cli-cap").is_file())
        self.assertEqual(self.current_account_file.read_text(encoding="utf-8").strip(), "cli-cap")

        # 2. Test alias `add <name> --from-current`
        cli_main(["add", "cli-alias", "--from-current", "--encrypt"])
        self.assertTrue(_token_file_path("cli-alias").is_file())
        raw = _token_file_path("cli-alias").read_text(encoding="utf-8").strip()
        self.assertTrue(is_encrypted(raw))

        # 3. Test `account capture <name> --force`
        cli_main(["account", "capture", "cli-cap", "--force"])
        self.assertEqual(self.current_account_file.read_text(encoding="utf-8").strip(), "cli-cap")

    def test_cli_add_missing_token_error(self):
        from agy_account_switch.agy_account_cli import main as cli_main
        with self.assertRaises(SystemExit) as cm:
            cli_main(["add", "missing-tok"])
        self.assertEqual(cm.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
