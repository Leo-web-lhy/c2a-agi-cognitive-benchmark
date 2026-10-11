# -*- coding: utf-8 -*-
"""C2a 基准运行器：可解性证书 / 无模型基线 / 生成审计 / 学习增益报告。

指标
- A_k：适应集大小 k 时的逐题正确率（网格精确匹配）
- D_k = A_k - A_0：学习增益（扣除先验技能后的净归纳收益）
- E_k = D_k / k：单位经验的学习效率
- 多次重复运行 -> 均值 / 标准差 / bootstrap 95% CI（信度证据）

必须说明的一件事（否则会把效度证书误读成能力测量）
- solvability_oracle 与任务生成器共用**同一个**有限规则空间，因此它的
  A_k == 1 是恒等式，只证明"任务在本空间内可解、且答案唯一"，
  **不是**被测求解器的能力分数。
- 真正被测的是外部求解器（人类 / 模型）在**不被告知规则空间**时的 A_k 曲线。
- 本地能自证的只有三件：任务良构（唯一可识别）、非归纳基线贴地板（无免费午餐）、
  上限可达（可解性成立）。这三件恰好是效度最容易被跳过、也最该先钉死的部分。

用法
  python benchmark_run.py selftest --episodes 8  --depth 1
  python benchmark_run.py report   --episodes 20 --reps 5 --depth 1
  python benchmark_run.py audit    --n 500     --depth 1
"""
import argparse
import collections
import json
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import benchmark_core as B  # noqa: E402

KS = (0, 1, 2, 4)
BIG = 10 ** 6


def _ham(a, b):
    if len(a) != len(b) or any(len(x) != len(y) for x, y in zip(a, b)):
        return BIG
    return sum(1 for r1, r2 in zip(a, b) for x, y in zip(r1, r2) if x != y)


def reference(ep):
    """可解性证书：在有限规则空间内穷尽搜索与适应集一致的规则，命中即应用。
    它存在只证明任务可解且答案唯一，不代表任何智能水平。"""
    for _, f in B.rule_space(ep["depth"], ep["infer_private"]):
        if all(f(g) == o for g, o in ep["adapt"]):
            return [f(g) for g, _ in ep["query"]]
    return [g for g, _ in ep["query"]]


def b_identity(ep):
    return [g for g, _ in ep["query"]]


def b_uniform_random(ep):
    rng = random.Random(ep["task_id"])
    return [B._sparse_grid(rng, list(range(1, 10))) for _ in ep["query"]]


def b_retrieval_1nn(ep):
    """检索式基线：返回输入最相似的示例之输出，量化"检索而非归纳"的天花板。"""
    if not ep["adapt"]:
        return b_identity(ep)
    return [min(ep["adapt"], key=lambda p: _ham(p[0], g))[1] for g, _ in ep["query"]]


def b_majority_output(ep):
    if not ep["adapt"]:
        return b_identity(ep)
    tally = {}
    for _, o in ep["adapt"]:
        key = json.dumps(o)
        tally[key] = (tally.get(key, (0, o))[0] + 1, o)
    best = max(tally.values(), key=lambda t: t[0])[1]
    return [best for _ in ep["query"]]


PREDICTORS = {
    "solvability_oracle": reference,
    "retrieval_1nn": b_retrieval_1nn,
    "majority_output": b_majority_output,
    "identity": b_identity,
    "uniform_random": b_uniform_random,
}


def evaluate(ks, episodes, depth, reps, infer_private):
    res = collections.defaultdict(list)
    gen_fail = 0
    for k in ks:
        for rep in range(reps):
            for i in range(episodes):
                seed = (k + 1) * 100000 + rep * 1000 + i
                try:
                    ep = B.sample_episode(seed, k=k, depth=depth,
                                          infer_private=infer_private)
                except RuntimeError:
                    gen_fail += 1
                    continue
                for pname, fn in PREDICTORS.items():
                    res[(pname, k)].append(B.score(ep, fn(ep))["acc"])
    return res, gen_fail


