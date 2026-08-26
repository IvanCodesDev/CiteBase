---
id: card-decision-git-source-of-truth
kind: decision
name: Git 是唯一事实源
summary: cards/ 入版本控制；_index JSON 是可核验提交物，SQLite 只是本地缓存。
aliases:
- source of truth
- 事实源
tags:
- 架构
- 治理
links:
- predicate: related_to
  to: card-method-quality-gates-ci
claims:
- id: c1
  text: cards/ 是事实源并纳入版本控制，_index/ 是可随时重建的构建物，SQLite 仅作本地加速缓存。
  sources:
  - source: src-design-notes
    loc: extracted/text.md#L13-L13
    span_sha256: 390044b7f7d36c0b756535c663452dc01b4de3206fe23921332403d6c5fb84f6
- id: c2
  text: _index JSON 是提交物，一致性由 vault index --check 校验（L-IDX-1）。
  sources:
  - source: src-release-notes
    loc: extracted/text.md#L12-L12
    span_sha256: df2ad630eae6f81eaea7e68225ae5035abebfe8a86f2aca9cd8bfa7a06393c20
version: 1
status: active
schema_version: '0.1'
---

## 背景

知识库产品通常自带数据库与服务端；这与「知识要能进代码评审、能 diff、能回滚」的目标冲突。

## 决策

一个 vault 就是一个 git 目录：卡片、配置、审计记录全部是文件；索引 JSON 随库提交并在 CI 里核验一致性；二进制缓存不入库。

## 理由

Git 免费提供了版本、评审、回滚与权限；索引作为提交物则保证任何检出即刻可检索、可核验，不需要构建服务。

## 后果

写路径必须经过文件与提交（没有在线编辑）；大库的索引 diff 会占仓库体积，是接受的代价。

## 关联

一致性核验所在的质量闸见「CI 六道质量门」。
