"""文件系统源适配器：file（单文件）与 dir（目录树）。

revision 一律是内容哈希（sha256:…），可比较相等性；changed_since 通过重算实现，
因此永远能给出确定答案（返回 bool 而非 None）。
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

_IGNORED_DIR_PARTS = {".git", "__pycache__", ".venv"}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


class FileSourceAdapter:
    """单个文件即一个源。"""

    name = "file"

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)

    def resolve(self) -> str:
        resolved = self._path.resolve()
        if not resolved.is_file():
            raise FileNotFoundError(f"源文件不存在：{resolved}")
        return str(resolved)

    def revision(self) -> str:
        self.resolve()
        return f"sha256:{_sha256_file(self._path)}"

    def changed_since(self, revision: str) -> bool | None:
        return self.revision() != revision

    def fetch(self, originals_dir: Path) -> list[Path]:
        self.resolve()
        originals_dir.mkdir(parents=True, exist_ok=True)
        dest = originals_dir / self._path.name
        shutil.copyfile(self._path, dest)
        return [dest]


class DirSourceAdapter:
    """目录树即一个源：revision 为全部常规文件（路径 + 内容哈希）的合并哈希。"""

    name = "dir"

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)

    def resolve(self) -> str:
        resolved = self._path.resolve()
        if not resolved.is_dir():
            raise FileNotFoundError(f"源目录不存在：{resolved}")
        return str(resolved)

    def _files(self) -> list[Path]:
        files = []
        for candidate in sorted(self._path.rglob("*")):
            if not candidate.is_file():
                continue
            rel_parts = candidate.relative_to(self._path).parts
            if any(part.startswith(".") or part in _IGNORED_DIR_PARTS for part in rel_parts):
                continue
            files.append(candidate)
        return files

    def revision(self) -> str:
        self.resolve()
        digest = hashlib.sha256()
        for file in self._files():
            rel = file.relative_to(self._path).as_posix()
            digest.update(rel.encode("utf-8"))
            digest.update(b"\0")
            digest.update(_sha256_file(file).encode("ascii"))
            digest.update(b"\n")
        return f"sha256:{digest.hexdigest()}"

    def changed_since(self, revision: str) -> bool | None:
        return self.revision() != revision

    def fetch(self, originals_dir: Path) -> list[Path]:
        self.resolve()
        copied = []
        for file in self._files():
            rel = file.relative_to(self._path)
            dest = originals_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(file, dest)
            copied.append(dest)
        return copied


def adapter_for_path(path: Path | str) -> FileSourceAdapter | DirSourceAdapter:
    """auto 模式：目录走 dir，其余走 file。"""
    target = Path(path)
    if target.is_dir():
        return DirSourceAdapter(target)
    return FileSourceAdapter(target)
