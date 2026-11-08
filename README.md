# agy-multiaccount-encrypted

Multi-account manager with OpenSSL AES-256-CBC encryption and HMAC integrity verification for the **Google Antigravity CLI** (`agy`).

---

## Features

- **Multi-Account Profile Management:** Easily add, list, switch, and delete multiple Antigravity authentication profiles.
- **Browser-Based OAuth & Zero Copy-Paste:** Interactively authenticate new accounts directly via Google OAuth in your browser (`login`), or instantly snapshot your active session (`capture`), completely eliminating manual JSON copying.
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
elif [ "$1" = "add" ] || [ "$1" = "list" ] || [ "$1" = "switch" ] || [ "$1" = "remove" ] || [ "$1" = "capture" ] || [ "$1" = "login" ]; then
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

### 1. Browser-Based Authentication (Zero Token Copy-Paste)

You never need to manually copy, inspect, or paste raw JSON tokens or secrets. The tool provides two native browser authentication workflows:

#### A. Interactive Browser Sign-In (`login`)
Sign into a brand new Google account directly from your browser. The switcher temporarily clears the active token and triggers the Antigravity browser OAuth flow. Once you approve the prompt in your browser, the credentials and associated Google email are automatically saved under `<name>`.

```bash
# Interactive login with automatic AES-256-CBC encryption
agy_account account login work --encrypt

# Plain unencrypted login
agy_account account login work

# Overwrite existing profile if already present
agy_account account login work --encrypt --force
```

**Example Output:**
```
Starting browser authentication for account 'work'...
Executing '/home/faizen/.local/bin/agy models' to trigger browser OAuth flow...
Please visit the following URL to authenticate:
https://accounts.google.com/o/oauth2/auth?...
Successfully logged in and saved account 'work' [user@domain.com] (encrypted).
```

> [!NOTE]
> If authentication is aborted or cancelled (e.g. browser closed or `Ctrl+C`), your previous active session is automatically restored without any data loss.

#### B. Snapshot Active Browser Session (`capture`)
If you have already signed into Antigravity via `agy` in your browser and want to save the active session into a named account profile:

```bash
# Capture active session with encryption
agy_account account capture dev --encrypt

# Plain unencrypted capture
agy_account account capture dev

# Overwrite an existing account
agy_account account capture dev --force --encrypt
```

**Example Output:**
```
Captured active session into account 'dev' [developer@domain.com] (encrypted).
```

You can also use the `add` alias with `--from-current`:
```bash
agy_account account add dev --from-current --encrypt
```

> [!TIP]
> Both `login` and `capture` automatically extract your Google email address from the OAuth token payload (`id_token_email`) for audit logging and confirmation display.

### 2. Manual Token Addition (Direct / CI)

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

### 3. Switching Active Account

Switching decrypts the token (if encrypted) and atomically writes the decrypted token into `~/.gemini/antigravity-cli/antigravity-oauth-token` with `0600` mode, updating `current_account.txt`:

```bash
agy_account account switch dev
```

### 4. Listing Accounts

```bash
agy_account account list
```

Output:
```
dev
personal
```

### 5. Removing an Account

Creates a backup of the token before unlinking it:

```bash
agy_account account remove old-account
```

### 6. Native Antigravity Passthrough

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
tests/test_account_switch.py::AccountSwitchTest::test_capture_account_encrypted PASSED
tests/test_account_switch.py::AccountSwitchTest::test_capture_account_with_json_and_email PASSED
tests/test_account_switch.py::AccountSwitchTest::test_capture_nonexistent_or_empty_token PASSED
tests/test_account_switch.py::AccountSwitchTest::test_capture_overwrite_behavior PASSED
tests/test_account_switch.py::AccountSwitchTest::test_cli_add_missing_token_error PASSED
tests/test_account_switch.py::AccountSwitchTest::test_cli_capture_and_add_from_current PASSED
tests/test_account_switch.py::AccountSwitchTest::test_invalid_account_name PASSED
tests/test_account_switch.py::AccountSwitchTest::test_login_account_failure_restores_backup PASSED
tests/test_account_switch.py::AccountSwitchTest::test_login_account_success PASSED
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
