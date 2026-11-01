# -*- coding: utf-8 -*-
"""
金铲铲之战（自走棋）运营策略分析 —— 报告生成。

把 insights.json 与 9 张 SVG 图拼成一份**自包含**的 HTML 数据分析报告。

- 零外部依赖：图表全部内嵌为 <svg>，数据全部写入 HTML，单文件即可离线打开；
- 输出：reports/report_tft_analysis.html
用法：python -m src.build_report
"""
from __future__ import annotations

import html
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIG_DIR = os.path.join(ROOT, "reports", "figures")
DATA_JSON = os.path.join(ROOT, "reports", "data", "insights.json")
OUT = os.path.join(ROOT, "reports", "report_tft_analysis.html")

FIG_ORDER = [
    ("fig_style_placement.svg", "运营流派 × 平均名次", "四种主流运营思路的实战成绩对比：均衡流最稳，存钱流风险最高"),
    ("fig_style_rankmap.svg", "流派 × 名次分布热图", "行内占比一目了然：均衡/速本偏向前四，存钱与赌狗长尾更重"),
    ("fig_interest_rank.svg", "利息效率 → 名次", "每回合平均利息与名次的关系——经济是优化项，不是胜负手"),
    ("fig_gold_curve.svg", "比赛进程：存款曲线", "前 2 / 中 4 / 后 2 名玩家的存款演化：前端滚雪球、后端崩盘"),
    ("fig_comp_curve.svg", "比赛进程：战力曲线", "战力走势前段即分化——决定名次的运营窗口在 8–15 回合"),
    ("fig_level_curve.svg", "比赛进程：人口等级曲线", "人口节奏：强队先升人口，弱队在等级上同样落后"),
    ("fig_streak_rank.svg", "连胜滚雪球", "单局最大连胜越长，平均名次越靠前：连胜是强运营的信号"),
    ("fig_elim_round.svg", "淘汰节奏", "第 8 名平均 20 回合出局，冠军撑到第 34 回合——血量是运营的硬约束"),
    ("fig_corr.svg", "指标相关性热图", "总投入（r=-0.88）与存活回合数（r=-0.93）是名次的最强解释变量"),
]


def fig_svgs() -> dict[str, str]:
    out = {}
    for fname, _, _ in FIG_ORDER:
        p = os.path.join(FIG_DIR, fname)
        with open(p, encoding="utf-8") as f:
            svg = f.read()
        # 去除 <svg> 开标签里的固定宽高，交给 CSS 缩放
        svg = svg.replace("<?xml", "<!-- xml").replace("?>", "-->", 1)
        svg = svg.replace("width=\"", "w=\"", 1).replace("height=\"", "h=\"", 1)
        out[fname] = svg
    return out


def render_style_table(styles: list[dict]) -> str:
    rows = []
    for s in styles:
        rows.append(
            f'<tr><td>{html.escape(s["style"])}</td>'
            f'<td>{s["avg_placement"]:.2f}</td>'
            f'<td>{s["top1"] * 100:.1f}%</td>'
            f'<td>{s["top4"] * 100:.1f}%</td>'
            f'<td>{s["avg_interest"]:.1f}</td>'
            f'<td>{s["avg_level"]:.1f}</td>'
            f'<td>{s["avg_elim"]:.1f}</td></tr>'
        )
    return ("<table><thead><tr><th>运营流派</th><th>平均名次</th>"
            "<th>吃鸡率</th><th>前四率</th><th>平均利息/回合</th>"
            "<th>平均人口</th><th>平均淘汰回合</th></tr></thead>"
            "<tbody>" + "".join(rows) + "</tbody></table>")


def render_corr(corr: dict) -> str:
    """把各指标与名次的相关系数渲染成横向条形。"""
    order = ["elim_round", "spent_total", "final_comp", "skill", "max_streak",
             "final_level", "interest", "income", "gold", "dmg"]
    rows = []
    for k in order:
        r = corr.get(k, {}).get("placement", 0)
        width = max(2, int(abs(r) * 200))
        color = "#2FD8A8" if r < 0 else "#F25757"
        rows.append(
            f'<div class="corr-row"><span class="corr-name">{k}</span>'
            f'<span class="corr-bar"><i style="width:{width}px;background:{color}"></i></span>'
            f'<span class="corr-val">{r:+.2f}</span></div>'
        )
    return "".join(rows)


