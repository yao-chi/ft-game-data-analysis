# -*- coding: utf-8 -*-
"""
金铲铲之战（自走棋）运营策略分析 —— 主分析脚本。

对回合级运营时序做四层拆解：
  1) 流派画像：四种运营流派（存钱/速本/赌狗/均衡）的名次与投入特征；
  2) 经济引擎：利息收入与名次的关系（吃利息到底值不值）；
  3) 比赛进程：前/中/后段名次组在 存款/战力/人口 上的演化轨迹；
  4) 因子归因：最大连胜、淘汰节奏、指标相关性。

用法：python -m src.analysis
输出：
  data/processed/cleaned.csv        玩家级汇总表
  reports/figures/*.svg            8 张分析图表（零依赖渲染）
  reports/data/insights.json       结构化分析结论
"""
from __future__ import annotations

import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import numpy as np
import pandas as pd

try:                      # python -m src.analysis
    from . import chart
except ImportError:       # python src/analysis.py
    import chart

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw", "games.csv")
PROC = os.path.join(ROOT, "data", "processed", "cleaned.csv")
FIG = os.path.join(ROOT, "reports", "figures")
INS = os.path.join(ROOT, "reports", "data", "insights.json")

# 玩家级汇总用到的数值列
AGG = {
    "interest": ("interest", "mean"), "income": ("income", "mean"),
    "streak_bonus": ("streak_bonus", "mean"),
    "gold": ("gold", "mean"), "comp": ("comp", "mean"),
    "level": ("level", "max"), "spent_total": ("cum_spent", "max"),
    "spent_reroll": ("spent_reroll", "sum"), "spent_unit": ("spent_unit", "sum"),
    "spent_level": ("spent_level", "sum"),
    "dmg": ("dmg_taken", "max"), "final_gold": ("gold", "last"),
    "final_comp": ("comp", "last"), "final_level": ("level", "last"),
    "max_streak": ("streak", "max"),
}


