---
id: card-pitfall-stale-editable-install
kind: pitfall
name: 更名后可编辑安装失效
summary: 项目目录改名后 venv 里的 editable 安装仍指旧绝对路径，导入随即报错。
aliases:
- editable install
- ModuleNotFoundError
tags:
- 工程实践
links:
- predicate: related_to
  to: card-pitfall-typestub-drift
claims:
- id: c1
  text: 整仓更名后，虚拟环境里的可编辑安装仍指向更名前的旧目录，导致 pytest 报 ModuleNotFoundError。
  sources:
  - source: src-dev-log
    loc: extracted/text.md#L5-L5
    span_sha256: e9d11a56fd915598ebfe019f65db01cb78aa9ad46642c7afcf26af634d0f77a4
- id: c2
  text: 可编辑安装在 site-packages 里写的是绝对路径，项目目录改名后必须重新安装一次才能生效。
  sources:
  - source: src-dev-log
    loc: extracted/text.md#L6-L6
    span_sha256: 5b3e873c203e80b9262a2c6b93da17b8cdedc2096cf434df498e0476849781db
- id: c3
  text: 更名残留最容易漏在被 gitignore 的本地配置里，排查要用 --no-ignore 连同被忽略文件一起全库搜索。
  sources:
  - source: src-dev-log
    loc: extracted/text.md#L7-L8
    span_sha256: 0229f3ac455f8f86ff8bc87367bb982e3b900966d32ac0f7274901e6216031d7
version: 1
status: active
schema_version: '0.1'
---

## 现象

项目目录更名（CardVault → CiteBase）后运行测试，conftest 导入直接失败：`ModuleNotFoundError: No module named 'citebase'`，报错栈里还出现旧目录路径。

## 根因

`pip install -e` 写进 site-packages 的 `.pth` / direct_url 记录的是绝对路径；目录改名后这些指针悬空，Python 解释器找不到包。

## 规避

目录更名或迁移后立即重装：`uv pip install -e ".[dev]"`；同时用 `rg --no-ignore` 全库搜索旧名，被 gitignore 的本地配置（如 MCP 的 --workspace 参数）最容易漏。

## 触发条件

任何改变仓库根路径的操作：目录改名、盘符迁移、克隆到新位置后复用旧 venv。

## 关联

同日另一起「本地与 CI 环境不一致」事故见「第三方类型存根漂移」。
