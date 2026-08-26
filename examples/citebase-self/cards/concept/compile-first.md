---
id: card-concept-compile-first
kind: concept
name: 编译式知识库
summary: 把理解前置到编译期，检索复用已蒸馏结论；交付物是 Git 中可治理的长期知识资产。
aliases:
- compile-first
- 编译式
tags:
- 架构
links:
- predicate: related_to
  to: card-concept-card-claim
claims:
- id: c1
  text: Citebase 把理解前置到编译期，源材料先编译成结构化卡片，检索直接复用已蒸馏的结论。
  sources:
  - source: src-design-notes
    loc: extracted/text.md#L5-L5
    span_sha256: 4d25af12d96d77fc04b573161b0095b9f75ea18c5076f9fbf61733bdd69d3ef9
- id: c2
  text: 编译式知识库的交付物是长期维护的知识资产，卡片、论断、出处与审计记录都是 Git 里的文件。
  sources:
  - source: src-design-notes
    loc: extracted/text.md#L6-L6
    span_sha256: c64056470b1c0392b82ba08fa62afd03985d88af8026b1441378870c4a9b01b5
version: 1
status: active
schema_version: '0.1'
---

## 是什么

编译式（compile-first）指理解发生在写入之前：源材料经编译产出结构化卡片，查询时直接复用结论，而不是每次提问都重新解读全量语料。

## 为什么

重复理解的成本随提问次数线性增长；把理解一次性沉淀为可核验的卡片后，检索、引用与治理都工作在蒸馏产物上，成本与质量都可控。

## 边界

写入需要编译与审核，不适合「丢一堆临时文件立刻问答」的场景；适合需要长期复用、可追责的知识。

## 关联

知识单元的具体形态见「卡片与论断双粒度」。
