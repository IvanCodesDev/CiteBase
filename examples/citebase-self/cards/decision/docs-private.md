---
id: card-decision-docs-private
kind: decision
name: 设计文档不随仓库公开
summary: docs/ 被 gitignore 且取消跟踪；公开知识经自举 vault 以卡片形式发布。
aliases:
- docs 私有
- private docs
tags:
- 发布
links:
- predicate: related_to
  to: card-method-commit-hooks
claims:
- id: c1
  text: docs/ 设计文档目录不进入公开仓库：.gitignore 排除并已取消跟踪，公开知识经自举 vault 以卡片形式发布。
  sources:
  - source: src-release-notes
    loc: extracted/text.md#L5-L5
    span_sha256: bb6d2e0c8816a2f19c1fbb585eab130f0302ad04e45b2b8a45161ce16eba57a1
- id: c2
  text: pre-commit 钩子拦截 docs/ 路径进入暂存区。
  sources:
  - source: src-release-notes
    loc: extracted/text.md#L7-L7
    span_sha256: 3575b37e245fab4b9c246620b4f1cde9d99d698025c81a3d3fc54bd54e5b0d09
version: 1
status: active
schema_version: '0.1'
---

## 背景

docs/ 里混有产品策略、竞品分析等内部内容，2026-08-28 公开仓库时决定整目录不入库。

## 决策

docs/ 进 .gitignore 并从索引取消跟踪，pre-commit 钩子兜底拦截；对外可见的工程与设计知识由 examples/citebase-self 自举 vault 承载。

## 理由

按目录整体划界比逐文件甄别可靠；知识以卡片形式公开还顺带成为产品自身的 dogfooding。

## 后果

公开 README 不能再链接 docs/ 内文件；贡献者了解设计要走自举 vault 的检索漏斗。

## 关联

兜底拦截机制见「提交规范钩子」。
