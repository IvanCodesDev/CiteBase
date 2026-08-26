---
id: card-concept-federation-lock
kind: concept
name: 联邦依赖锁定
summary: 跨库依赖由 vault.lock 锁定版本与逐卡哈希；升级是显式变更，上游永不静默传播。
aliases:
- vault.lock
- federation
- 联邦
tags:
- 架构
- 治理
links:
- predicate: related_to
  to: card-decision-git-source-of-truth
claims:
- id: c1
  text: vault 依赖用 vault.lock 锁定（resolved_rev + 逐卡内容哈希），跨库卡片以 <vault-id>::<card-id> 标识。
  sources:
  - source: src-design-notes
    loc: extracted/text.md#L31-L31
    span_sha256: 6ba0b4737b157eb7d68195548992d55d4262da86cb1b2d4e9b8470a1a3b6b3c1
- id: c2
  text: 升级依赖是显式的 lock 文件变更，上游内容永不静默传播。
  sources:
  - source: src-design-notes
    loc: extracted/text.md#L32-L32
    span_sha256: 2d4d9ce2a9467edf0450dd4809e536fd885f5e312058802cff32273514353c57
version: 1
status: active
schema_version: '0.1'
---

## 是什么

一个 vault 可以声明依赖其他 vault；依赖以 lock 文件钉死到具体修订与逐卡哈希，跨库引用带 `::` 前缀显式标识来源库。

## 为什么

知识和代码一样有供应链问题：上游改动必须经过显式的 lock 变更进入下游，diff 里能看到影响面。

## 边界

只支持一层依赖；鉴权全权交给 git 凭据体系，联邦是可选层。

## 关联

「Git 是唯一事实源」解释了为什么 lock 文件是提交物。
