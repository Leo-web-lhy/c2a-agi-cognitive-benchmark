# -*- coding: utf-8 -*-
"""C2a 基准内核：有限规则空间 / 可识别任务生成 / 确定性判定。

构念：面对**未见过的规则空间**时，从少量示例中归纳出可迁移规则的效率
（技能获取效率），而不是既有技能的检索量。

为什么这么设计（效度基础）
- 规则空间有限且可枚举 -> "任务是否唯一可识别"能被**穷尽验证**，不靠估计。
- 任务由种子程序化生成，不发布固定测试集 -> 不存在可被记忆的答案表。
- 判定由生成器自带 oracle 精确比较网格 -> 不依赖脆弱的字符串/正则评分器。

仅依赖标准库。
"""
import hashlib
import random

SIZE = 8
COLORS = tuple(range(10))
BG = 0


# ---------------- 算子 ----------------
def mirror_h(g):
    return [row[::-1] for row in g]


def mirror_v(g):
    return g[::-1]


def rot90(g):
    return [list(c) for c in zip(*g[::-1])]


def transpose(g):
    return [list(r) for r in zip(*g)]


def gravity_down(g):
    h, w = len(g), len(g[0])
    out = [[BG] * w for _ in range(h)]
    for c in range(w):
        vals = [g[r][c] for r in range(h) if g[r][c] != BG]
        for i, v in enumerate(vals):
            out[h - len(vals) + i][c] = v
    return out


def symmetrize_h(g):
    return [[a if a != BG else b for a, b in zip(r, r[::-1])] for r in g]


def outline(g):
    h, w = len(g), len(g[0])
    out = [[BG] * w for _ in range(h)]
    for r in range(h):
        for c in range(w):
            if g[r][c] == BG:
                continue
            edge = (r in (0, h - 1) or c in (0, w - 1)
                    or any(g[r + dr][c + dc] == BG
                           for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1))))
            if edge:
                out[r][c] = g[r][c]
    return out


def crop_bbox(g):
    """裁到非背景包围盒；输出尺寸可变，因此判定必须做精确网格比较。"""
    rows = [r for r in range(len(g)) if any(v != BG for v in g[r])]
    cols = [c for c in range(len(g[0])) if any(g[r][c] != BG for r in range(len(g)))]
    if not rows or not cols:
        return [row[:] for row in g]
    return [[g[r][c] for c in range(cols[0], cols[-1] + 1)]
            for r in range(rows[0], rows[-1] + 1)]


def colorize_bg(g, c):
    return [[c if v == BG else v for v in r] for r in g]


def recolor(g, p):
    return [[p[c] for c in r] for r in g]


NO_PARAM = {
    "mirror_h": mirror_h, "mirror_v": mirror_v, "rot90": rot90, "transpose": transpose,
    "gravity_down": gravity_down, "symmetrize_h": symmetrize_h,
    "outline": outline, "crop_bbox": crop_bbox,
}


def _perms(n, seed):
    rng = random.Random(seed)
    out = []
    while len(out) < n:
        p = list(COLORS)
        rng.shuffle(p)
        if p != list(COLORS) and p not in out:
            out.append(p)
    return out


# 公开置换随样本发布；私有置换只存在于评测用的推断空间中，记忆公开样本无收益。
PUBLIC_PERMS = _perms(20, 20261011)
PRIVATE_PERMS = _perms(20, 777)

_SPACE_CACHE = {}


def rule_space(depth=1, infer_private=False):
    """有限规则列表 [(name, fn)]。infer_private=True 并入私有置换（评测侧）。"""
    key = (depth, infer_private)
    if key in _SPACE_CACHE:
        return _SPACE_CACHE[key]
    ops = [(n, f) for n, f in NO_PARAM.items()]
    ops += [("colorize_bg(%d)" % c, (lambda g, c=c: colorize_bg(g, c)))
            for c in range(1, 10)]
    perms = PUBLIC_PERMS + PRIVATE_PERMS if infer_private else PUBLIC_PERMS
    ops += [("recolor#%d" % i, (lambda g, p=p: recolor(g, p)))
            for i, p in enumerate(perms)]
    if depth == 1:
        space = ops
    else:
        space = []
        for n1, f1 in ops:
            for n2, f2 in ops:
                space.append(("%s|%s" % (n1, n2),
                              (lambda g, f1=f1, f2=f2: f2(f1(g)))))
    _SPACE_CACHE[key] = space
    return space


# ---------------- 任务生成 ----------------
def _sparse_grid(rng, palette):
    """稀疏对象网格：背景 + 2~4 个彩色矩形（ARC 式构图，便于归纳而非记忆）。"""
    g = [[BG] * SIZE for _ in range(SIZE)]
    for i in range(rng.randint(2, 4)):
        h, w = rng.randint(2, 3), rng.randint(2, 3)
        r, c = rng.randint(0, SIZE - h), rng.randint(0, SIZE - w)
        col = palette[i % len(palette)] if palette else 1
        for rr in range(r, r + h):
            for cc in range(c, c + w):
                g[rr][cc] = col
    if all(v == BG for row in g for v in row):
        g[0][0] = palette[0] if palette else 1
    return g


def _pairs(rng, rule, k, n_query):
    """k 个适应对 + n_query 个查询对；适应集的输入合计覆盖 1..9 全部颜色，
    使 recolor 类规则在适应集上可被完整辨识。"""
    palette = list(range(1, 10))
    rng.shuffle(palette)
    out = []
    for i in range(k + n_query):
        if k and i < k:
            seg = palette[(i * 9) // k:((i + 1) * 9) // k] or palette[:1]
            rng.shuffle(seg)
        else:
            seg = palette
        gi = _sparse_grid(rng, seg)
        out.append((gi, rule(gi)))
    return out


def _ep(seed, name, adapt, query, depth, infer_private):
    tid = hashlib.sha256(("%s|%s|%d|%d" % (seed, name, depth,
                                           int(infer_private))).encode()).hexdigest()[:16]
    return {"task_id": tid, "seed": seed, "rule": name, "depth": depth,
            "infer_private": infer_private, "adapt": adapt, "query": query}


def sample_episode(seed, k=3, n_query=4, depth=1, infer_private=False, tries=60):
    """生成**唯一可识别**的任务：适应集一致的规则必须唯一，且它恰好是生成规则。
    k=0 时无法谈可识别性，跳过该检验（用于测量 A_0 先验表现）。"""
    space = rule_space(depth, infer_private)
    rng = random.Random(seed)
    for _ in range(tries):
        name, rule = space[rng.randrange(len(space))]
        pairs = _pairs(rng, rule, k, n_query)
        adapt, query = pairs[:k], pairs[k:]
        if k == 0:
            return _ep(seed, name, adapt, query, depth, infer_private)
        consist = [nm for nm, f in space if all(f(g) == o for g, o in adapt)]
        good = [nm for nm, f in space
                if all(f(g) == o for g, o in adapt)
                and all(f(g) == o for g, o in query)]
        if name in good and len(consist) == len(good):
            return _ep(seed, name, adapt, query, depth, infer_private)
    raise RuntimeError("seed=%s depth=%d 在 %d 次内未生成唯一可识别任务"
                       % (seed, depth, tries))


def score(ep, preds):
    """逐题精确网格匹配 -> 正确率。"""
    hits = [1 if p == o else 0 for p, (_, o) in zip(preds, ep["query"])]
    return {"acc": (sum(hits) / len(hits)) if hits else 0.0,
            "hits": hits, "n": len(hits)}