def build() -> None:
    with open(DATA_JSON, encoding="utf-8") as f:
        ins = json.load(f)

    base = ins["base"]
    svgs = fig_svgs()

    stat_cards = [
        (f"{base['matches']:,}", "对局场次"),
        (f"{base['rows']:,}", "回合记录"),
        (f"{base['players']:,}", "玩家记录"),
        (f"{base['avg_rounds']:.0f}", "平均回合"),
        (f"{base['avg_placement']:.1f}", "平均名次"),
        (f"{base['avg_interest']:.1f}", "平均利息/回合"),
        (f"{base['avg_income']:.1f}", "平均收入/回合"),
        (f"{base['skill_placement_r']:.2f}", "实力-名次相关"),
    ]
    cards = "".join(
        f'<div class="stat"><b>{name}</b><span>{label}</span></div>'
        for name, label in stat_cards
    )

    findings = "".join(f"<li>{html.escape(x)}</li>" for x in ins["findings"])

    sections = []
    for fname, title, desc in FIG_ORDER:
        sections.append(
            f'<section><h3>{html.escape(title)}</h3>'
            f'<p class="fig-desc">{html.escape(desc)}</p>'
            f'<div class="fig">{svgs[fname]}</div></section>'
        )

    streak_chips = "".join(
        f'<span class="chip">{html.escape(a)} → 名次 <b>{p:.1f}</b></span>'
        for a, p in ins["streak_rank"]
    )

    steps = ["对抗模拟", "回合级清洗", "玩家聚合", "流派对比", "进程追踪", "相关性归因"]
    tech = {
        "语言 / 依赖": "Python 3.12 · 仅 NumPy / pandas（零第三方图表库）",
        "数据生成": "金铲铲回合制运营模拟器：收入=基础+利息+连胜/连败；四流派策略引擎；战力-胜负模型",
        "数据处理": "21.6 万条回合明细 → 玩家级聚合（经济 / 人口 / 战力 / 连胜 / 淘汰）",
        "分析维度": "流派画像 / 经济效率 / 前中后程轨迹 / 滚雪球 / 淘汰节奏 / 因子相关性",
        "可视化": "自研 SVG 渲染器（bar / line / multi-line / heatmap），9 张图",
        "可复现性": "固定随机种子（seed=42），一键重跑全流程",
    }
    tech_rows = "".join(
        f'<tr><th>{html.escape(k)}</th><td>{html.escape(v)}</td></tr>'
        for k, v in tech.items()
    )
    steps_html = "".join(f"<span>{html.escape(s)}</span>" for s in steps)

    html_doc = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>金铲铲之战 · 自走棋运营策略分析报告</title>
<style>
:root {{
  --bg:#0e1220; --panel:#1a2138; --panel2:#222b47; --txt:#e8ecf8;
  --muted:#9aa6c8; --blue:#3E6FF2; --green:#2FD8A8; --red:#F25757; --orange:#FF9F1C;
}}
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{ background:var(--bg); color:var(--txt);
  font-family:"Microsoft YaHei","PingFang SC",system-ui,sans-serif; line-height:1.6; }}
.wrap {{ max-width:1080px; margin:0 auto; padding:32px 20px 64px; }}
header {{ text-align:center; padding:40px 0 28px; }}
.badge {{ display:inline-block; background:rgba(255,159,28,.13); color:var(--orange);
  border:1px solid rgba(255,159,28,.4); border-radius:999px; padding:4px 14px;
  font-size:13px; letter-spacing:.5px; }}
h1 {{ font-size:30px; margin:14px 0 6px; }}
.sub {{ color:var(--muted); font-size:15px; }}
.stats {{ display:grid; grid-template-columns:repeat(4,1fr);
  gap:12px; margin:26px 0 8px; }}
.stat {{ background:var(--panel); border:1px solid rgba(255,255,255,.06);
  border-radius:12px; padding:14px 10px; text-align:center; }}
