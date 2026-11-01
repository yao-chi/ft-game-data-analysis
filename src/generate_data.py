# -*- coding: utf-8 -*-
"""
金铲铲之战（自走棋）对局模拟器 v2 —— 回合级运营时序数据生成。

v2 相对 v1 的修正：
  1) 存款目标驱动支出：每名玩家先攒够流派目标存款（吃利息）再花钱，
     让“存钱吃利息” vs “花钱滚战力”的运营权衡真实成立；
  2) 加快对局节奏：败方掉血随回合加速（约 14-18 回合出现首个出局，
     30+ 回合收尾），接近真实对局节奏；
  3) 连胜/连败皆给奖励（连胜滚雪球、连败补偿），奖励二者取高；
  4) 最终名次在整局结束后回填到该玩家全部回合行，保证明细可直接分析。

玩法模型：
  - 每回合收入 = 基础 5 + 利息(存款每 10 金 +1，封顶 5) + 战绩奖励(0-4)；
  - 流派决定 (目标存款, 升人口/买棋子权重, D牌权重)：存钱流/速本流/赌狗流/均衡流；
  - 战力 = 人口等级基础 + 累计投入质量 + 玩家实力 skill + 噪声；
  - 每回合 4 场 1v1，败方按战力差与回合阶段扣血，归零出局，决出 1-8 名。

用法：python -m src.generate_data
输出：data/raw/games.csv （utf-8-sig）
"""
from __future__ import annotations

import csv
import math
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import numpy as np

SEED = 42
N_MATCHES = 800          # 模拟对局数
N_PER = 8                # 每局人数
MAX_ROUND = 38           # 对局最多回合（极端情况按血量派名次）
BASE_INCOME = 5          # 每回合基础收入
MAX_EARLY = 2            # 前 2 回合野怪阶段：无利息，固定收入 5

TIERS = [(-9.0, "荣耀黄金"), (-1.0, "尊贵铂金"), (-0.5, "璀璨钻石"),
         (0.0, "超凡大师"), (0.6, "傲世宗师"), (1.2, "最强王者")]


def tier_of(s: float) -> str:
    name = TIERS[0][1]
    for th, n in TIERS:
        if s >= th:
            name = n
    return name


# 流派 → (目标存款, 升人口权重, 买棋子权重, D牌权重)
STYLES = {
    "存钱流": (34, 0.30, 0.50, 0.20),
    "速本流": (25, 0.70, 0.15, 0.15),
    "赌狗流": (18, 0.25, 0.25, 0.50),
    "均衡流": (32, 0.40, 0.35, 0.25),
}

# 升到第 n 级（n 从 2 起）累计需花费的金币
LEVEL_COST = [0, 4, 8, 14, 22, 32, 46, 62, 82, 108]  # index i => 升到 level i+2

HEADERS = ["match_id", "round", "player_id", "style", "tier", "skill",
           "gold_before", "income", "interest", "streak_bonus", "gold",
           "spent_level", "spent_reroll", "spent_unit", "cum_spent", "level",
           "comp", "hp", "streak", "alive", "opp_id", "fight_win",
           "dmg_taken", "placement", "elim_round"]

RANK_COL = HEADERS.index("placement")
ELIM_COL = HEADERS.index("elim_round")


def level_of(cum_level_spent: float) -> int:
    lv = 1
    for i, c in enumerate(LEVEL_COST, start=2):
        if cum_level_spent >= c:
            lv = i
        else:
            break
    return min(lv, 10)


