"""Repository-relative local paths (D171).

One folder holds the repo and, under the git-ignored ``local/``, every non-git item:
``local/data`` (current), ``local/evidence`` (cited), ``local/archive`` (old generations).
The root is the repository root, overridable with ``AMIDST_ROOT``. Nothing here reads a
marker file or looks up the home directory for a default.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
PATH_MAP = PACKAGE_ROOT / 'configs/local_path_map_v1.json'
DEFAULT_OWNED_ROOT = 'local/data/demo-owned-v1'
SEARCH_AREAS = ('data', 'evidence', 'archive')
_WINDOWS = re.compile(r'^[A-Za-z]:[\\/]|^\\\\')


class OwnedRootNotFound(ValueError):
    pass


class ArtifactNotFound(LookupError):
    pass


class ArtifactAmbiguous(LookupError):
    pass


def _alternates_source(root: Path) -> Path | None:
    """The ``git clone --shared`` source checkout, read from objects/info/alternates."""
    try:
        text = (root / '.git/objects/info/alternates').read_text(encoding='utf-8')
    except OSError:
        return None
    for line in text.splitlines():
        line = line.strip()
        if line:
            objects = Path(line)
            if objects.name == 'objects' and objects.parent.name == '.git':
                return objects.parent.parent
    return None


def amidst_root() -> Path:
    env = os.environ.get('AMIDST_ROOT')
    if env:
        return Path(env).expanduser().resolve()
    return PACKAGE_ROOT


def local_dir() -> Path:
    """``<root>/local``; a shared clone without its own ``local/`` uses its source's."""
    root = amidst_root()
    own = root / 'local'
    if own.is_dir():
        return own.resolve()
    source = _alternates_source(root)
    if source is not None and (source / 'local').is_dir():
        return (source / 'local').resolve()
    return own.resolve()


def data_dir() -> Path:
    return local_dir() / 'data'


def evidence_dir() -> Path:
    return local_dir() / 'evidence'


def archive_dir() -> Path:
    return local_dir() / 'archive'


def demo_owned_root(config_value: str | None = None) -> Path:
    """``AMIDST_DEMO_HOME``, else the config ``owned_root`` relative to the root.

    The result is absolute but not ``resolve()``d, so callers can still reject a
    symlinked root (the canonical-owned-root check). The directory must exist.
    """
    explicit = os.environ.get('AMIDST_DEMO_HOME')
    if explicit:
        raw, origin = explicit, 'AMIDST_DEMO_HOME'
    else:
        if config_value is None:
            config = json.loads((PACKAGE_ROOT / 'configs/demo_integration_local.json').read_text(encoding='utf-8'))
            config_value = config['owned_root']
        raw, origin = config_value or DEFAULT_OWNED_ROOT, 'config owned_root'
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = amidst_root() / path
    path = Path(os.path.normpath(path))
    if not path.is_dir():
        raise OwnedRootNotFound(
            f'OWNED_ROOT_NOT_FOUND: {path} (from {origin}). Set AMIDST_DEMO_HOME to the owned '
            f'demo package, or place it at <repo>/{DEFAULT_OWNED_ROOT}.')
    return path


def office_canonical_root() -> Path | None:
    """``OFFICE_ASSETS_REPO``, else ``local/archive/office-canonical`` when it exists."""
    env = os.environ.get('OFFICE_ASSETS_REPO')
    if env:
        return Path(env).expanduser().resolve()
    candidate = archive_dir() / 'office-canonical'
    return candidate if candidate.is_dir() else None


def artifacts_output_root() -> Path:
    """Where new artifacts may be written: ``AMIDST_ARTIFACTS``, else ``local/evidence``."""
    env = os.environ.get('AMIDST_ARTIFACTS')
    return Path(env).expanduser().resolve() if env else evidence_dir()


def locate_artifact(name: str) -> Path:
    """The unique ``name`` below ``local/{data,evidence,archive}``."""
    part = PurePosixPath(name)
    if part.is_absolute() or not part.parts or '..' in part.parts:
        raise ValueError('ARTIFACT_NAME_MUST_BE_RELATIVE')
    found = [local_dir() / area / part for area in SEARCH_AREAS if (local_dir() / area / part).exists()]
    if not found:
        raise ArtifactNotFound(f'ARTIFACT_NOT_FOUND: {name} (searched local/{{data,evidence,archive}})')
    if len(found) > 1:
        raise ArtifactAmbiguous('ARTIFACT_AMBIGUOUS: ' + ', '.join(str(x) for x in found))
    return found[0].resolve()


def _parts(value) -> tuple[PurePath, tuple[str, ...], bool]:
    if isinstance(value, PurePath):
        path = value
    else:
        text = str(value)
        path = PureWindowsPath(text) if _WINDOWS.match(text) else PurePosixPath(text)
    return path, path.parts, isinstance(path, PureWindowsPath)


def relative_to_root(value, root) -> str | None:
    """``value`` below ``root`` as a posix relative path, matching whole components only."""
    _, parts, windows = _parts(value)
    _, root_parts, root_windows = _parts(root)
    if windows != root_windows or len(parts) < len(root_parts):
        return None
    fold = (lambda s: s.lower()) if windows else (lambda s: s)
    if [fold(p) for p in parts[:len(root_parts)]] != [fold(p) for p in root_parts]:
        return None
    return '/'.join(parts[len(root_parts):])


def _tilde(text: str, home: str) -> str:
    """Canonical form: ``~/x`` when below ``home``, else the text itself."""
    if text == '~' or text.startswith('~/'):
        return text
    rest = relative_to_root(PurePosixPath(text), PurePosixPath(home))
    if rest is None:
        return text
    return '~/' + rest if rest else '~'


def _entries(path_map=None) -> list[dict]:
    data = path_map if path_map is not None else json.loads(PATH_MAP.read_text(encoding='utf-8'))
    return sorted(data['entries'], key=lambda e: len(PurePosixPath(e['old']).parts), reverse=True)


def resolve_legacy(value, *, home=None, path_map=None) -> Path | None:
    """Map an old absolute path to its new place under the root, longest prefix first.

    ``~`` means ``home`` (default: the user's home); map entries and input are compared
    in ``~`` form. Matching is per path component, so ``…/d133-bench`` never matches
    ``…/d133-bench-pilot``. Returns ``None`` when no entry covers the path; the new
    location may or may not exist.
    """
    path, _, windows = _parts(value)
    if windows:
        return None
    home = str(home or Path.home())
    target = PurePosixPath(_tilde(str(path), home))
    for entry in _entries(path_map):
        rest = relative_to_root(target, PurePosixPath(_tilde(entry['old'], home)))
        if rest is not None:
            result = amidst_root() / entry['new']
            return result / rest if rest else result
    return None
