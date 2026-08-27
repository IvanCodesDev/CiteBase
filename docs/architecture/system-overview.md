# 系统架构总览

> 状态：设计（未实现）· 基线 2026-08-21 · 设计版本 v0.2
> v0.2 相对 v0.1 内部设计稿的架构级变化：① 三条失效通道统一为**失效信号总线**（§5）；② 编译引入**可复现回放**（详见[编译管线](./compile-pipeline.md)）；③ 为 **Vault 联邦**预留命名空间与解析端口（详见[存储与版本化](./storage-and-versioning.md)）。

## 1. 设计目标（可测量定义）

| 目标 | 可测量定义 | 对应机制 |
|---|---|---|
| 可验证 | 任何论断可回溯到「源 id + 位置 + 片段哈希」，重算哈希一致 | 出处硬闸（L-PROV-*）+ span_sha256 |
| 成本可摊销 | 理解成本只在编译期付一次；检索期无原始语料进上下文 | 编译式架构 + 渐进披露检索 |
| 会进化 | 源漂移 / 时效过期 / 实战反例三类信号都能把过期知识撤出检索 | 失效信号总线 + suspect 生命周期 |
| 会自证 | 「知识库有没有用」输出为可复算指标 | 证据回流 + 贡献度度量 |
| 零重基建 | `git clone` 后不装任何服务即可 lint / search / read | 纯文件事实源 + 进程内索引 |
| 通用内核 | 内核代码与内置 schema 零领域词汇 | Ontology Pack + L-CORE-1 |

## 2. 六层架构

```mermaid
flowchart TB
    subgraph GOV["L5 治理 Govern"]
        G1["出处硬闸"]
        G2["失效信号总线"]
        G3["矛盾台账"]
        G4["评测与命中率回流"]
        G5["注入防御"]
    end

    subgraph CONSUME["L4 消费 Consume"]
        C1["MCP Server（Agent）"]
        C2["Python SDK（进程内）"]
        C3["CLI（人与脚本）"]
        C4["导出器（站点 / JSON 快照）"]
    end

    subgraph RETRIEVE["L3 检索 Retrieve"]
        R1["search / read / follow / quote"]
        R2["漏斗策略 + 时效过滤"]
    end

    subgraph INDEX["L2 索引 Index"]
        I1["目录 · 别名表 · 链接图 · 倒排"]
        I2["IndexBackend 端口（内存 → FTS5 → 向量）"]
    end

    subgraph COMPILE["L1 编译 Compile"]
        P1["extract → propose → merge → interlink → contradict"]
        P2["机器闸 validate + 人工抽查闸 review"]
    end

    subgraph SOURCES["L0 源库 Sources"]
        S1["SourceAdapter：file / dir / git / url / evidence"]
        S2["内容寻址 · 原件不动 · 派生另存"]
    end

    CONSUME --> RETRIEVE --> INDEX
    COMPILE --> SOURCES
    INDEX -.由卡片文件重建.-> COMPILE
    GOV -.约束所有层.- COMPILE
```

**分层铁律**：上层只能通过端口访问下层；任何层可单独替换实现而协议不变（例如 L2 从内存倒排换成 SQLite FTS，L3 的四工具签名与漏斗语义完全不动）。

## 3. 端口清单（六边形架构）

内核（core）定义端口，外围包提供实现，运行时装配：

| 端口 | 方法 | 语义要点 | v0 实现 → 可替换实现 |
|---|---|---|---|
| `SourceAdapter` | `resolve() / revision() / changed_since(rev) / fetch()` | `changed_since` **必须允许返回「无法判断」**——诚实优于假精确 | file / dir → git / url / evidence / 自定义 |
| `Extractor` | `extract(derivable) -> derivatives + confidence` | 抽取器名与版本入源 meta；低置信派生物不得支撑论断 | plain / pypdf → mineru / docling |
| `LlmProvider` | `propose / merge_judge / contradict_judge` | 只有 compiler 会调用；**整个 core 无 LLM 依赖** | OpenAI 兼容 / Anthropic；可离线跳过 |
| `IndexBackend` | `build(cards) / search(q) / check()` | 索引是纯生成物，`check` 校验重建一致性 | 进程内存 → SQLite FTS5 → pgvector 混合 |
| `VaultResolver`（M5 预留） | `resolve(vault_id) -> vault root` | 联邦引用 `vault::card` 的解析点 | 本地目录 → git 依赖缓存 |

## 4. 三条数据流

### 4.1 编译流：源 → 卡片

```mermaid
flowchart LR
    SRC["源（PDF / 仓库 / URL / 证据事件）"] --> EX["extract 派生物 + 置信度"]
    EX --> PR["propose 卡片草案 + claims"]
    PR --> MG["merge 与既有卡对齐"]
    MG --> IL["interlink 受控谓词建链"]
    IL --> CT["contradict 冲突检测"]
    CT --> VA{"validate 机器闸"}
    VA -- 拒绝 --> REJ["结构性拒绝 + 原因"]
    VA -- 通过 --> RV{"review 人工抽查闸"}
    RV -- 通过 --> CARDS["卡片入库 + 索引重建"]
    RV -- 驳回 --> REJ
```

每步产物落盘可追溯；抽样率随源历史通过率自适应（新源 100% 送审，稳定源降到 10%）。细节见[编译管线](./compile-pipeline.md)。

