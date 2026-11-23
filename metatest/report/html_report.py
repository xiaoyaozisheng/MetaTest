"""HTML 报告：自包含单文件（无外部依赖），含代码上下文与质量/自检章节。"""

from __future__ import annotations

import html
import time
from pathlib import Path

from metatest import __version__
from metatest.models import AnalysisResult, MutantStatus, QualityReport
from metatest.mutators.base import describe_operator

_CSS = """
:root { --bg:#0f1420; --card:#171e2e; --line:#2a3448; --tx:#dbe4f3; --dim:#8b97ad;
  --ok:#3fb96f; --bad:#e0566b; --warn:#d9a13c; --info:#4f9cf9; --mut:#b388ff; }
* { box-sizing:border-box; }
body { margin:0; padding:32px 24px 64px; background:var(--bg); color:var(--tx);
  font:14px/1.55 "Segoe UI", "Microsoft YaHei", system-ui, sans-serif; }
.wrap { max-width:1080px; margin:0 auto; }
h1 { font-size:22px; margin:0 0 4px; }
h2 { font-size:16px; margin:34px 0 12px; border-left:3px solid var(--info); padding-left:10px; }
h3 { font-size:14px; margin:18px 0 8px; color:var(--dim); }
.meta { color:var(--dim); font-size:12.5px; margin-bottom:20px; }
.cards { display:flex; gap:12px; flex-wrap:wrap; margin:18px 0; }
.card { background:var(--card); border:1px solid var(--line); border-radius:10px;
  padding:14px 18px; min-width:110px; }
.card .num { font-size:24px; font-weight:600; }
.card .lbl { color:var(--dim); font-size:12px; margin-top:2px; }
.score-badge { display:inline-flex; align-items:baseline; gap:8px; background:var(--card);
  border:1px solid var(--line); border-radius:12px; padding:12px 20px; }
.score-badge .big { font-size:34px; font-weight:700; }
.score-ok { color:var(--ok); } .score-mid { color:var(--warn); } .score-bad { color:var(--bad); }
table { width:100%; border-collapse:collapse; background:var(--card); border:1px solid var(--line);
  border-radius:10px; overflow:hidden; font-size:13px; }
th, td { padding:7px 10px; text-align:left; border-bottom:1px solid var(--line); vertical-align:top; }
th { color:var(--dim); font-weight:600; background:rgba(255,255,255,.02); font-size:12px; }
tr:last-child td { border-bottom:none; }
.tag { display:inline-block; padding:1px 8px; border-radius:99px; font-size:11.5px; font-weight:600; }
.tag.killed { background:rgba(63,185,111,.15); color:var(--ok); }
.tag.survived { background:rgba(224,86,107,.18); color:var(--bad); }
.tag.timeout { background:rgba(217,161,60,.18); color:var(--warn); }
.tag.equivalent { background:rgba(179,136,255,.16); color:var(--mut); }
.tag.error { background:rgba(224,86,107,.18); color:var(--bad); }
.tag.pass { background:rgba(63,185,111,.15); color:var(--ok); }
.tag.fail { background:rgba(224,86,107,.18); color:var(--bad); }
code, pre { font-family:Consolas, "JetBrains Mono", monospace; font-size:12.5px; }
pre { background:#0c111b; border:1px solid var(--line); border-radius:8px; padding:10px 12px;
  overflow-x:auto; margin:6px 0 0; }
pre .hl { background:rgba(79,156,249,.14); display:inline-block; width:100%; border-radius:3px; }
pre .add { color:var(--bad); }
.delta { color:var(--mut); }
.muted { color:var(--dim); }
.ok-text { color:var(--ok); } .bad-text { color:var(--bad); } .warn-text { color:var(--warn); }
.bar { background:#0c111b; border-radius:99px; height:8px; width:120px; overflow:hidden; display:inline-block; }
.bar i { display:block; height:100%; background:var(--ok); }
ul.suggestions li { margin:6px 0; }
.note { color:var(--dim); font-size:12px; margin-top:6px; }
a { color:var(--info); text-decoration:none; }
"""


def write_html_report(analysis: AnalysisResult, path, quality: QualityReport | None = None,
                      selftest=None, config=None, project_root=None, gate=None) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_render(analysis, quality, selftest, config, project_root, gate), encoding="utf-8")
    return path


