# GitHub Integration

Tracks pull requests where your review is requested. Classifies each PR by complexity, risk, and whether it's documentation-only.

Requires the [`gh` CLI](https://cli.github.com/) installed and authenticated (`gh auth login`).

## Quick Start

```yaml
integrations:
  - type: github
    name: my_repos
    schedule:
      every: 30m
```

## Configuration Reference

```yaml
integrations:
  - type: github
    name: my_repos                  # Unique name used in logs and note paths
    schedule:
      every: 30m                    # or: cron: "0 8-18 * * 1-5"
    llm: default                    # LLM profile name from the llms: section
    orgs: [myorg]                   # Optional: restrict to specific organizations
    repos: [myorg/myrepo]           # Optional: restrict to specific repositories
    include_mentions: false         # Include PRs that mention you (noisy, default: false)
    classifications: ...            # Optional — defaults are used if omitted
```

`orgs` and `repos` can be combined. If both are set, PRs matching either are included.

## Classifications

Classifications are LLM-driven assessments stored in each PR's note frontmatter.

### Default Classifications

| Key | Type | Prompt |
|-----|------|--------|
| `classification.complexity` | confidence | How complex is this PR to review? 0 = trivial typo fix, 1 = major architectural change. |
| `classification.risk` | confidence | How risky is this change to production systems? 0 = no risk, 1 = high risk of breaking things. |
| `classification.documentation_only` | boolean | Is this primarily a documentation or configuration change? |

### Custom Classifications

```yaml
classifications:
  # Shorthand: string becomes a confidence classification (0–1)
  complexity: how complex is this PR to review?

  # Boolean
  documentation_only:
    prompt: is this primarily a documentation change?
    type: boolean

  # Enum
  category:
    prompt: what type of change is this?
    type: enum
    values: [feature, bugfix, refactor, docs, chore]
```

## Pipeline

```
github.check (entry task)
  Fetches all PRs where review is requested (@me) from GitHub.
  Compares against locally tracked PRs:
    - PRs no longer requiring attention are moved to synced/.
  Enqueues github.collect for every active PR.

github.collect (priority 3)
  Fetches PR metadata (title, status, author, additions, deletions, changed files).
  Creates or updates the PR note in the store.
  If the PR is unclassified, enqueues github.classify_pr.

github.classify_pr (priority 6)
  Fetches the full PR description and diff (truncated to 10,000 characters).
  Renders a classification prompt with salt-based injection defense.
  Calls the LLM and validates structured output.
  Updates the PR note frontmatter with classification results.
```

### Note Store Layout

```
notes/github/pull_requests/{integration-name}/
  myorg__myrepo__42.md     # Active PRs requiring review
  myorg__myrepo__38.md
  synced/
    myorg__myrepo__35.md   # Merged, closed, or no longer assigned
```

Each note is a markdown file with YAML frontmatter containing PR metadata and classification results.

## Current Status

Classification is fully implemented. Automation rules (`when`/`then`) are not yet supported for GitHub — classification results are stored but not acted upon. This mirrors the email integration's pattern and will be added in a future phase. The expectation is that the human will setup some rules based approach in their notes tool to order these pull requests. Some automations that we may introduce in the future is creating a time block calendar event for particular pull requests.
