# 质量门

> 状态：设计 · 基线 2026-08-21
> 同一套规则同时服务三个执行点：编译期机器闸（validate）、本地 `vault lint`、CI。规则只写一份，防止三处漂移。

## 1. lint 规则清单 v0

| 规则 | 级别 | 内容 |
|---|---|---|
| L-PROV-1 | error | claim 必须有 ≥1 个 sources，且 source id 存在 |
| L-PROV-2 | error | `span_sha256` 与源派生物实际内容一致 |
| L-PROV-3 | error | 卡片不得作为出处（源链必须落 Source） |
| L-PROV-4 | warn | 低置信抽取（<0.6）支撑的论断必须带 `low_confidence` 旗标 |
| L-REF-1 | error | 交付物引用只准来自 `refs/` 已验证条目 |
| L-LINK-1 | error | 链接谓词必须在启用 Pack 的受控表内；双端卡片存在 |
| L-LIFE-1 | error | superseded / retired 卡不得被 active 卡的 claims 引用 |
| L-CORE-1 | error | 内核代码与内置 schema 不得出现任何领域词汇 |
| L-SEC-1 | warn | 源派生物注入扫描命中区段不得被 claim 引用 |
| L-IDX-1 | error | `_index` 重建结果与提交版本一致 |
| L-ID-1 | error | id 格式合法；本地 id 不含保留分隔符 `::`；已退役 id 不得复用 |
| L-SUM-1 | error | 卡片必须有 `summary` 且 ≤80 字（检索 token 契约的落点） |
| L-FED-*（M5 预留） | —— | 联邦引用解析、lock 一致性（设计见[存储与版本化 §5](../architecture/storage-and-versioning.md)） |

级别语义：`error` = 机器闸拒绝写入 / CI 红灯；`warn` = 入库放行但进报告，超阈值升级。

## 2. 评测门

| 门 | 命令 | 红线 | 生效里程碑 |
|---|---|---|---|
| 结构完整 | `vault lint` | 0 error | M0 |
| 索引一致 | `vault index --check` | 重建索引与提交索引逐字节一致 | M0 |
| 检索质量 | `vault eval` | golden set 命中率 ≥ 0.85；首位命中 ≥ 0.6 | M2 |
| 漂移健康 | `vault drift --report` | suspect 卡占比 < 5%，超限 CI 警告 | M2 |
| 忠实度 | `vault eval --faithfulness` | 抽样不忠实率 < 2% | M3 |
| 出处拦截 | 注入 5 个无源论断的对抗样本 | 拦截率 100% | M1 |
| 检索性能 | 10k 卡基准 | search P95 < 200ms | M4 |

## 3. CI 即治理

```yaml
# .github/workflows/vault-ci.yml（用户 vault 侧模板，随 vault init 生成）
name: vault-ci
on: [push, pull_request]
jobs:
  govern:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install cardvault
      - run: vault lint
      - run: vault index --check
      - run: vault eval --smoke
      - run: vault drift --report --warn-threshold 0.05
```

要点：

1. **知识库和代码库享受同一套 CI 纪律**：坏账本红灯，不静默腐烂；
2. 编译产出走 PR，lint 在 PR 上执行——人工抽查闸与机器闸在同一个评审界面汇合；
3. `vault eval --smoke` 用 golden set 子集（<30s），全量评测放 nightly。

## 4. 项目自身的工程质量门（CardVault 仓库侧）

| 门 | 工具 | 红线 |
|---|---|---|
| 类型 | mypy strict | 0 error |
| 风格 | ruff | 0 error |
| 测试 | pytest | **确定性测试不依赖 LLM**：fixtures 断言精确 offset 与哈希；LLM 相关路径用录制回放 |
| 契约 | spec 校验脚本 | 三 schema 自检 + 示例 vault 全部通过 lint |
| 文档 | 诚实分级抽查 | 「规划写成事实」= 评审驳回 |

## 5. Golden Set 约定

```yaml
# evals/golden.yaml（示例）
- q: 小样本时间序列预测用什么方法
  expect: [card-method-gm11]
  expect_rank: 3        # 期望进前 3
- q: GM11
  expect: [card-method-gm11]
  expect_rank: 1        # 别名精确命中必须第一
```

- 每个示例 vault 附带 ≥20 条 golden 样例；
- 未命中样例是缺口清单的一部分，与检索日志回流合并去重。
