# Local layout: one folder, `~/amidst` (D171)

Status: code and tests for the relative paths are in this PR. The folder move itself is a separate, later step (D179).

## Layout

- `~/amidst` is the git repo itself (branch `main`). Everything that is not in git goes under its git-ignored `local/`:
  `local/data` (current), `local/evidence` (cited), `local/archive` (old generations, old checkouts), plus `local/logs`, `local/env-templates` and `local/demo-pin.json`.
- `.venv/`, `.local/` and `tests/browser/core-preview/node_modules` stay at the repo-relative paths the launchers already use.

## How code finds things (`src/amidst/paths.py`)

| Function | Result |
| --- | --- |
| `amidst_root()` | `AMIDST_ROOT`, else the repository root. No marker file, no home lookup. |
| `local_dir()`, `data_dir()`, `evidence_dir()`, `archive_dir()` | Below the root. A `--shared` clone without its own `local/` uses its clone source's `local/` (read from `objects/info/alternates`). |
| `demo_owned_root(config_value)` | `AMIDST_DEMO_HOME`, else `owned_root` from `configs/demo_integration_local.json` (`local/data/demo-owned-v1`, relative to the root). A missing directory raises `OWNED_ROOT_NOT_FOUND` and names `AMIDST_DEMO_HOME`. The path is not `resolve()`d, so the canonical-owned-root check still rejects a symlinked root. |
| `artifacts_output_root()` | `AMIDST_ARTIFACTS`, else `local/evidence`. |
| `locate_artifact(name)` | The unique match below `local/{data,evidence,archive}`; `ArtifactNotFound` or `ArtifactAmbiguous` otherwise. |
| `resolve_legacy(path)` | Old absolute or `~/` path to its new place, from `configs/local_path_map_v1.json` (longest prefix, whole path components only). Historical locators in pinned records are never edited; they resolve through this map. |
| `office_canonical_root()` | `OFFICE_ASSETS_REPO`, else `local/archive/office-canonical` if it exists. |

Before the move, set `AMIDST_DEMO_HOME` to the real owned package (for example `~/amidst-artifacts/demo-owned-v1`) and `AMIDST_ARTIFACTS` to the old artifacts folder; nothing else changes. `start_all_demo.command` falls back to the old locations only while the new ones do not exist yet.

## Demo pin

`scripts/demo_pin.py approve --approved-by NAME --gate RESULT.txt` writes `local/demo-pin.json` for a clean tree and a passing, fresh `verify_gate.sh` result. `start_445_demo.command` runs `demo_pin.py check`: with a pin file, HEAD must equal the pin and the tree must be clean (`AMIDST_DEMO_ALLOW_UNPINNED=1` for QA ports only). Without a pin file it starts as before.

## Session scripts (`scripts/local/`, not installed by this PR)

`sync_main.sh` with `com.amidst.sync-main.plist` (fetch every 10 minutes; fast-forward `main` only when every guard passes), `env_templates.sh` (relocatable `.venv` and `node_modules` templates copied with `cp -c`) and `session_bootstrap.sh` (disk check, `--shared` clone, templates, `session.env`). Nothing here installs launchd or builds templates.

## Proposed wording for AGENTS.md and CLAUDE.md (NOT applied)

`AGENTS.md` and `CLAUDE.md` are pinned by `configs/architecture/authority_pins_v1.json` (#306). The guard (`check_architecture_guard.py`) fails any change to their bytes without an authority pin and a change receipt tied to a user authorization comment. This PR therefore leaves both files untouched. Text to add once the user authorizes that change:

- Clone source is `~/amidst`: `git clone --shared ~/amidst <scratchpad>/repo`, with `origin` set to the GitHub remote.
- Never edit `~/amidst` directly. It runs the demo and holds `local/`.
- Never run `git clean -ffdx`, `git checkout .` or `git reset` in `~/amidst`.
- New sessions may start with `bash ~/amidst/scripts/local/session_bootstrap.sh <task-name>`.
