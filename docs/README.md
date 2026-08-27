# CardVault 文档总览

> 文档基线 2026-08-21 · 设计版本 v0.2。所有文档遵循同一写作纪律（见下），阅读顺序按角色推荐。

## 阅读路径

| 你是谁 | 推荐顺序 |
|---|---|
| 新读者 | [README](../README.md) → [系统架构总览](./architecture/system-overview.md) → [对象模型](./architecture/object-model.md) |
| 实现者 | [对象模型](./architecture/object-model.md) → [spec/](../spec/README.md) → [编译管线](./architecture/compile-pipeline.md) → [检索协议](./architecture/retrieval-protocol.md) → [质量门](./governance/quality-gates.md) |
| 集成者（接 Agent 系统） | [检索协议](./architecture/retrieval-protocol.md) → [对象模型 §证据事件](./architecture/object-model.md) → [威胁模型](./security/threat-model.md) |
| 评审者 / 决策者 | [竞争格局](./product/competitive-landscape.md) → [路线图](./product/roadmap.md) → [ADR 全集](./adr/) |

## 目录

### architecture/ —— 系统如何构成

- [system-overview.md](./architecture/system-overview.md)：六层架构、端口清单、三条数据流、失效信号总线
- [object-model.md](./architecture/object-model.md)：核心对象、Ontology Pack、时效模型、ID 稳定性
- [compile-pipeline.md](./architecture/compile-pipeline.md)：七步编译循环、增量编译、可复现回放、回流编译器
- [retrieval-protocol.md](./architecture/retrieval-protocol.md)：四工具、漏斗策略、无命中契约、token 经济学
- [storage-and-versioning.md](./architecture/storage-and-versioning.md)：git 原生、PR 即知识变更、Vault 联邦（M5 设计）

### governance/ —— 知识如何保真

- [provenance-and-drift.md](./governance/provenance-and-drift.md)：出处硬闸、漂移审计、矛盾台账、失效信号总线
- [quality-gates.md](./governance/quality-gates.md)：lint 规则清单、评测红线、CI 即治理

### security/ —— 如何不被投毒

- [threat-model.md](./security/threat-model.md)：资产与攻击面、三段注入防御、回流投毒、Pack 供应链

### product/ —— 为什么值得做

- [roadmap.md](./product/roadmap.md)：M0–M5、验收线、发布策略、风险与放弃条件
- [competitive-landscape.md](./product/competitive-landscape.md)：2026-08 竞距快照、对照矩阵、创新点诚实分级

### adr/ —— 关键决策为什么这样定

| ADR | 决策 |
|---|---|
| [0001](./adr/0001-compile-time-understanding.md) | 编译期理解，而非检索时理解 |
| [0002](./adr/0002-dual-granularity-card-claim.md) | 卡片 + 论断双粒度合一 |
| [0003](./adr/0003-git-native-zero-infra.md) | 纯文件 + git 原生，零重基础设施 |
| [0004](./adr/0004-no-auto-entity-graph.md) | 否决自动实体图谱，受控谓词链接代替 |
| [0005](./adr/0005-pluggable-ontology-packs.md) | 本体可插拔，内核零领域词 |
| [0006](./adr/0006-readonly-mcp-cli-governance.md) | Agent 只读 MCP，人类 CLI 治理 |
| [0007](./adr/0007-execution-evidence-backflow.md) | 执行证据回流与知识贡献度度量 |

## 写作纪律（全部文档强制）

1. **诚实分级**：每个设计点标注〔真差异化〕〔组合实践〕〔大路货〕；被否决的方案保留完整论证进 ADR。
2. **状态声明**：文档头部标注它描述的是「设计 / 草案 / 已实现」，绝不把规划写成事实。
3. **可测验收**：任何「做到 X」的承诺必须给出可测量的验收线（数字、命令、红线）。
4. **时间锚点**：竞品与生态论断标注调研日期，过期须重核。
5. **图随文走**：架构图用 Mermaid 内嵌在 Markdown 里，随文本一起 diff 与评审，不用外部画图工具的二进制产物。
