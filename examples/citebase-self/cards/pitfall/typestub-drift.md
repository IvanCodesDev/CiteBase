---
id: card-pitfall-typestub-drift
kind: pitfall
name: 第三方类型存根漂移
summary: 依赖新版类型存根增删符号，静态 import 加 ignore 注释的兼容分支在 CI 崩掉。
aliases:
- type stub drift
- unused-ignore
tags:
- 工程实践
links:
- predicate: related_to
  to: card-method-quality-gates-ci
claims:
- id: c1
  text: CI 全新安装拿到 mcp 2.1.1 而本地是 2.0.0：mcp.server.fastmcp 模块存根重新出现但不再暴露 FastMCP 属性。
  sources:
  - source: src-dev-log
    loc: extracted/text.md#L12-L12
    span_sha256: 12145390f6d3110d2705824329f4e2394653eaa42fcf7c116c497adda3954452
- id: c2
  text: "挂在兼容回退 import 上的 type: ignore[import-not-found] 注释随依赖存根形态漂移，反过来变成 unused-ignore 报错。"
  sources:
  - source: src-dev-log
    loc: extracted/text.md#L13-L13
    span_sha256: d05338427c801775abf1d9ed5b9e3b88b93c46dd0e815357736ad51aeb88f32a
- id: c3
  text: 修复方式：主路径静态导入保持类型完整，旧版回退分支改用 importlib 动态导入 + cast，与类型存根彻底解耦。
  sources:
  - source: src-dev-log
    loc: extracted/text.md#L14-L14
    span_sha256: b05c66df71a09a936d7ff87fac82cb24f41e32027874dab300cfb103fda083b6
- id: c4
  text: 本地依赖版本要与 CI 全新安装对齐，否则本地绿、CI 红。
  sources:
  - source: src-dev-log
    loc: extracted/text.md#L15-L15
    span_sha256: c526598109ef0f34af60b4f461c674b8ea2aad9ac3ccebb0ae69a8ec629d39ed
version: 1
status: active
schema_version: '0.1'
---

## 现象

本地 ruff / mypy / pytest 全绿，推送后 CI 双平台在 mypy 一步失败：`unused-ignore` 与 `attr-defined` 同时报在同一行兼容 import 上。

## 根因

兼容旧版 SDK 的静态 import 依赖第三方类型存根的形态；存根随版本增删符号后，原本必要的 `type: ignore[...]` 注释反转为「未使用」，而新缺失的属性又需要新的错误码——ignore 清单随上游漂移，永远追不完。

## 规避

版本兼容分支不要静态 import：主路径正常导入并保持类型完整，回退分支用 `importlib.import_module(...)` + `cast`，与存根形态解耦；本地依赖定期对齐 PyPI 最新版再跑门禁。

## 触发条件

同时满足：strict mypy（含 warn_unused_ignores）、多版本兼容的条件 import、CI 每次全新安装最新依赖。

## 关联

暴露此问题的门禁见「CI 六道质量门」。