def _render(analysis, quality, selftest, config, project_root, gate) -> str:
    e = html.escape
    score = analysis.score_percent()
    score_cls, score_txt = _score_style(score, gate)
    parts = []
    parts.append(f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<title>MetaTest 报告 · {e(analysis.project_name)}</title><style>{_CSS}</style></head>
<body><div class="wrap">
<h1>MetaTest 变异测试报告</h1>
<div class="meta">项目 {e(analysis.project_name)} · 生成于 {e(time.strftime("%Y-%m-%d %H:%M:%S"))} ·
耗时 {analysis.duration_sec:.1f}s · MetaTest v{__version__}</div>""")

    if score is None:
        score_html = '<div class="score-badge"><span class="big muted">N/A</span><span class="muted">无可计分变异体</span></div>'
    else:
        score_html = f'<div class="score-badge"><span class="big {score_cls}">{score:.1f}%</span><span class="{score_txt}">{_gate_text(gate, score)}</span></div>'
    parts.append(score_html)

    baseline = analysis.baseline
    if baseline is not None:
        bcls = "pass" if baseline.is_clean_pass() else "fail"
        parts.append(
            f'<p class="note">基线测试：<span class="tag {bcls}">{e(baseline.outcome.value)}</span> '
            f'tests={baseline.tests} failures={baseline.failures} errors={baseline.errors} '
            f'skipped={baseline.skipped}（{baseline.duration_sec:.1f}s）</p>'
        )
    if analysis.strategy:
        st = analysis.strategy
        chain = " -> ".join(n for n, _d, _s in st.get("chain", []))
        extra = f"（{st.get('rules')} 条规则）" if st.get("strategy") == "rule" else ""
        parts.append(
            f'<p class="note">变异策略: <b>{e(st.get("strategy", ""))}</b> {e(extra)} 选择链 {e(chain)}</p>')
    if analysis.incremental:
        inc = analysis.incremental
        parts.append(
            f'<p class="note">增量模式：来源 {e(str(inc.get("source", "")))} · 改动文件 {len(inc.get("changed_files", []))} 个 · '
            f'相关变异体 {inc.get("kept", 0)}/{inc.get("total", 0)}</p>'
        )

    # 引擎可信度提示（词法级回退的变异需谨慎解读）
    engines = analysis.engine_scores()
    if "fallback" in engines:
        fb = engines["fallback"]
        parts.append(
            f'<p class="note"><span class="tag timeout">词法级回退</span> '
            f"本报告含 {fb['total']} 个由词法级回退引擎生成的变异体"
            f"（得分 {fb['score']:.0%}）——回退模式不经 AST，可信度低于 AST 级变异，"
            f'建议安装 tree-sitter（pip install "metatest[c]"）后重跑。'
            f"分引擎统计见 results.json 的 engine_scores。</p>"
        )

    parts.append('<div class="cards">' + "".join(
        f'<div class="card"><div class="num">{n}</div><div class="lbl">{lbl}</div></div>'
        for lbl, n in [
            ("变异体总数", len(analysis.mutants)),
            ("killed 已杀死", analysis.killed),
            ("survived 漏测", analysis.survived),
            ("timeout 超时", analysis.timeout),
            ("equivalent 等价", analysis.equivalent),
            ("error 错误", analysis.error),
        ]
    ) + "</div>")

    # 每文件得分
    parts.append("<h2>文件得分</h2>")
    fs = analysis.file_scores()
    if fs:
        rows = []
        for path in sorted(fs):
            info = fs[path]
            pct = info["score"] * 100 if info["score"] is not None else None
            bar = _bar(pct)
            rows.append(
                f"<tr><td><code>{e(path)}</code></td><td>{info['killed']}/{info['scored']}</td>"
                f"<td>{_fmt_pct(pct)} {bar}</td></tr>"
            )
        parts.append('<table><tr><th>文件</th><th>killed/计分</th><th>得分</th></tr>' + "".join(rows) + "</table>")
    else:
        parts.append('<p class="muted">无变异体（command 适配器项目或源码为空）。</p>')

    # 漏测变异（重点章节）
    survivors = [m for m in analysis.mutants if m.status == MutantStatus.SURVIVED]
    parts.append(f"<h2>漏测变异（survived）<span class='muted'> · {len(survivors)} 个</span></h2>")
    if survivors:
        parts.append(_mutant_table(survivors, project_root, e))
    else:
        parts.append('<p class="ok-text">没有漏测变异 —— 测试套件杀死了所有可执行变异体。</p>')

    # 超时 / 等价 / 错误
    for status, title in [(MutantStatus.TIMEOUT, "超时变异"), (MutantStatus.EQUIVALENT, "等价变异（不计分）"),
                          (MutantStatus.ERROR, "错误变异（不计分）")]:
        ms = [m for m in analysis.mutants if m.status == status]
        if not ms:
            continue
        parts.append(f"<h2>{title}<span class='muted'> · {len(ms)} 个</span></h2>")
        rows = []
        for m in ms:
            rows.append(
                f"<tr><td><code>{e(m.location)}</code></td><td>{e(m.operator)}</td>"
                f"<td><code>{e(m.change)}</code></td><td class='muted'>{e(m.message[:120])}</td></tr>"
            )
        parts.append('<table><tr><th>位置</th><th>算子</th><th>变异</th><th>说明</th></tr>' + "".join(rows) + "</table>")
        if status == MutantStatus.EQUIVALENT:
            parts.append('<p class="note">等价变异可通过 <code>.metatest/equivalents.yaml</code> 人工标记（见 docs/configuration.md）。</p>')

    if quality is not None:
        parts += _quality_sections(quality, e)
    if selftest:
        parts += _selftest_section(selftest, e)

    parts.append("</div></body></html>")
    return "".join(parts)


def _score_style(score, gate):
    if score is None:
        return "", ""
    threshold = gate.get("threshold") if gate else None
    if threshold is not None and score < threshold:
        return "score-bad", "bad-text"
    if score >= 80:
        return "score-ok", "ok-text"
    if score >= 50:
        return "score-mid", "warn-text"
    return "score-bad", "bad-text"


def _gate_text(gate, score):
    threshold = gate.get("threshold") if gate else None
    if threshold is None:
        return "变异得分"
    passed = score >= threshold
    cls = "ok-text" if passed else "bad-text"
    return f'<span class="{cls}">门禁阈值 {threshold:.0f}% · {"达标" if passed else "未达标"}</span>'


def _fmt_pct(pct):
    if pct is None:
        return '<span class="muted">N/A</span>'
    return f"<b>{pct:.0f}%</b>"


def _bar(pct):
    if pct is None:
        return ""
    width = max(0, min(100, pct))
    color = "#3fb96f" if width >= 80 else ("#d9a13c" if width >= 50 else "#e0566b")
    return f'<span class="bar"><i style="width:{width:.0f}%;background:{color}"></i></span>'


def _mutant_table(mutants, project_root, e) -> str:
    rows = []
    for m in mutants:
        # 代码上下文内部已完成转义，这里不再二次转义
        ctx = _code_context(project_root, m.path, m.lineno)
        detail = f"<pre>{ctx}</pre>" if ctx else ""
        suspect = ' <span class="warn-text">疑似等价</span>' if m.suspect_equivalent else ""
        rows.append(
            f"<tr><td><code>{e(m.location)}</code></td>"
            f"<td><span class='tag survived'>survived</span></td>"
            f"<td>{e(m.operator)}<br><span class='muted'>{e(describe_operator(m.operator))}</span></td>"
            f"<td><code>{e(m.original)}</code> <span class='delta'>→</span> <code class='add'>{e(m.mutated)}</code>"
            f"<br><span class='muted'>{e(m.description)}</span>{suspect}{detail}</td></tr>"
        )
    return '<table><tr><th>位置</th><th>状态</th><th>算子</th><th>变异内容</th></tr>' + "".join(rows) + "</table>"


def _code_context(project_root, rel_path: str, lineno: int, pad: int = 3) -> str:
    """渲染漏测变异的代码上下文（文件被删除/改动时静默降级）。"""
    e = html.escape
    if not project_root:
        return ""
    try:
        lines = (Path(project_root) / rel_path).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    lo = max(0, lineno - 1 - pad)
    hi = min(len(lines), lineno + pad)
    out = []
    for i in range(lo, hi):
        mark = "→ " if i == lineno - 1 else "  "
        text = lines[i]
        if i == lineno - 1:
            out.append(f"{e(mark)}{e(str(i + 1).rjust(4))} │ <span class='hl'>{e(text)}</span>")
        else:
            out.append(f"{e(mark)}{e(str(i + 1).rjust(4))} │ {e(text)}")
    return "\n".join(out)


def _quality_sections(q: QualityReport, e) -> list:
    parts = []
    if q.flaky_tests:
        parts.append(f"<h2>Flaky 测试<span class='muted'> · {len(q.flaky_tests)} 个</span></h2>")
        rows = "".join(
            f"<tr><td><code>{e(f.test_id)}</code></td><td>{f.runs}</td><td>{f.passed}</td><td>{f.failed}</td>"
            f"<td>{f.unstable_rate:.0%}</td><td>{e(getattr(f, 'mode', ''))}</td></tr>"
            for f in q.flaky_tests
        )
        parts.append('<table><tr><th>测试</th><th>运行次数</th><th>通过</th><th>失败</th><th>不稳定率</th><th>隔离分类</th></tr>' + rows + "</table>")
        parts.append('<p class="note">isolated_flaky=单独运行也 flaky；order_dependent=套件内顺序/状态依赖（需隔离复测开启）。</p>')
    if q.weak_assertions:
        parts.append(f"<h2>弱断言测试<span class='muted'> · {len(q.weak_assertions)} 个</span></h2>")
        reason_cn = {"no_assertion": "只执行不断言", "trivial_assert": "断言恒真/自比较",
                     "constant_assert": "断言常量", "test_skipped": "无条件跳过"}
        rows = "".join(
            f"<tr><td><code>{e(w.file)}</code></td><td><code>{e(w.test)}</code></td><td>{w.lineno}</td>"
            f"<td>{e(reason_cn.get(w.reason, w.reason))}</td></tr>"
            for w in q.weak_assertions
        )
        parts.append('<table><tr><th>文件</th><th>测试</th><th>行</th><th>问题</th></tr>' + rows + "</table>")
    if q.duplicate_tests:
        parts.append(f"<h2>重复测试<span class='muted'> · {len(q.duplicate_tests)} 组</span></h2>")
        rows = "".join(
            f"<tr><td><code>{e(a)}::{e(b)}</code></td><td><code>{e(c)}::{e(d)}</code></td></tr>"
            for a, b, c, d in q.duplicate_tests
        )
        parts.append('<table><tr><th>测试 A</th><th>测试 B（实现相同）</th></tr>' + rows + "</table>")
    if q.high_coverage_low_mutation:
        parts.append("<h2>高覆盖率 × 低变异得分</h2>")
        rows = "".join(
            f"<tr><td><code>{e(i['file'])}</code></td><td>{i['coverage']:.0%}</td>"
            f"<td>{i['score']:.0%}</td><td>{i['survived']}</td></tr>"
            for i in q.high_coverage_low_mutation
        )
        parts.append('<table><tr><th>文件</th><th>行覆盖率</th><th>变异得分</th><th>漏测数</th></tr>' + rows + "</table>")
        parts.append('<p class="note">覆盖率只说明代码被执行，变异得分才说明断言强度。</p>')
    if q.axes:
        a = q.axes
        adequacy = f"{a['adequacy']:.0%}" if a.get("adequacy") is not None else "N/A"
        parts.append(
            f"<h2>质量三轴（sixth_sense 式）</h2><table>"
            f"<tr><th>轴</th><th>值</th><th>含义</th></tr>"
            f"<tr><td>adequacy 充分性</td><td><b>{adequacy}</b></td><td>变异得分</td></tr>"
            f"<tr><td>redundancy 冗余</td><td><b>{a.get('redundancy', 0)}</b></td><td>重复测试组数</td></tr>"
            f"<tr><td>maintainability 可维护性</td><td><b>{a.get('maintainability', 0)}</b></td><td>弱断言（test smell）数</td></tr>"
            "</table>"
            + ("".join(f'<p class="note">{e(n)}</p>' for n in a.get("notes", [])))
        )
    if q.suggestions:
        parts.append("<h2>可操作建议</h2><ul class='suggestions'>"
                     + "".join(f"<li>{e(s)}</li>" for s in q.suggestions) + "</ul>")
    return parts


def _selftest_section(selftest, e) -> list:
    parts = ["<h2>元测试自检结果</h2>"]
    rows = []
    for r in selftest:
        cls = "pass" if r["pass"] else ("equivalent" if r.get("skipped") else "fail")
        label = "通过" if r["pass"] else ("跳过" if r.get("skipped") else "失败")
        rows.append(
            f"<tr><td><code>{e(r['case_id'])}</code></td><td>{e(r['kind'])}</td>"
            f"<td><span class='tag {cls}'>{label}</span></td>"
            f"<td class='muted'>{e(r.get('message', ''))[:100]}</td></tr>"
        )
    parts.append('<table><tr><th>用例</th><th>类型</th><th>结果</th><th>说明</th></tr>' + "".join(rows) + "</table>")
    return parts
