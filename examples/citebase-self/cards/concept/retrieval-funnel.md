---
id: card-concept-retrieval-funnel
kind: concept
name: 检索漏斗
summary: search → read → follow → quote 四个只读动作；无命中显式降级，不冒充库内知识。
aliases:
- retrieval funnel
- 检索协议
tags:
- 检索
links:
- predicate: related_to
  to: card-concept-suspect-lifecycle
claims:
- id: c1
  text: 检索拆成四个只读动作：search 返回候选卡摘要，read 读卡片全文，follow 沿受控关系跳邻居，quote 取论断源片段并核验哈希。
  sources:
  - source: src-design-notes
    loc: extracted/text.md#L19-L19
    span_sha256: 4f2901510086497ef59dc9f77d313500e8195c15cc9041773d923e267ee3cb55
- id: c2
  text: 检索默认排除 suspect / superseded / retired 状态的卡片；无命中时返回显式降级信号。
  sources:
  - source: src-design-notes
    loc: extracted/text.md#L20-L20
    span_sha256: 76babd7eceb94a9f9abb54a230858b5a2fe87d9e3175ee2eba68a32434c2921d
version: 1
status: active
schema_version: '0.1'
---

## 是什么

检索不是一次性返回整库，而是四步渐进漏斗：先拿摘要（search），选中后读全文（read），沿受控关系跳读（follow），最后取源片段核验（quote）。

## 为什么

渐进披露控制上下文成本；quote 一步强制核验哈希，让「引用」与「原文」始终可以对质。

## 边界

漏斗只读；治理动词（drift / audit / resolve）不在检索面，只在 CLI。

## 关联

被排除状态的来龙去脉见「失效治理生命周期」。