.stat b {{ display:block; font-size:22px; color:#fff; }}
.stat span {{ font-size:12px; color:var(--muted); }}
.steps {{ display:flex; justify-content:center; gap:10px; flex-wrap:wrap; margin:22px 0 8px; }}
.steps span {{ background:var(--panel2); border-radius:999px; padding:6px 16px;
  font-size:13px; color:var(--muted); }}
h2 {{ font-size:22px; margin:40px 0 12px; padding-left:10px; border-left:4px solid var(--orange); }}
section {{ background:var(--panel); border:1px solid rgba(255,255,255,.06);
  border-radius:14px; padding:18px 18px 8px; margin:14px 0; }}
section h3 {{ font-size:17px; margin-bottom:4px; }}
.fig-desc {{ color:var(--muted); font-size:13px; margin-bottom:10px; }}
.fig svg {{ width:100%; height:auto; }}
.findings {{ background:var(--panel); border-radius:14px; padding:20px 24px; }}
.findings li {{ margin:8px 0 8px 4px; }}
table {{ width:100%; border-collapse:collapse; margin-top:6px; }}
th, td {{ padding:8px 10px; text-align:left; border-bottom:1px solid rgba(255,255,255,.07); font-size:14px; }}
th {{ color:var(--muted); font-weight:600; }}
.chip {{ display:inline-flex; align-items:center; gap:8px; background:var(--panel2);
  border-radius:999px; padding:8px 14px; margin:4px 6px 4px 0; font-size:13px; }}
.chip b {{ color:var(--orange); }}
.corr-row {{ display:flex; align-items:center; gap:12px; margin:7px 0; }}
.corr-name {{ width:110px; font-size:13px; color:var(--muted); }}
.corr-bar {{ flex:1; background:rgba(255,255,255,.05); border-radius:6px; height:14px; }}
.corr-bar i {{ display:block; height:14px; border-radius:6px; }}
.corr-val {{ width:52px; text-align:right; font-size:13px; font-variant-numeric:tabular-nums; }}
.tech table th {{ width:150px;}}
.note {{ color:var(--muted); font-size:13px; margin-top:24px; }}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <span class="badge">数据科学 · 游戏数据分析</span>
    <h1>金铲铲之战 · 自走棋运营策略分析报告</h1>
    <p class="sub">800 场对局 · 21.6 万条回合记录 · 6,400 条玩家记录 —— 全流程 Python 数据管线</p>
  </header>

  <div class="stats">{cards}</div>
  <div class="steps">{steps_html}</div>

  <h2>核心发现</h2>
  <div class="findings"><ul>{findings}</ul></div>

  <h2>关键图表</h2>
  {"".join(sections)}

  <h2>运营流派成绩榜</h2>
  <div class="findings">{render_style_table(ins["styles"])}</div>

  <h2>连胜滚雪球：单局最大连胜 → 平均名次</h2>
  <div class="findings">{streak_chips}
    <p style="margin-top:10px" class="fig-desc">连胜 9+ 的玩家平均名次 1.5，1–2 连的玩家平均 6.9 —— 连胜既是实力外溢，也是经济滚雪球的信号。</p>
  </div>

  <h2>与最终名次的相关系数</h2>
  <div class="findings">{render_corr(ins["corr"])}
    <p style="margin-top:10px" class="fig-desc">负相关 = 绿色（名次越低越好，负相关即有利因子）；正相关 = 红色。淘汰回合与总投入是最强解释变量。</p>
  </div>

  <h2>技术栈与方法</h2>
  <div class="findings tech"><table>{tech_rows}</table></div>

  <p class="note">数据说明：本数据集按金铲铲之战公开游戏机制（利息 / 连胜奖励 / 升级费用 / 对战结算）认知模拟生成（seed=42，可复现），用于演示数据分析全流程；结论价值在方法而非数据来源。项目代码见仓库 README。</p>
</div>
</body>
</html>"""

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html_doc)
    print(f"[build_report] 报表已生成 → {OUT}（{len(html_doc):,} 字节，自包含单文件）")


if __name__ == "__main__":
    build()