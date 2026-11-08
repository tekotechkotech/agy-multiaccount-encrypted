"""AGY Account Switch with OpenSSL-based AES-256-CBC Encryption."""

__version__ = "0.3.0"

from .encryption import (
    _get_key,
    encrypt_token,
    decrypt_token,
    compute_hmac,
    verify_hmac,
    is_encrypted,
)
from .account_switch import (
    add_account,
    list_accounts,
    switch_account,
    remove_account,
    capture_account,
    login_account,
    _token_file_path,
)

__all__ = [
    "_get_key",
    "encrypt_token",
    "decrypt_token",
    "compute_hmac",
    "verify_hmac",
    "is_encrypted",
    "add_account",
    "list_accounts",
    "switch_account",
    "remove_account",
    "capture_account",
    "login_account",
    "_token_file_path",
]
