# spec/ —— 契约事实源

> 状态：v0.1 草案（M0 冻结前可改；冻结后走版本化演进）· 基线 2026-08-21

三类 JSON Schema 是跨模块、跨语言的契约事实源，**先于代码冻结**：

| Schema | 约束对象 | 消费方 |
|---|---|---|
| [`card.schema.json`](./card.schema.json) | 卡片 YAML frontmatter（含 claims / links / 生命周期） | 编译器 validate、`vault lint`、CI |
| [`evidence-event.schema.json`](./evidence-event.schema.json) | 执行证据事件（回流协议） | evidence 适配器、外部 Agent 系统 |
| [`pack.schema.json`](./pack.schema.json) | Ontology Pack 声明文件 | `vault doctor`、Pack 加载器 |

## 校验模型

- 卡片以 YAML frontmatter 书写，校验时解析为 JSON 后对 `card.schema.json` 验证；
- schema 只管**结构**；跨对象一致性（source id 存在、span 哈希一致、谓词在 Pack 词表内、终态卡不被引用）由 lint 规则承担（L-* 质量门规则，随 `vault lint` 执行）——两层分工：schema 验形，lint 验义；
- `kind` 与 `links[].predicate` 的取值域来自启用的 Pack：schema 层只约束格式，词表校验在 lint 层完成（L-LINK-1）。

## 版本策略

1. 三 schema 独立 semver，与代码版本解耦；`$id` 内嵌版本号（`https://citebase.dev/spec/<name>/v<major.minor>.json`）；
2. **破坏性变更**（删字段、改必填、改语义）必须：主版本 +1、附迁移脚本、`vault doctor` 增加旧版本检测；
3. **兼容变更**（加可选字段、放宽约束）次版本 +1；
4. 卡片 frontmatter 的 `schema_version` 字段缺省等于当前主版本；迁移工具按版本逐级升级；
5. M0 验收要求：三 schema 自检通过 + 示例 vault 全部卡片校验通过。

## 保留字与保留值

| 保留项 | 说明 |
|---|---|
| `kind: contradiction` | 内核内置矛盾卡类，Pack 不得声明同名 kind |
| `::` | 跨库引用分隔符（M5 联邦），本地 id 禁用 |
| `_` 前缀目录 | 生成物 / append-only 台账，不受 schema 约束但受 lint 约束 |
