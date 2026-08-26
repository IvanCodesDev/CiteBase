---
id: card-method-quality-gates-ci
kind: method
name: CI 六道质量门
summary: 双平台跑 ruff / mypy / pytest 加示例库 lint / index / eval；评测线 0.8。
aliases:
- quality gates
- CI 质量门
tags:
- 工程实践
- 治理
links:
- predicate: related_to
  to: card-decision-git-source-of-truth
- predicate: pitfall
  to: card-pitfall-typestub-drift
claims:
- id: c1
  text: CI 在 ubuntu 与 windows 双平台跑六道门：ruff、mypy（strict）、pytest、示例库 lint、index、eval。
  sources:
  - source: src-release-notes
    loc: extracted/text.md#L11-L11
    span_sha256: 576a6359f0ffb2373d41397d60686ca1c35f6902f50812ec3a2eeacc71e9c82a
- id: c2
  text: vault 的 _index JSON 是提交物，一致性由 vault index --check 校验（L-IDX-1）；index.sqlite 是本地缓存不入库。
  sources:
  - source: src-release-notes
    loc: extracted/text.md#L12-L12
    span_sha256: df2ad630eae6f81eaea7e68225ae5035abebfe8a86f2aca9cd8bfa7a06393c20
- id: c3
  text: golden set 命中率与首位命中率的评测验收线都不得低于 0.8。
  sources:
  - source: src-release-notes
    loc: extracted/text.md#L13-L13
    span_sha256: 41371b793df0245bdb602ea6e472da8161f5ed65d430a9875ebc6992a951913d
version: 1
status: active
schema_version: '0.1'
---

## 是什么

提交合入前的机器质量闸：静态检查、类型检查、单元测试，加上每个示例 vault 的结构 lint、索引一致性与 golden 集评测。

## 何时用

每次 push 与 pull request 自动触发；本地提交前手动跑同一组命令可以提前暴露问题。

## 怎么用

`python -m ruff check .`、`python -m mypy`、`python -m pytest tests -q`，然后对每个 vault 依次
`vault lint`、`vault index --check`、`vault eval --min-hit 0.8 --min-first 0.8`。

## 边界与陷阱

CI 是全新安装环境，本地依赖版本若落后于 PyPI 最新版会出现「本地绿、CI 红」；Windows 平台还有编码与 shell 语义差异。

## 关联

索引为什么必须以提交物形态核验，见「Git 是唯一事实源」。