def streak_bonus_of(streak: int) -> int:
    if streak < 2:
        return 0
    return min(1 + (streak - 2) // 2, 4)


def interest_of(gold_before: int) -> int:
    return min(max(gold_before, 0) // 10, 5)


def new_player(pid: int, skill: float, style: str) -> dict:
    target, gl, gu, gr = STYLES[style]
    return {
        "player_id": pid, "skill": skill, "style": style,
        "target": float(target), "gl": gl, "gu": gu, "gr": gr,
        "gold": 1, "gold_before": 1, "income": 0, "interest": 0,
        "streak_bonus": 0, "spent_level": 0, "spent_reroll": 0, "spent_unit": 0,
        "cum_lvl": 0.0, "cum_reroll": 0.0, "cum_unit": 0.0, "cum_spent": 0.0,
        "level": 1, "comp": 5.0, "hp": 100.0, "streak": 0, "lose_streak": 0,
        "alive": True, "opp_id": 0, "fight_win": 0, "dmg_taken": 0.0,
        "placement": 0, "elim_round": 0,
    }


def allocate(p: dict, money: float) -> tuple[float, float, float]:
    """把超额金币按流派权重拆成 升人口/买棋子/D牌 三路（D牌 2 金一次取整）。"""
    if money <= 0.05:
        return 0.0, 0.0, 0.0
    gsum = p["gl"] + p["gu"] + p["gr"]
    sr = 2.0 * math.floor(money * p["gr"] / gsum / 2.0)
    rest = money - sr
    if rest < 0.05:
        return 0.0, 0.0, max(0.0, sr - rest)
    su = rest * p["gu"] / (p["gl"] + p["gu"] + 1e-9)
    sl = rest - su
    return max(0.0, sl), max(0.0, sr), max(0.0, su)


def main() -> None:
    rng = np.random.default_rng(SEED)
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(ROOT, "data", "raw", "games.csv")
    os.makedirs(os.path.dirname(out), exist_ok=True)

    rows: list[list] = []
    placement_records: list[tuple[int, int, int]] = []  # (match, player, placement)

    for mid in range(1, N_MATCHES + 1):
        skills = rng.normal(0, 1, N_PER)
        style_names = list(STYLES.keys())
        players = {i: new_player(i + 1, float(skills[i]), str(rng.choice(style_names)))
                   for i in range(N_PER)}
        alive_idx = list(range(N_PER))

        for r in range(1, MAX_ROUND + 1):
            # ---------- 1) 收入 + 投资决策 ----------
            for pid in alive_idx:
                p = players[pid]
                p["gold_before"] = int(p["gold"])
                if r <= MAX_EARLY:
                    inc, interest, sb = 5, 0, 0
                else:
                    interest = interest_of(p["gold_before"])
                    sb = streak_bonus_of(max(p["streak"], p["lose_streak"]))
                    inc = BASE_INCOME + interest + sb
                p["income"], p["interest"], p["streak_bonus"] = inc, interest, sb
                p["gold"] += inc
                # 存款目标驱动：低于目标几乎不花；超额部分按权重投入。
                # 另外每回合至少花 1 金买棋子保底（维持基本战力，防“裸奔”）。
                base_buy = 1.0 if p["gold"] > p["target"] + 2 else 0.0
                spendable = max(0.0, p["gold"] - p["target"] - base_buy)
                if spendable > 0.05:
                    sl, sr, su = allocate(p, spendable)
                    su += base_buy
                else:
                    sl = sr = 0.0
                    su = base_buy if p["gold"] >= base_buy else 0.0
                p["cum_lvl"] += sl
                p["cum_reroll"] += sr
                p["cum_unit"] += su
                p["cum_spent"] += sl + sr + su
                p["gold"] -= sl + sr + su
                p["spent_level"], p["spent_reroll"], p["spent_unit"] = sl, sr, su
                p["level"] = level_of(p["cum_lvl"])
                comp = (4.0 * (p["level"] - 1)
                        + 1.40 * math.sqrt(max(p["cum_unit"], 0) * 2.0 + 1e-6)
                        + 1.15 * math.sqrt(max(p["cum_reroll"], 0) * 1.8 + 1e-6)
                        + 8.0 * p["skill"]
                        + 0.02 * p["cum_spent"]
                        + float(rng.normal(0, 7)))
                p["comp"] = max(0.5, comp)

            # ---------- 2) 对战：存活者随机两两配对 ----------
            order = alive_idx.copy()
            rng.shuffle(order)
            for k in range(len(order) // 2):
                a, b = order[2 * k], order[2 * k + 1]
                pa, pb = players[a], players[b]
                pa["opp_id"], pb["opp_id"] = b + 1, a + 1
                diff = pa["comp"] - pb["comp"]
                p_win_a = 1.0 / (1.0 + math.exp(-diff / 13.0))
                if rng.random() < p_win_a:
                    winner, loser = pa, pb
                else:
                    winner, loser = pb, pa
                winner["fight_win"], loser["fight_win"] = 1, 0
                winner["streak"] += 1
                winner["lose_streak"] = 0
                loser["streak"] = 0
                loser["lose_streak"] += 1
                dmg = (2.0 + r / 4.0
                       + max(0.0, (winner["comp"] - loser["comp"]) / 18.0)
                       + float(rng.uniform(0, 3)))
                loser["hp"] -= dmg
                loser["dmg_taken"] += dmg

            # ---------- 3) 出局判定（名次按出局顺序递减派发） ----------
            dead = [pid for pid in alive_idx if players[pid]["hp"] <= 0]
            rank_next = len(alive_idx)
            for pid in sorted(dead, key=lambda q: players[q]["hp"]):
                p = players[pid]
                p["alive"] = False
                p["elim_round"] = r
                p["placement"] = rank_next
                rank_next -= 1
            alive_idx = [pid for pid in alive_idx if players[pid]["alive"]]

            # ---------- 4) 写本回合（含出局者，保持出局时状态） ----------
            for pid in range(N_PER):
                p = players[pid]
                rows.append([
                    mid, r, p["player_id"], p["style"], tier_of(p["skill"]),
                    round(p["skill"], 4), p["gold_before"], int(p["income"]),
                    int(p["interest"]), int(p["streak_bonus"]), int(p["gold"]),
                    round(p["spent_level"], 1), round(p["spent_reroll"], 1),
                    round(p["spent_unit"], 1), round(p["cum_spent"], 1),
                    p["level"], round(p["comp"], 1), round(p["hp"], 1),
                    p["streak"], 1 if p["alive"] else 0, p["opp_id"],
                    p["fight_win"], round(p["dmg_taken"], 1),
                    p["placement"], p["elim_round"],
                ])

            if len(alive_idx) == 1:
                players[alive_idx[0]]["placement"] = 1
                players[alive_idx[0]]["elim_round"] = r
                alive_idx = []
                break

        # 打满 MAX_ROUND 未出完（极端）：按血量补名次
        if alive_idx:
            rest = sorted(alive_idx, key=lambda q: -players[q]["hp"])
            rank = len(rest)
            for pid in rest:
                players[pid]["placement"] = rank
                players[pid]["elim_round"] = MAX_ROUND
                rank -= 1

        # ---------- 5) 回填最终名次到该玩家的全部回合行 ----------
        finals = {pid: (players[pid]["placement"], players[pid]["elim_round"])
                  for pid in range(N_PER)}
        for row in rows:
            if row[0] == mid:
                row[RANK_COL] = finals[row[2] - 1][0]
                row[ELIM_COL] = finals[row[2] - 1][1]
        for pid in range(N_PER):
            placement_records.append((mid, pid + 1, finals[pid][0]))

    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEADERS)
        w.writerows(rows)

    import collections
    dist = collections.Counter(p for _, _, p in placement_records)
    print(f"[generate_data] v2 {N_MATCHES} 局完成")
    print(f"  总行数（回合×玩家）: {len(rows):,}")
    print(f"  平均回合数/局: {len(rows) / N_MATCHES / N_PER:.1f}")
    print(f"  名次分布: {dict(sorted(dist.items()))}")
    print(f"  输出 → {out}")


if __name__ == "__main__":
    main()