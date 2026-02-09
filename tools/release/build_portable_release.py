#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import zipfile

EXCLUDE_DIRS = {
    '.git', '.github', '__pycache__',
    'build', 'dist', 'installer_output', 'installer',
    'data', 'updates',
}
EXCLUDE_SUFFIXES = {'.pyc', '.pyo', '.log'}


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def should_exclude(path: Path, root: Path) -> bool:
    rel = path.relative_to(root)
    parts = set(rel.parts)
    if parts & EXCLUDE_DIRS:
        return True
    if path.suffix in EXCLUDE_SUFFIXES:
        return True
    return False


def zip_dir(src_root: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for p in src_root.rglob('*'):
            if p.is_dir():
                continue
            if should_exclude(p, src_root):
                continue
            rel = p.relative_to(src_root)
            z.write(p, rel.as_posix())


def main() -> int:
    repo = Path(os.environ.get('GITHUB_WORKSPACE', '.')).resolve()
    tag = os.environ.get('GITHUB_REF_NAME', 'dev')
    version = tag.lstrip('vV')

    out_dir = repo / 'release_out'
    out_dir.mkdir(parents=True, exist_ok=True)

    zip_name = f'Budgetmanager_latest_PORTABLE_SLIM_SOURCE_{version}.zip'
    zip_path = out_dir / zip_name

    zip_dir(repo, zip_path)
    digest = sha256_file(zip_path)

    repo_name = os.environ.get('GITHUB_REPOSITORY', 'sloogy/Budgetmanager')
    base_url = f'https://github.com/{repo_name}/releases/download/{tag}'

    latest = {
        'app': 'BudgetManager',
        'channel': 'stable',
        'version': version,
        'release_tag': tag,
        'assets': {
            'windows': {
                'type': 'portable-source',
                'url': f'{base_url}/{zip_name}',
                'sha256': digest,
            },
            'linux': {
                'type': 'portable-source',
                'url': f'{base_url}/{zip_name}',
                'sha256': digest,
            },
        },
    }

    (out_dir / 'latest.json').write_text(json.dumps(latest, indent=2), encoding='utf-8')
    (out_dir / 'sha256sums.txt').write_text(f'{digest}  {zip_name}\n', encoding='utf-8')

    print('ZIP:', zip_path)
    print('SHA256:', digest)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