### 4.2 消费流：查询 → 可核引用

```mermaid
sequenceDiagram
    participant A as Agent（MCP 宿主）
    participant M as MCP Server
    participant I as 索引 L2
    participant F as 卡片文件

    A->>M: knowledge_search("GM11", as_of=...)
    M->>I: 漏斗第一跳：别名精确命中
    I-->>M: 命中列表（id + 一行摘要）
    A->>M: knowledge_read(card_id)
    M->>F: 读完整卡片（正文 + claims + 源引）
    A->>M: knowledge_quote(claim_id)
    M-->>A: 论断原文 + 源片段 + 引用元数据（可核）
```

检索永远从精确匹配开始，逐跳降级；无命中返回结构化降级信号，禁止静默回退到模型内化知识。细节见[检索协议](./retrieval-protocol.md)。

### 4.3 回流：执行证据 → 经验知识

```mermaid
flowchart LR
    RUN["Agent 任务运行（任意框架）"] --> EVT["EvidenceEvent 投递（HTTP / JSONL）"]
    EVT --> ESRC["evidence 源（L0，事件即出处）"]
    ESRC --> BC["回流编译器：失败聚类 → 陷阱卡草案"]
    BC --> GATE["同一套机器闸 + 人工闸（回流不豁免治理）"]
    GATE --> PIT["陷阱卡 / 经验卡 + pitfall 链接"]
    PIT --> METRIC["贡献度度量：引用卡的任务成功率对照"]
    METRIC -.持续为负 → 失效信号.-> BUS["失效信号总线"]
```

这是 2026-08 竞距快照中全场唯一的闭环（〔真差异化〕），也是「知识库有没有用」的度量来源。机制见 [ADR-0007](../adr/0007-execution-evidence-backflow.md)。

## 5. 失效信号总线（v0.2 统一抽象）

v0.1 把「源漂移」「时效过期」「实战反例」分散在三处描述；v0.2 把它们统一为**一条总线、一个队列、一个状态机**，治理逻辑从三套变一套〔组合实践 → 架构统一〕：

```mermaid
stateDiagram-v2
    [*] --> active: 编译入库
    active --> suspect: 失效信号（漂移 / 过期 / 反例）
    suspect --> active: 复核通过（verified_against 更新）
    suspect --> superseded: 被新卡取代
    suspect --> retired: 复核否决
    active --> superseded: supersedes 链接
    superseded --> [*]
    retired --> [*]
```

| 信号生产者 | 触发 | 载荷 |
|---|---|---|
| 漂移审计 | `vault drift` 发现源 revision 变更；抽查发现 span 哈希/语义偏差 | 源 id + 受影响卡片/论断 |
| 时效过期 | `valid_until` 到期 | 论断 id |
| 执行反例 | 贡献度持续为负；失败事件直接归因 | 卡 id + 事件源 |

统一消费规则：

1. 信号只把卡置为 `suspect` 并进复核队列，**从不直接删除**；
2. `suspect` 卡默认退出检索（显式参数才可见）——知识库宁可少说话，不说过期话；
3. 每个信号与复核动作都写入 `_audit/`（append-only），可追溯谁在何时因何信号动了哪张卡；
4. 复核是人工动词（CLI），机器只能生产信号，不能自我平反。

## 6. 消费拓扑

```mermaid
flowchart LR
    VAULT[("my-vault<br/>git 仓库")] --> MCP["MCP Server"]
    VAULT --> SDK["Python SDK"]
    VAULT --> CLI["vault CLI"]
    VAULT --> SITE["静态站点"]
    VAULT --> SNAP["JSON 快照"]

    MCP --> CURSOR["Cursor / Claude / 任意 MCP 宿主"]
    SDK --> APP["宿主应用（如 OMM）进程内"]
    SITE --> HUMAN["人类浏览"]
    SNAP --> PRODUCT["产品页面数据源"]
```

四种形态读的是**同一份卡片文件**；导出物带「生成物勿手改」戳。治理动词（compile/drift/audit/resolve）只存在于 CLI——Agent 只读、人治理，权限边界由包依赖关系保证（mcp 包不 import compiler）。

## 7. 层可替换性矩阵

| 层 | v0 实现 | 替换点 | 替换时的不变量 |
|---|---|---|---|
| L0 | file/dir 适配器 | 新增 git/url/自定义适配器 | 四方法签名；revision 可比较 |
| L1 | 单机顺序编译 | 并行 / 远程批处理 | 七步语义与两道闸不变 |
| L2 | 进程内倒排 | SQLite FTS5 / pgvector | `vault index --check` 重建一致 |
| L3 | BM25 + 别名精确 | 加向量第四跳 | 四工具签名与漏斗顺序不变 |
| L4 | CLI + MCP | 新导出器 | 只读、同一事实源 |
| L5 | lint + CI | 组织级审计集成 | 规则清单向后兼容 |

## 8. 当前状态与差距（诚实声明）

- 本仓库当前**只有文档与 schema 草案**，无任何可运行代码；
- 六层架构、端口签名、失效总线均为设计承诺，M0 起按[路线图](../product/roadmap.md)逐里程碑兑现；
- 竞距结论带日期（2026-08），实现启动前需重核竞品进展（见[竞争格局](../product/competitive-landscape.md)）。