def _ci(vals, n_boot=2000, seed=7):
    if len(vals) < 2:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    means = []
    for _ in range(n_boot):
        means.append(statistics.fmean(rng.choices(vals, k=len(vals))))
    means.sort()
    return (means[int(0.025 * n_boot)], means[int(0.975 * n_boot)])


def markdown(res, gen_fail, ks, depth, reps, episodes):
    L = []
    L.append("### 表 1 预测器 x 适应集大小 k（逐题正确率，网格精确匹配）\n")
    L.append("| 预测器 | " + " | ".join("A_%d" % k for k in ks) + " |")
    L.append("| --- | " + " | ".join("---" for _ in ks) + " |")
    for n in PREDICTORS:
        cells = []
        for k in ks:
            v = res.get((n, k)) or []
            cells.append("%.3f" % statistics.fmean(v) if v else "n/a")
        L.append("| %s | %s |" % (n, " | ".join(cells)))
    L.append("")
    L.append("> 读法警告：`solvability_oracle` 与生成器共用同一规则空间，"
             "它的 A_k == 1 是恒等式，仅证明**任务可解且答案唯一**；"
             "它不是被测求解器的能力分数。任何把这一行当作「我们赢了」"
             "来汇报的做法，都是把效度证书冒充成能力测量。")
    L.append("> 其余四行是**非归纳**基线，它们的价值在于**贴地板**："
             "若它们显著高于 0，说明任务能被检索/记忆类策略蒙对，"
             "基准就被污染了。")

    L.append("\n### 表 2 学习增益与效率（$D_k = A_k - A_0$，$E_k = D_k / k$）\n")
    L.append("| 指标 | 值 | 说明 |")
    L.append("| --- | --- | --- |")
    a0 = res.get(("solvability_oracle", 0)) or []
    has0 = bool(a0)
    base = statistics.fmean(a0) if has0 else float("nan")
    if has0:
        L.append("| A_0 | %.3f | 零示例下的先验（k=0 不谈可识别性） |" % base)
    else:
        L.append("| A_0 | n/a | 本次运行未采集 k=0（selftest 已含 k=0，此处应出现数值） |")
    for k in ks:
        if k == 0:
            continue
        v = res.get(("solvability_oracle", k)) or []
        if not v:
            continue
        m = statistics.fmean(v)
        sd = statistics.pstdev(v) if len(v) > 1 else 0.0
        lo, hi = _ci(v)
        L.append("| A_%d | %.3f | n=%d, sd=%.3f, 95%%CI=[%.3f, %.3f] |"
                 % (k, m, len(v), sd, lo, hi))
        if has0:
            L.append("| D_%d | %+.3f | A_%d - A_0 |" % (k, m - base, k))
            L.append("| E_%d | %+.4f | D_%d / %d（单位经验学习效率） |"
                     % (k, (m - base) / k, k, k))
        else:
            L.append("| D_%d | n/a | 缺 A_0，无法扣除先验，故不给增益 |" % k)
            L.append("| E_%d | n/a | 缺 A_0 |" % k)

    L.append("\n### 表 3 运行元数据\n")
    L.append("| 项 | 值 |")
    L.append("| --- | --- |")
    L.append("| depth | %d |" % depth)
    L.append("| 每格 episode 数 | %d |" % episodes)
    L.append("| 重复次数 reps | %d |" % reps)
    L.append("| 生成失败（未能在 60 次内唯一可识别） | %d |" % gen_fail)
    L.append("| 公开规则空间大小 | %d |" % len(B.rule_space(depth, False)))
    L.append("| 评测推断空间大小（含私有置换） | %d |"
             % len(B.rule_space(depth, True)))
    L.append("| 规则空间可枚举性 | 是（有限、可穷尽验证，故唯一可识别性可被证明） |")
    return "\n".join(L)


