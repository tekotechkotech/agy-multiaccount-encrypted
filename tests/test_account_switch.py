# -*- coding: utf-8 -*-
"""Unit tests for the Antigravity account-switch tool.

These tests exercise the public API in `account_switch.py` without touching
the real user token directory. The environment variables `AGY_TOKEN_DIR`,
`AGY_CURRENT_ACCOUNT_FILE`, `AGY_ACTIVE_TOKEN_FILE`, and `AGY_KEYS_DIR` are
overridden to point to an isolated temporary directory during testing.
"""

import os
import shutil
import unittest
from pathlib import Path

# Absolute import using the package namespace
from agy_account_switch.account_switch import (
    add_account,
    list_accounts,
    switch_account,
    remove_account,
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


if __name__ == "__main__":
    unittest.main()
