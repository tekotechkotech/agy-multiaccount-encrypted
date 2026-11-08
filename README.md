# agy-multiaccount-encrypted

Multi-account manager with OpenSSL AES-256-CBC encryption and HMAC integrity verification for the **Google Antigravity CLI** (`agy`).

---

## Features

- **Multi-Account Profile Management:** Easily add, list, switch, and delete multiple Antigravity authentication profiles.
- **Hardware/System OpenSSL Encryption:** Encrypts account tokens using `openssl enc -aes-256-cbc -pbkdf2` via secure subprocess execution.
- **Cryptographic Integrity Verification:** Appends HMAC-SHA256 authentication tag (`ENC:<hmac>:<ciphertext>`) to detect any data tampering or corruption before decryption.
- **Key Storage with Automatic Fallback:** Per-account 256-bit encryption keys are stored securely in the system keyring (`agy` service). If the system keyring is unavailable (e.g. headless Linux servers), keys automatically fallback to dedicated key files in `~/.gemini/antigravity-cli/keys/<account>.key` with strict `0600` permissions.
- **Safety First & Backups:** Restrictive `0600` permissions enforced on all token files. Automatic timestamped backups (`.bak.<timestamp>`) are generated prior to any token overwrite or removal.
- **Seamless Wrapper:** The `agy_account` executable acts as a drop-in wrapper that transparently intercepts `account` commands while delegating all other native Antigravity commands directly to `/home/faizen/.local/bin/agy`.

---

## Directory Structure

```
~/.gemini/antigravity-cli/
├── antigravity-oauth-token     # Active decrypted token read by Antigravity CLI (mode 0600)
├── current_account.txt         # Active account name indicator
├── tokens/
│   ├── dev.token              # Encrypted token: ENC:<hmac>:<ciphertext> (mode 0600)
│   └── work.token             # Plain or encrypted token file (mode 0600)
├── keys/
│   └── dev.key                # Fallback per-account 256-bit key (mode 0600)
└── log/
    └── account_switch.log     # Operation audit log
```

---

## Installation & Setup

### Prerequisites

- **Python:** 3.8+
- **OpenSSL:** 3.0+
- **Keyring:** `pip install keyring`
- **Pytest (for development/testing):** `pip install pytest`

### Repository Setup

Clone or install the package in development mode:

```bash
git clone https://github.com/tekotechkotech/agy-multiaccount-encrypted.git ~/tools/agy-account-switch
cd ~/tools/agy-account-switch
pip install -e .
```

### Wrapper Script Setup

Create the wrapper script at `~/bin/agy_account` (or `~/.local/bin/agy_account`):

```bash
mkdir -p ~/bin
cat << 'EOF' > ~/bin/agy_account
#!/usr/bin/env bash
set -e

REPO_DIR="/home/faizen/tools/agy-account-switch"
export PYTHONPATH="$REPO_DIR:${PYTHONPATH:-}"
AGY_BIN="/home/faizen/.local/bin/agy"

if [ "$1" = "account" ]; then
    exec python3 -m agy_account_switch.agy_account_cli "$@"
elif [ "$1" = "add" ] || [ "$1" = "list" ] || [ "$1" = "switch" ] || [ "$1" = "remove" ]; then
    exec python3 -m agy_account_switch.agy_account_cli account "$@"
else
    exec "$AGY_BIN" "$@"
fi
EOF

chmod +x ~/bin/agy_account
ln -sf ~/bin/agy_account ~/.local/bin/agy_account
```

Ensure `~/bin` or `~/.local/bin` is in your `$PATH`.

---

## Usage

### 1. Adding an Account

To store an account token with AES-256-CBC encryption:

```bash
agy_account account add dev <your-oauth-token> --encrypt
```

To store an unencrypted account token:

```bash
agy_account account add personal <your-oauth-token>
```

To overwrite an existing account:

```bash
agy_account account add dev <new-token> --overwrite --encrypt
```

### 2. Switching Active Account

Switching decrypts the token (if encrypted) and atomically writes the decrypted token into `~/.gemini/antigravity-cli/antigravity-oauth-token` with `0600` mode, updating `current_account.txt`:

```bash
agy_account account switch dev
```

### 3. Listing Accounts

```bash
agy_account account list
```

Output:
```
dev
personal
```

### 4. Removing an Account

Creates a backup of the token before unlinking it:

```bash
agy_account account remove old-account
```

### 5. Native Antigravity Passthrough

All other commands pass directly through to the native `agy` CLI binary:

```bash
agy_account models
agy_account --help
```

---

## Security Architecture

1. **Encryption Scheme:**
   - Cipher: `aes-256-cbc` with PBKDF2 key derivation (`openssl enc -aes-256-cbc -pbkdf2 -base64 -A`).
   - HMAC: SHA-256 hex digest calculated over ciphertext.
   - Storage format: `ENC:<hmac-sha256-hex>:<base64-aes-256-cbc-ciphertext>`.
2. **Key Storage:**
   - Stored in system keyring under service `"agy"` keyed by sanitized account name.
   - Fallback: Stored in `~/.gemini/antigravity-cli/keys/<account>.key` with mode `0600` (readable only by current user).
3. **Decryption Verification:**
   - Before passing ciphertext to OpenSSL for decryption, the HMAC is computed and checked in constant time using `hmac.compare_digest`.
   - Any tampering immediately aborts decryption with a `ValueError`.
4. **Active Token Hydration:**
   - On switch, the decrypted token is written to `~/.gemini/antigravity-cli/antigravity-oauth-token` with mode `0600`.
   - Existing active token is backed up prior to hydration.

---

## Running Unit Tests

Run the complete test suite with `pytest`:

```bash
pytest -v
```

Expected output:
```
tests/test_account_switch.py::AccountSwitchTest::test_add_and_list PASSED
tests/test_account_switch.py::AccountSwitchTest::test_add_encrypted_and_switch PASSED
tests/test_account_switch.py::AccountSwitchTest::test_invalid_account_name PASSED
tests/test_account_switch.py::AccountSwitchTest::test_overwrite PASSED
tests/test_account_switch.py::AccountSwitchTest::test_switch_and_remove PASSED
tests/test_account_switch.py::AccountSwitchTest::test_switch_nonexistent_account PASSED
tests/test_encryption.py::EncryptionTest::test_hmac_verification_and_tampering PASSED
tests/test_encryption.py::EncryptionTest::test_is_encrypted_helper PASSED
tests/test_encryption.py::EncryptionTest::test_keyring_fallback_file_and_permissions PASSED
tests/test_encryption.py::EncryptionTest::test_round_trip_various_tokens PASSED
```

---

## License

MIT License.
