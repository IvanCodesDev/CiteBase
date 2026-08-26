---
id: card-method-commit-hooks
kind: method
name: 提交规范钩子
summary: pre-commit 钩子强制提交身份并拦截 docs、缓存与本地配置入库。
aliases:
- pre-commit
- 提交钩子
tags:
- 工程实践
- 发布
links:
- predicate: related_to
  to: card-decision-docs-private
claims:
- id: c1
  text: 公开提交的作者与提交者身份固定为 IvanCodesDev，由 pre-commit 钩子强制校验。
  sources:
  - source: src-release-notes
    loc: extracted/text.md#L6-L6
    span_sha256: 7eb2f6aa79ce479888815317d9453c2f544c09e1eac97aa16e4bc5a51b52e05f
- id: c2
  text: pre-commit 钩子同时拦截 docs/、本地配置、缓存与生成物路径进入暂存区；版本化副本在 .githooks/。
  sources:
  - source: src-release-notes
    loc: extracted/text.md#L7-L7
    span_sha256: 3575b37e245fab4b9c246620b4f1cde9d99d698025c81a3d3fc54bd54e5b0d09
version: 1
status: active
schema_version: '0.1'
---

## 是什么

仓库自带的提交前校验：身份必须是约定的发布账号，禁止入库路径命中即拒绝提交。

## 何时用

克隆仓库后第一次开发前安装；此后每次 `git commit` 自动生效。

## 怎么用

运行 `sh scripts/install-hooks.sh` 把 `.githooks/` 里的钩子装进本地 `.git/hooks/`；或 `git config core.hooksPath .githooks`。

## 边界与陷阱

钩子只在本地生效，绕过（`--no-verify`)是可能的——最终防线仍是评审与 CI；禁止路径清单要与 .gitignore 保持同步。

## 关联

为什么 docs 目录在禁止入库清单里，见「设计文档不随仓库公开」。