def audit(n, depth, infer_private, k=1):
    """生成器审计：唯一可识别任务的生成成功率、规则族分布、查询网格尺寸分布。
    这是"基准良构"的直接证据，不依赖任何求解器。"""
    space = B.rule_space(depth, infer_private)
    ok = 0
    fail = 0
    consist_hist = collections.Counter()
    fam = collections.Counter()
    qshape = collections.Counter()
    for s in range(n):
        seed = 900000 + s
        try:
            ep = B.sample_episode(seed, k=k, depth=depth,
                                  infer_private=infer_private)
        except RuntimeError:
            fail += 1
            continue
        ok += 1
        cons = [nm for nm, f in space
                if all(f(g) == o for g, o in ep["adapt"])]
        consist_hist[len(cons)] += 1
        fam[ep["rule"].split("(")[0].split("#")[0].split("|")[0]] += 1
        for g, _ in ep["query"]:
            qshape["%dx%d" % (len(g), len(g[0]))] += 1

    L = []
    L.append("### 生成器审计（n=%d, k=%d, depth=%d, 私有置换=%s）\n"
             % (n, k, depth, infer_private))
    L.append("| 项 | 值 |")
    L.append("| --- | --- |")
    L.append("| 唯一可识别任务生成成功 | %d |" % ok)
    L.append("| 生成失败 | %d |" % fail)
    L.append("| 生成成功率 | %s |"
             % (("%.4f" % (ok / n)) if n else "n/a"))
    L.append("| 适应集一致的规则数（众数） | %s |"
             % (consist_hist.most_common(1)[0][0] if consist_hist else "n/a"))
    L.append("| 适应集一致的规则数（分布） | %s |"
             % ", ".join("%d:%d" % kv for kv in sorted(consist_hist.items())))
    L.append("")
    L.append("**规则族分布（按生成规则的首个算子）**\n")
    L.append("| 算子 | 次数 |")
    L.append("| --- | --- |")
    for name, cnt in fam.most_common():
        L.append("| %s | %d |" % (name, cnt))
    L.append("")
    L.append("**查询网格尺寸分布**（`crop_bbox` 会改变尺寸，因此判定必须做精确网格比较）\n")
    L.append("| 尺寸 | 次数 |")
    L.append("| --- | --- |")
    for sh, cnt in qshape.most_common(12):
        L.append("| %s | %d |" % (sh, cnt))
    L.append("")
    L.append("> 成功率的含义：每一次失败都意味着该种子在 60 次尝试内没找到"
             "「适应集一致即唯一确定」的题。**失败率为 0 才是基准良构的证据**；"
             "若失败率偏高，说明规则空间过于拥挤，题目答案不唯一，评分不可信。")
    return "\n".join(L)


def _emit(text):
    """避免 sys.stdout.reconfigure —— 它在无重定向的 ConPTY 管道上会触发
    Windows 0xC0000005（本机实测），是纯环境级崩溃，与算法无关。"""
    try:
        data = (text + "\n").encode("utf-8", "replace")
        buf = getattr(sys.stdout, "buffer", None)
        if buf is not None:
            buf.write(data)
            buf.flush()
        else:
            sys.stdout.write(text + "\n")
    except Exception:
        pass


HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", nargs="?", default="selftest",
                    choices=["selftest", "report", "audit"])
    ap.add_argument("--episodes", type=int, default=8)
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--depth", type=int, default=1)
    ap.add_argument("--private", action="store_true")
    ap.add_argument("--n", type=int, default=200)
    a = ap.parse_args()

    if a.mode == "audit":
        md = audit(a.n, a.depth, a.private)
        out = os.path.join(HERE, "benchmark_audit.md")
    else:
        ks = KS if a.mode == "report" else (0, 1, 2)
        reps = a.reps if a.mode == "report" else 1
        res, gf = evaluate(ks, a.episodes, a.depth, reps, a.private)
        md = markdown(res, gf, ks, a.depth, reps, a.episodes)
        out = os.path.join(HERE, "benchmark_report.md" if a.mode == "report"
                           else "benchmark_selftest.md")

    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(md + "\n")
    _emit(md)
    _emit("WROTE " + out)


if __name__ == "__main__":
    main()
