# -*- coding: utf-8 -*-
"""C2a 交付物预检器（离线 + 平台双模式）。

离线模式（--local）：不依赖平台，直接按 requiredDeliverables 通配符扫描工作区，
                       报告命中/缺失，便于在平台不可达时也能自证交付物齐全。
平台模式（默认）：以精确 argv 方式调用 eduseed-student-submit 的 prepare-submission，
                 规避 PowerShell / cmd 吞掉 JSON 内嵌双引号的问题（C1 踩过的坑）。

usage:
  python presubmit.py --local
  python presubmit.py prepare-submission --repo <githubRepoUrl>
"""
import fnmatch
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WORKDIR = os.path.dirname(HERE)  # C2a/

CHALLENGE_ID = "ch-20260717031352-tlg70p"
REQUIRED = "*proposal*,*benchmark*,*AI日志*,*AAR*"
PROJECT_TITLE = "C2A / C9：衡量 AGI 的认知能力"

SKIP_DIRS = {".git", ".scratch", "node_modules", "__pycache__", ".venv"}


def walk_files(root):
    out = []
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            full = os.path.join(base, name)
            out.append((os.path.relpath(full, root).replace("\\", "/"), full))
    return out


def local_mode():
    patterns = [p.strip() for p in REQUIRED.split(",") if p.strip()]
    files = walk_files(WORKDIR)
    lines = ["=== C2a 离线交付物预检 ===", "workdir=%s" % WORKDIR,
             "required=%s" % REQUIRED, "本地文件数=%d" % len(files), ""]
    hit = 0
    for pat in patterns:
        matches = [rel for rel, _ in files if fnmatch.fnmatch(os.path.basename(rel), pat)]
        ok = len(matches) > 0
        hit += 1 if ok else 0
        lines.append("[%s] %-14s -> %s" % ("OK " if ok else "MISS", pat,
                                           ", ".join(matches) if matches else "(无匹配)"))
    lines.append("")
    lines.append("命中 %d/%d，缺失 %d" % (hit, len(patterns), len(patterns) - hit))
    lines.append("")
    lines.append("=== 当前文件树 ===")
    for rel, _ in sorted(files):
        lines.append("  " + rel)
    return "\n".join(lines)


def platform_mode(command, repo_url):
    node = os.environ.get("COGSEED_NODE") or "node"
    pc = os.environ.get("COGSEED_PC_DIR") or ""
    run_skill = os.path.join(pc, "bin", "run-skill.cjs")
    if not os.path.exists(run_skill):
        return "SPAWN_FAILED: run-skill.cjs 不存在 (%s)" % run_skill

    payload = {
        "workdir": WORKDIR,
        "requiredDeliverables": REQUIRED,
        "projectTitle": PROJECT_TITLE,
        "githubRepoUrl": repo_url,
    }
    args = [node, run_skill, "eduseed-student-submit", "runtime", "--", command,
            json.dumps(payload, ensure_ascii=False)]
    lines = ["node=%s" % node, "run_skill=%s" % run_skill,
             "command=%s" % command, "payload=%s" % json.dumps(payload, ensure_ascii=False)]
    try:
        r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                           timeout=240)
        lines.append("exit=%s" % r.returncode)
        lines.append("stdout=%s" % (r.stdout or "").strip())
        if r.stderr:
            lines.append("stderr=%s" % r.stderr.strip())
    except Exception as exc:  # noqa: BLE001
        lines.append("SPAWN_FAILED=%r" % (exc,))
    return "\n".join(lines)


def main():
    argv = sys.argv[1:]
    if argv and argv[0] == "--local":
        text = local_mode()
    else:
        command = argv[0] if argv else "prepare-submission"
        repo = ""
        if "--repo" in argv:
            repo = argv[argv.index("--repo") + 1]
        text = platform_mode(command, repo)
    out_path = os.path.join(HERE, "presubmit.out.txt")
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(text)
    tail = "\nWROTE %s (%d chars)" % (out_path, len(text))
    try:
        # 直接写 UTF-8 字节：避免 Windows ConPTY 下 sys.stdout.reconfigure()
        # 在重定向场景触发 0xC0000005 访问违例（同 benchmark_run.py 的坑）。
        sys.stdout.buffer.write((text + "\n" + tail + "\n").encode("utf-8"))
        sys.stdout.buffer.flush()
    except Exception:  # noqa: BLE001
        sys.stdout.write(text + "\n" + tail + "\n")


if __name__ == "__main__":
    main()
