import os
import sys
import hmac
import hashlib
import secrets
import logging
import subprocess
from pathlib import Path

# Keys directory (can be overridden via env var for testing)
def _keys_dir() -> Path:
    d = Path(os.getenv(
        "AGY_KEYS_DIR",
        Path.home() / ".gemini" / "antigravity-cli" / "keys",
    ))
    d.mkdir(parents=True, exist_ok=True)
    try:
        d.chmod(0o700)
    except Exception:
        pass
    return d

KEYS_DIR = _keys_dir()


def _sanitize_account_name(name: str) -> str:
    """Sanitize account name to prevent path traversal and invalid characters."""
    if not name:
        raise ValueError("Account name cannot be empty")
    if not all(c.isalnum() or c in "_-" for c in name):
        raise ValueError("Account name contains invalid characters")
    return name


def _get_key(account: str, create: bool = True) -> str:
    """Retrieve or generate an AES-256 key for the specified account.

    Stores per-account keys in the system keyring ('agy' service).
    Falls back to a 600-mode key file in ~/.gemini/antigravity-cli/keys/<account>.key.
    """
    sanitized = _sanitize_account_name(account)
    key = None

    # 1. Attempt retrieval from system keyring
    try:
        import keyring
        key = keyring.get_password("agy", sanitized)
    except Exception as e:
        logging.debug("Keyring retrieval failed for account '%s': %s", sanitized, e)
        key = None

    # 2. Check fallback key file
    key_file = _keys_dir() / f"{sanitized}.key"
    if not key and key_file.is_file():
        try:
            key = key_file.read_text(encoding="utf-8").strip()
            logging.debug("Retrieved key from fallback file for account '%s'", sanitized)
        except Exception as e:
            logging.warning("Failed reading fallback key file %s: %s", key_file, e)

    # 3. Generate key if not found and creation is permitted
    if not key and create:
        key = secrets.token_hex(32)  # 256-bit key represented as 64 hex characters
        saved_to_keyring = False
        try:
            import keyring
            keyring.set_password("agy", sanitized, key)
            saved_to_keyring = True
            logging.debug("Saved key to keyring for account '%s'", sanitized)
        except Exception as e:
            logging.debug("Keyring storage failed for account '%s': %s", sanitized, e)

        # Write to fallback file if keyring write failed or if explicitly forced
        if not saved_to_keyring or os.getenv("AGY_FORCE_KEY_FILE"):
            key_file.write_text(key + "\n", encoding="utf-8")
            try:
                key_file.chmod(0o600)
            except Exception:
                pass
            logging.info("Saved encryption key to fallback file: %s", key_file)

    if not key:
        raise ValueError(f"No encryption key found or generated for account '{account}'.")

    return key


def compute_hmac(key: str, data: str) -> str:
    """Compute HMAC-SHA256 hex digest for data using the provided key."""
    return hmac.new(key.encode("utf-8"), data.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_hmac(key: str, data: str, expected_hmac: str) -> bool:
    """Verify HMAC-SHA256 digest in constant time."""
    actual = compute_hmac(key, data)
    return hmac.compare_digest(actual, expected_hmac)


def is_encrypted(data: str) -> bool:
    """Check if the provided token string is in encrypted format."""
    if not isinstance(data, str):
        return False
    data = data.strip()
    return data.startswith("ENC:") or (":" in data and len(data.split(":", 1)[0]) == 64)


def encrypt_token(account: str, token: str | None = None, key: str | None = None) -> str:
    """Encrypt a token using OpenSSL aes-256-cbc with PBKDF2 and authenticated by HMAC.

    Can be called as:
      encrypt_token(account, token)
      encrypt_token(account, token, key=key)
      encrypt_token(token, key=key)
    """
    if token is None and key is not None:
        token = account
        account = "default"
    if token is None:
        raise ValueError("Token must not be None")

    if key is None:
        key = _get_key(account)

    cmd = [
        "openssl",
        "enc",
        "-aes-256-cbc",
        "-pbkdf2",
        "-base64",
        "-A",
        "-pass",
        f"pass:{key}",
    ]
    try:
        proc = subprocess.run(
            cmd,
            input=token.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        err_msg = e.stderr.decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenSSL encryption failed: {err_msg}") from e

    ciphertext = proc.stdout.decode("utf-8").strip()
    mac = compute_hmac(key, ciphertext)
    return f"ENC:{mac}:{ciphertext}"


def decrypt_token(account: str, encrypted_token: str | None = None, key: str | None = None) -> str:
    """Decrypt a token using OpenSSL aes-256-cbc after verifying HMAC integrity.

    Can be called as:
      decrypt_token(account, encrypted_token)
      decrypt_token(account, encrypted_token, key=key)
      decrypt_token(encrypted_token, key=key)
    """
    if encrypted_token is None and key is not None:
        encrypted_token = account
        account = "default"
    if encrypted_token is None:
        raise ValueError("Encrypted token must not be None")

    if key is None:
        key = _get_key(account)

    payload = encrypted_token.strip()

    # Parse HMAC and ciphertext
    if payload.startswith("ENC:"):
        parts = payload.split(":", 2)
        if len(parts) < 3:
            raise ValueError("Malformed encrypted token payload")
        expected_hmac = parts[1]
        ciphertext = parts[2]
        if not verify_hmac(key, ciphertext, expected_hmac):
            raise ValueError("HMAC verification failed: ciphertext integrity check failed")
    elif ":" in payload and len(payload.split(":", 1)[0]) == 64:
        expected_hmac, ciphertext = payload.split(":", 1)
        if not verify_hmac(key, ciphertext, expected_hmac):
            raise ValueError("HMAC verification failed: ciphertext integrity check failed")
    else:
        # Plain ciphertext without HMAC prefix
        ciphertext = payload

    # Decrypt with OpenSSL (try with -A first, then without -A)
    commands = [
        ["openssl", "enc", "-d", "-aes-256-cbc", "-pbkdf2", "-base64", "-A", "-pass", f"pass:{key}"],
        ["openssl", "enc", "-d", "-aes-256-cbc", "-pbkdf2", "-base64", "-pass", f"pass:{key}"],
    ]

    last_error = ""
    for cmd in commands:
        proc = subprocess.run(
            cmd,
            input=ciphertext.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if proc.returncode == 0:
            return proc.stdout.decode("utf-8")
        last_error = proc.stderr.decode("utf-8", errors="replace").strip()

    raise ValueError(f"OpenSSL decryption failed: {last_error}")
