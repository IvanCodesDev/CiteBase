---
id: card-method-span-provenance
kind: method
name: 论断出处绑定与核验
summary: 论断记录 loc 与 span_sha256；quote 重读源并重算哈希，改动无法静默通过。
aliases:
- span hash
- 出处哈希
- provenance
tags:
- 治理
links:
- predicate: refines
  to: card-concept-card-claim
claims:
- id: c1
  text: 每条论断绑定源位置（loc）与内容哈希（span_sha256），quote 时重读源文本并重算哈希。
  sources:
  - source: src-design-notes
    loc: extracted/text.md#L8-L8
    span_sha256: 45161cbfca6a9c1902988e4b21d74fe978f06a7d5cc2bd6cf663351e81b3f3d0
- id: c2
  text: 无出处论断会被质量闸拒绝。
  sources:
  - source: src-design-notes
    loc: extracted/text.md#L25-L25
    span_sha256: f814bedb062845efbd0ac11b743364f61a70e84f94fb6a5a09d2f2a7a11623b0
version: 1
status: active
schema_version: '0.1'
---

## 是什么

出处是数据而非注释：`loc` 指向源派生物的行区间，`span_sha256` 是该区间文本的 SHA-256。

## 何时用

手写或编译产出论断时必须绑定；`vault quote <card-id>#<claim-id>` 随时可以复核。

## 怎么用

loc 语法为 `<relpath>#L<start>-L<end>`（1-based 闭区间）或整文件路径；哈希是区间行以换行符连接后 UTF-8 字节的 SHA-256。

## 边界与陷阱

源文本任何改动（包括行序调整）都会导致哈希不一致，lint 以 L-PROV-2 报错——这是特性不是误报，说明引用与源已经对不上。

## 关联

双粒度设计的动机见「卡片与论断双粒度」。
