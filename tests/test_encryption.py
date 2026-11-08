# -*- coding: utf-8 -*-
"""Unit tests for the OpenSSL-based encryption helpers.

Covers:
- Encryption round-trip (various token formats and characters).
- HMAC integrity check and tamper rejection.
- System keyring fallback to file in AGY_KEYS_DIR with mode 600.
- is_encrypted detection utility.
"""

import os
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

from agy_account_switch.encryption import (
    _get_key,
    encrypt_token,
    decrypt_token,
    compute_hmac,
    verify_hmac,
    is_encrypted,
    _keys_dir,
)


class EncryptionTest(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(__file__).resolve().parent / "tmp_enc"
        if self.tmp_dir.exists():
            shutil.rmtree(self.tmp_dir)
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        self.keys_dir = self.tmp_dir / "keys"
        self.keys_dir.mkdir(parents=True, exist_ok=True)

        os.environ["AGY_KEYS_DIR"] = str(self.keys_dir)

    def tearDown(self):
        if self.tmp_dir.exists():
            shutil.rmtree(self.tmp_dir)

    def test_round_trip_various_tokens(self):
        tokens = [
            "simple-token-12345",
            "ya29.a0AfH6SMB_very_long_oauth_token_with_hyphens-and_underscores",
            '{"token": "xyz", "expires": 1234567890, "type": "bearer"}',
            "special_chars!@#$%^&*()_+~`|}{[]:;?><,./",
            "multiline\ntoken\nwith\nnewlines",
        ]
        for token in tokens:
            with self.subTest(token=token[:20]):
                account_name = f"user_{abs(hash(token)) % 10000}"
                encrypted = encrypt_token(account_name, token)

                self.assertTrue(is_encrypted(encrypted))
                self.assertTrue(encrypted.startswith("ENC:"))
                self.assertNotIn(token, encrypted)

                decrypted = decrypt_token(account_name, encrypted)
                self.assertEqual(decrypted, token)

    def test_hmac_verification_and_tampering(self):
        account = "tamper_test"
        secret = "super-confidential-api-key"
        encrypted = encrypt_token(account, secret)

        # 1. Normal decryption succeeds
        decrypted = decrypt_token(account, encrypted)
        self.assertEqual(decrypted, secret)

        # 2. Tampered ciphertext should fail HMAC verification
        parts = encrypted.split(":", 2)
        tampered_ciphertext = parts[2][:-1] + ("A" if parts[2][-1] != "A" else "B")
        tampered_token = f"{parts[0]}:{parts[1]}:{tampered_ciphertext}"

        with self.assertRaises(ValueError) as ctx:
            decrypt_token(account, tampered_token)
        self.assertIn("HMAC verification failed", str(ctx.exception))

        # 3. Tampered HMAC digest should fail
        tampered_mac = "0" * 64
        tampered_hmac_token = f"{parts[0]}:{tampered_mac}:{parts[2]}"

        with self.assertRaises(ValueError) as ctx:
            decrypt_token(account, tampered_hmac_token)
        self.assertIn("HMAC verification failed", str(ctx.exception))

        # 4. Malformed payload
        with self.assertRaises(ValueError):
            decrypt_token(account, "ENC:malformed")

    def test_keyring_fallback_file_and_permissions(self):
        account = "fallback_acct"

        # Mock keyring to simulate headless environments where keyring fails
        with patch.dict(os.environ, {"AGY_FORCE_KEY_FILE": "1"}):
            with patch("keyring.get_password", side_effect=Exception("NoKeyringError")), \
                 patch("keyring.set_password", side_effect=Exception("NoKeyringError")):

                key = _get_key(account, create=True)
                self.assertIsNotNone(key)
                self.assertEqual(len(key), 64)  # 256-bit hex

                # Verify key file was created in keys_dir
                key_file = self.keys_dir / f"{account}.key"
                self.assertTrue(key_file.is_file())
                self.assertEqual(key_file.read_text(encoding="utf-8").strip(), key)

                # Check strict permissions (0600)
                st_mode = oct(key_file.stat().st_mode)[-3:]
                self.assertEqual(st_mode, "600")

                # Verify second call retrieves the same key from file
                second_key = _get_key(account, create=False)
                self.assertEqual(second_key, key)

                # Verify encryption and decryption works with this fallback key
                token = "test-token-under-fallback"
                enc = encrypt_token(account, token)
                dec = decrypt_token(account, enc)
                self.assertEqual(dec, token)

    def test_is_encrypted_helper(self):
        self.assertTrue(is_encrypted("ENC:abcdef:ciphertext"))
        self.assertTrue(is_encrypted("a" * 64 + ":ciphertext"))
        self.assertFalse(is_encrypted("plain_token_string"))
        self.assertFalse(is_encrypted(""))
        self.assertFalse(is_encrypted(None))


if __name__ == "__main__":
    unittest.main()
