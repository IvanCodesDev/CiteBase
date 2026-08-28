"""SourceAdapter 实现：file / dir（M1）。git / url / evidence 按里程碑追加。"""

from citebase.adapters.fs import DirSourceAdapter, FileSourceAdapter, adapter_for_path

__all__ = ["DirSourceAdapter", "FileSourceAdapter", "adapter_for_path"]
