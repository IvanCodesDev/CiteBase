---
id: card-decision-no-llm-kernel
kind: decision
name: 内核不调用 LLM
summary: lint / index / search / eval 全程无 LLM；compiler 是唯一调用点，mcp 只读。
aliases:
- no-LLM kernel
- 无 LLM 内核
tags:
- 架构
links:
- predicate: related_to
  to: card-concept-compile-first
claims:
- id: c1
  text: 内核（lint / index / search / eval）全程不调用 LLM，compiler 是唯一会调用 LLM 的子包。
  sources:
  - source: src-design-notes
    loc: extracted/text.md#L12-L12
    span_sha256: d91423b3c6b652dba90cb769a9d2571f3f82b74eaba45272d8bae30a175a3857
- id: c2
  text: mcp 子包只读，不得 import compiler；治理动词只在 CLI。
  sources:
  - source: src-design-notes
    loc: extracted/text.md#L14-L14
    span_sha256: 5352a1175d994e9986722b78d2c5b5f436dfafdcf22bc73c654874b3c9892cca
- id: c3
  text: 内核零领域词：领域语义只准住在 Pack；垂直需求一律进 Pack / Adapter。
  sources:
  - source: src-design-notes
    loc: extracted/text.md#L15-L15
    span_sha256: 1e7e603770442be8a3ff59f1a79ff287cdacc6690d8edb926cc413a51dfd85c4
version: 1
status: active
schema_version: '0.1'
---

## 背景

「无 LLM 也能跑通」是与 RAG 玩具划清界限的第一卖点；同时测试必须确定性，不能依赖外部模型服务。

## 决策

理解（LLM）只发生在编译期且只住在 compiler 子包；内核动词与读侧协议不依赖任何模型；领域语义全部下放 Pack。

## 理由

结构性保证优于文档约定：包依赖关系让「检索结果可复现、测试可离线」成为编译期事实而不是口头承诺。

## 后果

内核能力上限受限于确定性算法（BM25、别名、链接图），语义检索等增强只能作为外围可选层；换来的是零基础设施依赖与全程可测。

## 关联

编译期与查询期的分工见「编译式知识库」。
