# Git + GitHub Setup for Claude Code on Windows

This guide ensures that Claude Code can execute `git clone`, `git pull`, `git push`
and all other git network operations without hanging or failing.

**Problem:** Claude Code runs commands in a non-interactive terminal. The default
Windows Git configuration uses credential helpers and TLS backends that require
interactive prompts or GUI popups, causing git to hang silently.

---

## Prerequisites

- [Git for Windows](https://git-scm.com/download/win) installed
- [GitHub CLI (`gh`)](https://cli.github.com/) installed
- Claude Code (Claude Desktop App) installed

---

## Step-by-Step Setup

### 1. Authenticate GitHub CLI

Open PowerShell and run:

```powershell
gh auth login
```

Follow the prompts (choose GitHub.com, HTTPS, authenticate via browser).
Verify it works:

```powershell
gh auth status
```

### 2. Fix TLS Backend

Windows Git defaults to Schannel for TLS, which can fail on certificate revocation
checks in non-interactive terminals. Switch to OpenSSL:

```powershell
git config --global http.sslBackend openssl
```

### 3. Configure Credential Storage

Set the file-based credential store (instead of Windows Credential Manager):

```powershell
git config --global credential.helper store
```

**Important:** Remove any host-specific credential helpers that `gh auth setup-git`
may have added (these use `gh.exe` interactively and will hang):

```powershell
git config --global --unset-all credential.https://github.com.helper
git config --global --unset-all credential.https://gist.github.com.helper
```

Also check if there is a system-level credential manager configured:

```powershell
git config --system --list | findstr credential
```

If you see `credential.helper=manager`, remove it (requires Admin PowerShell):

```powershell
# Run in Administrator PowerShell:
git config --system --unset credential.helper
```

### 4. Store GitHub Token in Credentials File

```powershell
$token = gh auth token
"https://<your-github-username>:$token@github.com" | Out-File -FilePath "$env:USERPROFILE\.git-credentials" -Encoding ascii -NoNewline
```

Replace `<your-github-username>` with your actual GitHub username.

### 5. Clone a Repository (with workaround)

For repositories where the file-based credential store still causes issues
(the `store` helper can hang on the post-fetch credential save step), configure
the cloned repo to disable the credential helper locally:

```powershell
# Clone normally (this works because credentials are in the URL after step 4)
git clone https://<your-github-username>:<token>@github.com/<owner>/<repo>.git

# Then disable credential helper locally for this repo
cd <repo>
git config --local credential.helper ""
```

Or as a one-liner:

```powershell
$token = gh auth token
git clone "https://<your-github-username>:$token@github.com/<owner>/<repo>.git"
cd <repo>
git config --local credential.helper ""
```

### 6. For Existing Repos

If you already have a cloned repo where git hangs:

```powershell
cd <repo-directory>

# Embed token in remote URL
$token = gh auth token
git remote set-url origin "https://<your-github-username>:$token@github.com/<owner>/<repo>.git"

# Disable credential helper for this repo
git config --local credential.helper ""
```

---

## Verification

After setup, test from Claude Code (or any non-interactive terminal):

```bash
# These should all work without hanging:
git fetch origin
git pull origin main
git push origin main
```

---

## Token Refresh

The `gh` token may expire. If git operations start failing with 401 errors,
refresh the token:

```powershell
gh auth refresh
$token = gh auth token
"https://<your-github-username>:$token@github.com" | Out-File -FilePath "$env:USERPROFILE\.git-credentials" -Encoding ascii -NoNewline
```

Also update the remote URL in each repo:

```powershell
cd <repo-directory>
$token = gh auth token
git remote set-url origin "https://<your-github-username>:$token@github.com/<owner>/<repo>.git"
```

---

## Summary of Git Config

After setup, your global git config should contain:

```ini
[http]
    sslBackend = openssl

[credential]
    helper = store
```

And each repo's local config should contain:

```ini
[credential]
    helper =

[remote "origin"]
    url = https://<username>:<token>@github.com/<owner>/<repo>.git
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Git hangs on clone/push/pull | Credential helper waiting for interactive input | `git config --local credential.helper ""` |
| `CRYPT_E_NO_REVOCATION_CHECK` error | Windows Schannel TLS issue | `git config --global http.sslBackend openssl` |
| 401 Unauthorized | Expired token | Run token refresh steps above |
| `gh auth git-credential get` hangs | Host-specific gh credential helper | `git config --global --unset-all credential.https://github.com.helper` |
