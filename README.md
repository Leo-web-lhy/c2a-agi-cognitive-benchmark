# C2A / C9：衡量 AGI 的认知能力

本目录是 EduSeed 挑战 **C2A / C9** 的工作区。此 README 只记录**已核实的挑战事实**与交付进度，
不作为必交交付物（平台必交清单见下），也不替代 proposal / benchmark 正文。

**公开仓库：** https://github.com/Leo-web-lhy/c2a-agi-cognitive-benchmark

---

## 一、挑战事实（来源：平台 `list-challenges` 本地缓存，核实于 2026-10-11）

| 项 | 值 |
| --- | --- |
| 挑战 ID | `ch-20260717031352-tlg70p` |
| 标题 | C2A / C9：衡量 AGI 的认知能力 |
| 状态 | `published` |
| 截止时间 | 2026-12-31 23:59 |
| 性质 | Elite 20 录取评审的重要组成部分 |

### 评分目标（平台 `objective` 原文）

- 设计指标清晰、基线合理的基准方案
- 论证基准的科学性（信度 / 效度 / 防作弊）
- 产出可执行的竞赛提案文档
- 理解评测设计的常见陷阱

### 必交交付物（平台 `requiredDeliverables` 通配模式）

```
*proposal*    *benchmark*    *AI日志*    *AAR*
```

---

## 二、目录约定

| 路径 | 用途 |
| --- | --- |
| `proposal.md` | 竞赛提案（必交） |
| `benchmark/` | 可执行基准：任务集、评分器、运行说明（必交） |
| `AI日志.md` | 与 AI 的协作记录（必交） |
| `AAR.md` | 复盘（必交） |
| `research/` | 证据底座：文献与来源核验（支撑 proposal，非必交） |
| `pipeline/presubmit.py` | 交付物预检器：`--local` 离线扫描，默认调用平台 `prepare-submission` |

---

## 三、当前状态（截至 2026-10-11）

| 环节 | 状态 | 说明 |
| --- | --- | --- |
| 挑战事实获取 | 完成 | 已取得标题 / 目标 / 必交清单（含截止时间与性质） |
| 正文与 rubric | 阻塞 | `get-challenge` 返回 `LICENSE_CHECK_FAILED`（授权端点不可达）；**未取得即不臆造正文内容** |
| 证据研究 | 未接入 | `research/` 暂无文件；proposal §8 与 AAR 均如实标注外部文献对比证据为「待接入」，未编造引用 |
| 交付物撰写 | 完成 | `proposal.md`、`benchmark/`、`AI日志.md`、`AAR.md` 四类必交全部就位 |
| 本地预检 | 通过 | `pipeline/presubmit.py --local` 命中 4/4，缺失 0 |
| 基准自测 | 通过 | `benchmark_run.py` 的 `selftest` / `report` / `audit` 均退出码 0，stderr 为空 |
| GitHub 发布 | 完成 | https://github.com/Leo-web-lhy/c2a-agi-cognitive-benchmark |
| 平台提交 | 阻塞 | 平台网络层不可达（`LICENSE_CHECK_FAILED`），网络恢复后即可提交 |

### 平台连通性诊断（2026-10-11）

- DNS 正常：`cogseed-open.bonc.com.cn` → `101.36.66.129`
- TCP 连接失败：`https://cogseed-open.bonc.com.cn/edu` 与根路径均返回「无法连接到远程服务器」
- 结论：属**网络层不通**（非鉴权 / 非 DNS 问题），所有依赖平台的读取与写入操作均受阻
- 后台探针持续重试中，日志：`.scratch/net_watch.log`，成功哨兵：`.scratch/net_ok.txt`

---

## 四、待人工介入

1. **授权唤醒研究代理** —— 用于产出 `research/` 证据底座，支撑 proposal 的科学性论证。
2. **恢复平台网络可达性** —— 若能访问 `cogseed-open.bonc.com.cn`（如内网 / VPN / 白名单），
   即可继续「取正文与 rubric → 撰写 → 提交」的链路。

---

> 本文件中的事实均可回溯到平台接口或本地工具输出；未取得的内容一律标注为「未取得 / 阻塞」，不做任何推测性填充。
