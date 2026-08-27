---
id: card-concept-client-retry-policy
kind: concept
name: 客户端重试策略
summary: 本库策略卡：重试节流直接复用上游 methods-provider 的方法与陷阱知识。
aliases:
- retry policy
- 重试策略
tags:
- 工程实践
links:
- predicate: cites
  to: methods-provider::card-method-backoff-with-jitter
- predicate: related_to
  to: methods-provider::card-pitfall-sync-retry-storm
version: 1
status: active
schema_version: '0.1'
---

## 是什么

本库对客户端重试的约定：统一采用上游方法库的「带抖动的指数退避」，
不在本库复制上游正文——跨库引用保持出处链可验证。

## 何时用

任何调用外部依赖的客户端模块。

## 怎么用

阅读 `methods-provider::card-method-backoff-with-jitter` 并按其参数约定配置；
引用其论断时用 quote 取可核片段。

## 边界与陷阱

上游卡退役或漂移时，`vault deps status` 会给出提示；升级依赖走 PR 评审影响面。

## 关联

上游方法与故障模式见链接。
