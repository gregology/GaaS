# gaas-github

The GitHub integration. Handles pull requests and issues via the `gh` CLI. All imports point at `gaas_sdk.*`, not `app.*`.

Discovered at startup via Python entry points. Can be shadowed by a local override during development.

## Structure

```
src/gaas_github/
  __init__.py
  client.py                  # GitHub API client (wraps gh CLI)
  entity_store.py            # GitHubEntityStore base class for PR and issue stores
  manifest.yaml
  platforms/
    pull_requests/
      __init__.py            # Exports HANDLERS dict
      check.py               # Entry task: discover new/updated PRs
      collect.py             # Fetch PR details, diff, comments
      classify.py            # LLM classification
      evaluate.py            # Evaluate automations
      act.py                 # Execute actions (currently no write actions)
      store.py               # PullRequestStore
      const.py               # Safety constants
      templates/
        classify.jinja
    issues/
      __init__.py
      check.py
      collect.py
      classify.py
      evaluate.py
      act.py
      store.py               # IssueStore
      const.py
      templates/
        classify.jinja
```

## Safety constants

**Pull requests** (`platforms/pull_requests/const.py`):
- DETERMINISTIC_SOURCES: `org`, `repo`, `author`, `status`, `additions`, `deletions`, `changed_files`
- IRREVERSIBLE_ACTIONS: empty (no write actions yet)
- SIMPLE_ACTIONS: empty

**Issues** (`platforms/issues/const.py`):
- DETERMINISTIC_SOURCES: `org`, `repo`, `author`, `state`, `labels`, `comment_count`
- IRREVERSIBLE_ACTIONS: empty
- SIMPLE_ACTIONS: empty

Both platforms are read-only right now. When write actions are added, categorize by reversibility tier first.

## Key patterns

**`gh` CLI as API client**: `client.py` shells out to `subprocess.run(["gh", "api", ...])`. The `gh` CLI handles auth (OAuth device flow, SSH keys, token storage), rate limiting, and pagination. Hard dependency on `gh` being installed and authenticated.

**GitHubEntityStore**: Base class in `entity_store.py` shared by `PullRequestStore` and `IssueStore`. Provides `find`, `find_anywhere`, `active_keys`, `update`, `move_to_synced`, `restore_to_active` -- all keyed by `(org, repo, number)`. Each subclass overrides only `save()` with entity-specific field mappings.

**Filename convention**: `{org}__{repo}__{number}.md`. Double underscore because org and repo names can contain hyphens.

## Tests

Currently only `tests/__init__.py`. Tests for the GitHub integration live in the main test suite under `tests/safety/` (provenance and automation invariant tests cover GitHub's safety constants).

When adding GitHub-specific tests, put them in `packages/gaas-github/tests/` and import from `gaas_sdk.*` directly.
