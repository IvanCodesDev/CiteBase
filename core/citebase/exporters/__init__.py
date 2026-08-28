"""导出器（M4）：site（静态站点）与 json（产品快照）。

导出遵循检索同一套可见性：默认排除 suspect / superseded / retired
（宁可少说话，不说过期话），``include_hidden`` 才全量；被引源许可证为
unknown 时输出警示清单（威胁模型 §5 的合规联动）。
"""

from __future__ import annotations

from citebase.exporters.json_snapshot import build_snapshot, export_json
from citebase.exporters.site import export_site

__all__ = ["build_snapshot", "export_json", "export_site"]