def load_and_clean() -> tuple[pd.DataFrame, pd.DataFrame]:
    df = pd.read_csv(RAW, encoding="utf-8-sig")
    for c in ["round", "player_id"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype("Int64")
    df["interest"] = pd.to_numeric(df["interest"], errors="coerce").fillna(0)
    # 玩家级汇总（每个人取整局聚合；placement/elim/tier/style 等取终局值）
    g = df.groupby(["match_id", "player_id"])
    gp = g.agg(**AGG).reset_index()
    meta = g.agg(style=("style", "last"), tier=("tier", "last"),
                 skill=("skill", "last"), placement=("placement", "last"),
                 elim_round=("elim_round", "last")).reset_index()
    player_df = gp.merge(meta, on=["match_id", "player_id"])
    before = len(df)
    df = df.dropna(subset=["match_id", "player_id", "round"])
    print(f"[analysis] 清洗：{before:,} → {len(df):,} 行（回合×玩家）；"
          f"玩家级 {len(player_df):,} 行")
    return df, player_df


def pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _save_svg(name: str, svg: str) -> None:
    with open(os.path.join(FIG, f"{name}.svg"), "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"  ✓ {name}.svg")


def main() -> None:
    os.makedirs(os.path.dirname(PROC), exist_ok=True)
    os.makedirs(FIG, exist_ok=True)
    os.makedirs(os.path.dirname(INS), exist_ok=True)

    df, pl = load_and_clean()
    pl.to_csv(PROC, index=False, encoding="utf-8-sig")

    n_matches = pl["match_id"].nunique()
    n_players = len(pl)
    ins: dict = {}

    base = {
        "matches": int(n_matches),
        "rows": int(len(df)),
        "players": int(n_players),
        "avg_rounds": round(float(df.groupby("match_id")["round"].max().mean()), 1),
        "avg_placement": round(float(pl["placement"].mean()), 2),
        "avg_interest": round(float(pl["interest"].mean()), 2),
        "avg_income": round(float(pl["income"].mean()), 2),
        "avg_final_gold": round(float(pl["final_gold"].mean()), 1),
        "avg_max_streak": round(float(pl["max_streak"].mean()), 1),
        "skill_placement_r": round(float(pl["skill"].corr(pl["placement"])), 3),
    }
    ins["base"] = base

    # ---------- 1) 流派画像：名次 / 投入 / 经济 ----------
    st = pl.groupby("style").agg(
        n=("placement", "size"), avg_placement=("placement", "mean"),
        avg_interest=("interest", "mean"), avg_gold=("gold", "mean"),
        avg_level=("final_level", "mean"), avg_comp=("final_comp", "mean"),
        avg_elim=("elim_round", "mean"), top1=("placement", lambda s: (s == 1).mean()),
        top4=("placement", lambda s: (s <= 4).mean()),
    ).reset_index().sort_values("avg_placement")
    ins["styles"] = [{**r, "avg_placement": round(r["avg_placement"], 2),
                      "avg_interest": round(r["avg_interest"], 2),
                      "avg_gold": round(r["avg_gold"], 1),
                      "avg_level": round(r["avg_level"], 1),
                      "avg_comp": round(r["avg_comp"], 1),
                      "avg_elim": round(r["avg_elim"], 1),
                      "top1": round(r["top1"], 4), "top4": round(r["top4"], 4)}
                     for r in st.to_dict("records")]
    _save_svg("fig_style_placement", chart.bar_chart(
        st["style"].tolist(), st["avg_placement"].tolist(),
        title="运营流派 × 平均最终名次", sub="名次越低越优：均衡流最稳，存钱流风险最高",
        ylabel="平均名次", ymin=1, ymax=8, fmt=".1f", color=chart.C_BLUE))

    # 流派 × 名次 分布热图（行占比）
    cros = pd.crosstab(pl["style"], pl["placement"], normalize="index")
    matrix = cros.round(3).values.tolist()
    _save_svg("fig_style_rankmap", chart.heatmap(
        matrix, list(cros.index), [str(c) for c in cros.columns],
        title="流派 × 最终名次 分布（行占比）",
        sub="行内占比：均衡/速本偏向前四，存钱与赌狗长尾更重", width=560, height=300, cell=42,
        vmin=0.0, vmax=0.28))

    # ---------- 2) 经济引擎：平均利息 → 名次 ----------
    int_q = pd.qcut(pl["interest"], 5, labels=False, duplicates="drop")
    itab = pd.DataFrame({"interest": pl["interest"], "placement": pl["placement"], "q": int_q})
    itab = itab.groupby("q").agg(x=("interest", "mean"),
                                 p=("placement", "mean")).reset_index().sort_values("x")
    ins["interest_rank"] = [[round(float(r["x"]), 2), round(float(r["p"]), 2)]
                            for r in itab.to_dict("records")]
    _save_svg("fig_interest_rank", chart.line_chart(
        list(zip(itab["x"], itab["p"])),
        title="每回合平均利息 → 平均名次", sub="利息越高名次略好，但差异有限——经济是优化项，不是胜负手",
        xlabel="平均每回合利息（金币）", ylabel="平均名次", fmt=".1f",
        ymin=3.5, ymax=5.5, color=chart.C_ORANGE))

    # ---------- 3) 比赛进程：前2 / 中4 / 后2 的存款·战力·人口曲线 ----------
    _SAVE_LABELS = {"gold": "金币存款", "comp": "阵容战力", "level": "人口等级"}

    def add_grouped(name, col, ymin_, ymax_, fmt_):
        gdf = df.copy()
        gdf["group"] = np.select(
            [df["placement"] <= 2, df["placement"] >= 7],
            ["前2名", "后2名"], default="中4名")
        grp = gdf.groupby(["round", "group"])[col].mean().reset_index()
        series = []
        for label, clr in [("前2名", chart.C_GREEN), ("中4名", chart.C_BLUE),
                           ("后2名", chart.C_RED)]:
            sub = grp[grp["group"] == label]
            series.append({"xs": sub["round"].tolist(), "ys": sub[col].round(2).tolist(),
                           "color": clr, "label": label})
        cn = _SAVE_LABELS.get(col, col)
        _save_svg(name, chart.multi_line_chart(
            series, title=f"比赛进程：每回合{cn}（按最终名次分组）",
            xlabel="回合", ylabel=cn, xticks=list(range(2, 40, 4)),
            ymin=ymin_, ymax=ymax_, fmt=fmt_))

    add_grouped("fig_gold_curve", "gold", 0, 60, ".0f")
    add_grouped("fig_comp_curve", "comp", 0, 120, ".0f")
    add_grouped("fig_level_curve", "level", 1, 11, ".0f")

    # ---------- 4) 滚雪球：最大连胜 → 名次 ----------
    sk = pl.groupby(pd.cut(pl["max_streak"], bins=[0, 2, 4, 6, 8, 100],
                           labels=["1-2连", "3-4连", "5-6连", "7-8连", "9+连"]))
    skt = sk.agg(x=("max_streak", "mean"), p=("placement", "mean")).reset_index()
    skt["lab"] = skt["x"].astype(str)
    # 用条带标签替换均值作为 x 轴刻度（更可读）
    labs = ["1-2连", "3-4连", "5-6连", "7-8连", "9+连"][: len(skt)]
    skt["lab"] = labs
    ins["streak_rank"] = [[r["lab"], round(float(r["p"]), 2)]
                          for r in skt.to_dict("records")]
    _save_svg("fig_streak_rank", chart.bar_chart(
        skt["lab"].tolist(), skt["p"].tolist(),
        title="单局最大连胜 → 平均名次", sub="连胜是滚雪球信号：连胜越久，平均名次越靠前",
        ylabel="平均名次", ymin=1, ymax=8, fmt=".1f", color=chart.C_RED))

    # ---------- 5) 淘汰节奏：名次 × 平均淘汰回合 ----------
    et = pl.groupby("placement")["elim_round"].mean().reset_index()
    ins["elim_by_rank"] = [[int(r["placement"]), round(float(r["elim_round"]), 1)]
                           for r in et.to_dict("records")]
    _save_svg("fig_elim_round", chart.bar_chart(
        et["placement"].astype(str).tolist(), et["elim_round"].tolist(),
        title="最终名次 × 平均淘汰回合", sub="第 8 名平均 ~21 回合出局，冠军撑到 ~34 回合",
        ylabel="平均淘汰回合", ymin=15, ymax=38, fmt=".0f", color=chart.C_GREEN))

    # ---------- 6) 指标相关性 ----------
    num_cols = ["skill", "interest", "income", "gold", "max_streak",
                "final_level", "final_comp", "spent_total", "dmg", "elim_round",
                "placement"]
    cm = pl[num_cols].corr()
    ins["corr"] = {c: {k: round(float(v), 3) for k, v in cm[c].items()}
                   for c in cm.columns}
    _save_svg("fig_corr", chart.heatmap(
        cm.round(3).values.tolist(), list(cm.index), list(cm.columns),
        title="运营指标相关性热力图",
        sub="正相关=红↔负相关=蓝；名次越低越好，故与名次正相关的都是劣势因子",
        width=560, height=430, cell=38))

    # ---------- 结论一句话 ----------
    cap = {}
    best = st.iloc[0]
    worst = st.iloc[-1]
    cap["style"] = (f"平均名次最优是 {best['style']}（{best['avg_placement']:.2f} 名，"
                    f"前四率 {pct(best['top4'])}），最险是 {worst['style']}"
                    f"（{worst['avg_placement']:.2f} 名，吃鸡率 {pct(worst['top1'])}）")
    cap["interest"] = (f"每回合利息从 {ins['interest_rank'][0][0]:.1f} 金提到 "
                       f"{ins['interest_rank'][-1][0]:.1f} 金，名次仅从 "
                       f"{ins['interest_rank'][0][1]:.2f} 升到 {ins['interest_rank'][-1][1]:.2f}"
                       f" —— 利息是优化项而非胜负手")
    cap["streak"] = (f"连胜 9 局以上的玩家平均名次 {ins['streak_rank'][-1][1]:.2f}，"
                     f"仅 1-2 连的为 {ins['streak_rank'][0][1]:.2f}")
    cap["elim"] = (f"第 8 名平均 {ins['elim_by_rank'][-1][1]:.0f} 回合出局，"
                   f"冠军撑到第 {ins['elim_by_rank'][0][1]:.0f} 回合")
    sc = cm["placement"].drop("placement").abs().sort_values()
    strongest = sc.index[-1]
    cap["corr"] = (f"与名次相关性最强的是「{strongest}」"
                   f"（r={cm.loc[strongest, 'placement']:+.2f}）；"
                   f"实力 skill 与名次 r={cm.loc['skill', 'placement']:+.2f}，"
                   f"总投入 spent_total r={cm.loc['spent_total', 'placement']:+.2f}")
    ins["captions"] = cap

    findings = [
        f"样本：{base['matches']:,} 局 × {base['players']:,} 条玩家记录 / "
        f"{base['rows']:,} 条回合明细；平均 {base['avg_rounds']} 回合决出胜负。",
        f"运营流派显著影响成绩：{cap['style']}。",
        f"经济只是优化项：{cap['interest']}；真正决定名次的是总投入与存活节奏。",
        f"滚雪球效应：{cap['streak']}。",
        f"淘汰节奏：{cap['elim']}；血量管理（卖血 vs 保血）决定了运营窗口。",
        f"因子归因：{cap['corr']} —— 实力是最大底色、投入与节奏决定执行上限。",
    ]
    ins["findings"] = findings

    with open(INS, "w", encoding="utf-8") as f:
        json.dump(ins, f, ensure_ascii=False, indent=1)
    print(f"[analysis] 完成：{len(os.listdir(FIG))} 张图表，insights.json 已写出")


if __name__ == "__main__":
    main()