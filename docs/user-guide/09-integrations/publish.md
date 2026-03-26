# Publishing Artifacts

After the pipeline finishes, use `scripts/publish.py` to push the generated artifacts to external systems. The script reads the output directory produced by `orchestrate.py` and can open a GitHub pull request with the generated code, post the design analysis and release notes back to Jira, or do both in a single run.

---

## Prerequisites

Before running the publish script, confirm you have:

- Completed at least one workflow run with `--output-dir` set, so the output directory exists and contains `state.json`
- The GitHub CLI (`gh`) installed and authenticated — required for `--push-code`
- The appropriate credentials in your `.env` file (see [Required Environment Variables](#required-environment-variables) below)

---

## Usage

```bash
uv run python scripts/publish.py --output-dir PATH [--push-code] [--push-jira] [--dry-run]
```

At least one of `--push-code` or `--push-jira` is required. The two flags can be combined in a single run.

---

## CLI Flags

| Flag | Required | Description |
|------|----------|-------------|
| `--output-dir PATH` | Yes | Directory containing pipeline artifacts (must contain `state.json`) |
| `--push-code` | No* | Push generated code and tests to the target GitHub repository as a PR |
| `--push-jira` | No* | Attach design analysis and post PR summary and release notes back to the originating Jira ticket |
| `--dry-run` | No | Print what would be done without making any API calls or git operations |

*At least one of `--push-code` or `--push-jira` must be specified.

---

## Required Environment Variables

### For `--push-code`

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GITHUB_TOKEN` | Yes | (none) | Personal access token with `Contents` (write) permission on the target repository |
| `TARGET_GITHUB_REPO` | Yes | (none) | Target repository in `org/repo` format, e.g. `openshift-builds/builds` |
| `TARGET_GITHUB_BASE_BRANCH` | No | `main` | The branch in the target repository that the generated PR targets |

Add these to your `.env` file:

```bash
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
TARGET_GITHUB_REPO=openshift-builds/builds
TARGET_GITHUB_BASE_BRANCH=main
```

To create a `GITHUB_TOKEN`: GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens. The token needs `Contents` (write) permission on the target repository so the script can push the new branch.

### For `--push-jira`

| Variable | Required | Description |
|----------|----------|-------------|
| `JIRA_BASE_URL` | Yes | Your Atlassian Cloud base URL, e.g. `https://your-org.atlassian.net` |
| `JIRA_USER_EMAIL` | Yes | The email address tied to your Jira API token |
| `JIRA_API_TOKEN` | Yes | Your Atlassian API token |

Add these to your `.env` file:

```bash
JIRA_BASE_URL=https://your-org.atlassian.net
JIRA_USER_EMAIL=your-email@company.com
JIRA_API_TOKEN=your-api-token-here
```

`--push-jira` also requires that `state.json` contains a `jira_ticket_id` field. This field is populated automatically when the pipeline is started with `--jira-ticket`. If the field is absent, the script exits with an error.

See [Jira & Rovo Integration](jira-rovo.md) for instructions on setting up Jira credentials and creating an API token.

---

## What Each Flag Does

### `--push-code`

Pushes the generated Go source files and test files to the target GitHub repository and opens a pull request.

Steps performed:

1. Reads `state.json` to extract the Jira ticket ID and issue title.
2. Collects all files under `output-dir/code/` and `output-dir/tests/`.
3. Shallow-clones `TARGET_GITHUB_REPO` into a temporary directory.
4. Creates a new branch named `feat/<ticket-id>-<slug-of-title>` from `TARGET_GITHUB_BASE_BRANCH`.
5. Copies code and test files to the repo root, preserving their relative paths.
6. Commits and pushes the branch.
7. Opens a PR using `docs/pr_description.md` from the output directory as the PR body. If that file is absent, a default body is generated.
8. Prints the PR URL.
9. Cleans up the temporary directory.

The commit message follows the Conventional Commits format: `feat(<ticket-id>): <issue title>`, truncated to 72 characters if necessary.

### `--push-jira`

Uploads design and documentation artifacts back to the originating Jira ticket.

Actions performed:

1. Attaches `design/design_analysis.md` as a file attachment on the ticket.
2. Posts the contents of `docs/pr_summary.md` as a ticket comment.
3. Posts the contents of `docs/release_notes.md` as a ticket comment, if the file is non-empty.

---

## Example Usage

**Preview what would happen without making any changes:**

```bash
uv run python scripts/publish.py \
  --output-dir ./output/SHIP-456 \
  --push-code \
  --dry-run
```

**Open a GitHub PR from the generated artifacts:**

```bash
uv run python scripts/publish.py \
  --output-dir ./output/SHIP-456 \
  --push-code
```

**Upload artifacts back to the Jira ticket:**

```bash
uv run python scripts/publish.py \
  --output-dir ./output/SHIP-456 \
  --push-jira
```

**Do both in a single run:**

```bash
uv run python scripts/publish.py \
  --output-dir ./output/SHIP-456 \
  --push-code \
  --push-jira
```

---

## Output Directory Layout

`publish.py` expects the output directory to have been produced by `orchestrate.py --output-dir`. The relevant files it reads are:

```text
output/SHIP-456/
  state.json              ← required by both --push-code and --push-jira
  code/                   ← read by --push-code
  tests/                  ← read by --push-code
  design/
    design_analysis.md    ← attached to Jira by --push-jira
  docs/
    pr_description.md     ← used as GitHub PR body by --push-code
    pr_summary.md         ← posted as Jira comment by --push-jira
    release_notes.md      ← posted as Jira comment by --push-jira (if non-empty)
```

Files that are missing are skipped with a warning rather than causing a hard failure, except for `state.json` which is required and causes an immediate exit if absent.

---

## Dry-Run Mode

Add `--dry-run` to any invocation to print what would be done without making API calls, creating branches, or modifying any external system.

```bash
uv run python scripts/publish.py \
  --output-dir ./output/SHIP-456 \
  --push-code \
  --push-jira \
  --dry-run
```

Sample output:

```text
-- push-code -------------------------------------------------------
  Target repo:   openshift-builds/builds
  Base branch:   main
  New branch:    feat/ship-456-add-timeout-support-to-buildrun
  Commit msg:    feat(SHIP-456): Add timeout support to BuildRun
  Code files:    4
  Test files:    2

  [dry-run] Would clone, copy files, commit, push, and open a PR.
  [dry-run] Branch:  feat/ship-456-add-timeout-support-to-buildrun
  [dry-run] Commit:  feat(SHIP-456): Add timeout support to BuildRun
  [dry-run] Repo:    https://github.com/openshift-builds/builds

-- push-jira -------------------------------------------------------
  Ticket: SHIP-456
  [dry-run] Would attach design/design_analysis.md to SHIP-456
  [dry-run] Would post PR summary comment to SHIP-456
  [dry-run] Would post release notes comment to SHIP-456
```

---

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `state.json not found` | `--output-dir` does not contain a completed pipeline run | Run `orchestrate.py --output-dir PATH` first |
| `TARGET_GITHUB_REPO is not set` | Missing environment variable | Add `TARGET_GITHUB_REPO=org/repo` to `.env` |
| `GITHUB_TOKEN is not set` | Missing environment variable | Add `GITHUB_TOKEN=ghp_...` to `.env` |
| `git push failed — branch may already exist` | A branch with the same name was pushed previously | Delete the remote branch and retry, or rerun the pipeline to generate a new branch name |
| `Missing required environment variable(s): JIRA_BASE_URL, ...` | One or more Jira variables absent | Add the missing variables to `.env` |
| `jira_ticket_id not found in state.json` | Pipeline was not started with `--jira-ticket` | Re-run `orchestrate.py` with `--jira-ticket TICKET-ID --output-dir PATH` |
| `Failed to attach design_analysis.md (HTTP 401/403)` | Jira credentials are wrong or expired | Verify `JIRA_USER_EMAIL` and `JIRA_API_TOKEN` in `.env`; regenerate the token if needed |

---

[← Previous: Jira & Rovo Integration](jira-rovo.md) | [Back to Index →](../README.md)
