import os
import json
import logging
import shutil
from pathlib import Path
from datetime import datetime

try:
    from agy_account_switch.encryption import (
        encrypt_token,
        decrypt_token,
        is_encrypted,
        _get_key,
    )
except ImportError:
    from .encryption import (
        encrypt_token,
        decrypt_token,
        is_encrypted,
        _get_key,
    )

# Configure logging
LOG_FILE = Path.home() / ".gemini" / "antigravity-cli" / "log" / "account_switch.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
# Ensure log file has safe permissions
try:
    LOG_FILE.chmod(0o600)
except Exception:
    pass

# Dynamic path helpers to support runtime environment variable overrides during tests
def _token_dir() -> Path:
    d = Path(os.getenv(
        "AGY_TOKEN_DIR",
        Path.home() / ".gemini" / "antigravity-cli" / "tokens",
    ))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _current_account_file() -> Path:
    return Path(os.getenv(
        "AGY_CURRENT_ACCOUNT_FILE",
        Path.home() / ".gemini" / "antigravity-cli" / "current_account.txt",
    ))


def _active_token_file() -> Path:
    return Path(os.getenv(
        "AGY_ACTIVE_TOKEN_FILE",
        Path.home() / ".gemini" / "antigravity-cli" / "antigravity-oauth-token",
    ))


# Backwards-compatible module-level definitions
TOKEN_DIR = _token_dir()
CURRENT_ACCOUNT_FILE = _current_account_file()
ACTIVE_TOKEN_FILE = _active_token_file()


def _sanitize_account_name(name: str) -> str:
    """Sanitize an account name to prevent path traversal and illegal characters.

    Allows only alphanumeric characters, underscores and hyphens.
    """
    if not name:
        raise ValueError("Account name cannot be empty")
    if not all(c.isalnum() or c in "_-" for c in name):
        raise ValueError("Account name contains invalid characters")
    return name


def _token_file_path(account: str) -> Path:
    sanitized = _sanitize_account_name(account)
    return _token_dir() / f"{sanitized}.token"


def _backup_file(path: Path) -> None:
    if path.is_file():
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        backup_path = path.with_name(f"{path.name}.bak.{timestamp}")
        shutil.copy2(path, backup_path)
        logging.info("Backup created for %s -> %s", path, backup_path)


def add_account(account: str, token: str, overwrite: bool = False, encrypt: bool = False) -> None:
    """Add a new account token.

    Args:
        account: Logical name for the account.
        token: The authentication token string.
        overwrite: If True, replaces existing token after backing it up.
        encrypt: If True, encrypts token with OpenSSL AES-256-CBC and HMAC.
    """
    token_path = _token_file_path(account)
    if token_path.exists() and not overwrite:
        raise FileExistsError(f"Token file for account '{account}' already exists.")
    if token_path.exists() and overwrite:
        _backup_file(token_path)

    if encrypt:
        token_to_store = encrypt_token(account, token)
    else:
        token_to_store = token

    # Write token with restrictive permissions
    token_path.write_text(token_to_store + "\n", encoding="utf-8")
    try:
        token_path.chmod(0o600)
    except Exception:
        pass
    logging.info("Added account %s (encrypted=%s)", account, encrypt)


def list_accounts() -> list[str]:
    """Return a list of account names for which token files exist."""
    accounts = []
    for file in _token_dir().glob("*.token"):
        accounts.append(file.stem)
    logging.info("Listed %d accounts", len(accounts))
    return sorted(accounts)


def switch_account(account: str) -> None:
    """Switch the active account.

    Writes the selected account name to the current account file and updates
    the active Antigravity OAuth token file (decrypting if stored encrypted).
    """
    token_path = _token_file_path(account)
    if not token_path.is_file():
        raise FileNotFoundError(f"Token for account '{account}' not found.")

    raw_token = token_path.read_text(encoding="utf-8").strip()

    # Determine if stored token is encrypted and decrypt if necessary
    if is_encrypted(raw_token):
        token_to_activate = decrypt_token(account, raw_token)
    else:
        token_to_activate = raw_token

    # 1. Update current account indicator
    cur_file = _current_account_file()
    cur_file.parent.mkdir(parents=True, exist_ok=True)
    cur_file.write_text(account, encoding="utf-8")

    # 2. Update active Antigravity OAuth token file
    act_file = _active_token_file()
    act_file.parent.mkdir(parents=True, exist_ok=True)
    if act_file.is_file():
        _backup_file(act_file)
    act_file.write_text(token_to_activate, encoding="utf-8")
    try:
        act_file.chmod(0o600)
    except Exception:
        pass

    logging.info("Switched to account %s", account)


def remove_account(account: str) -> None:
    """Remove an account token safely.

    Creates a backup before deletion.
    """
    token_path = _token_file_path(account)
    if not token_path.is_file():
        raise FileNotFoundError(f"Token for account '{account}' not found.")
    _backup_file(token_path)
    token_path.unlink()
    logging.info("Removed account %s", account)
