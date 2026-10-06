#!/usr/bin/env python3
"""拉斯维加斯掷骰（Las Vegas dice game）——终端版。

规则（简化版 Ravensburger 桌游）：
- 6 个赌场（编号 1-6），每局每赌场随机放一笔钱（1万/2万/3万/4万/5万/9万 打乱）
- 每人 8 个骰子。轮到你时掷剩余骰子，选一个点数，把该点数的全部骰子
  放到对应编号的赌场，然后该点数在本轮对你"锁死"（不能再放同点数）
- 没骰子了换下家。所有人放完后每个赌场按骰子数决出名次：
  - 钱从大到小发：独占第一拿最大一笔；平分时若有并列第一，
    并列者先分走顶部奖金（均分，有余数时舍去零头），
    并列者同时失去后续名次资格
  - 经典规则：并列第一者平分奖金后离开，该奖项"消耗"对应名次
- 所有赌场结算后钱多者胜

本项目规则细节：赌场放 N 笔钱（N = 该赌场点数？不——简化为固定 3 笔：
$10k/$20k/$30k 打乱分配），名次 1/2/3 依次拿。并列时：
- 若 k 人并列某名次，他们平分该名次及之后 k-1 个名次的奖金总和（向下取整到千），
  然后跳过这些名次继续。
"""
import argparse
import copy
import random
import sys

CASINOS = 6
DICE = 8
PRIZES = [10, 20, 30]  # 千美元


class IllegalMove(Exception):
    pass


class LasVegas:
    def __init__(self, players=2, seed=None):
        self.rng = random.Random(seed)
        self.players = players
        self.money = [0] * players
        self.prizes = []          # 每个赌场一笔奖金清单
        self.placements = []      # placements[p][c] = p 在赌场 c 的骰子数
        self.locked = []          # locked[p] = 已锁死的点数集合
        self.dice_left = []       # 每人剩余骰子
        self.turn = 0
        self.reset_round()

    def reset_round(self):
        self.prizes = []  # prizes[c] = 该赌场的奖金清单（千美元），已打乱
        for _ in range(CASINOS):
            pool = list(PRIZES)
            self.rng.shuffle(pool)
            self.prizes.append(pool)
        self.placements = [[0] * CASINOS for _ in range(self.players)]
        self.locked = [set() for _ in range(self.players)]
        self.dice_left = [DICE] * self.players
        self.turn = 0

    def roll(self):
        return [self.rng.randint(1, 6) for _ in range(self.dice_left[self.turn])]

    def legal_moves(self, roll):
        counts = {}
        for d in roll:
            counts[d] = counts.get(d, 0) + 1
        return [v for v in counts if v not in self.locked[self.turn]]

    def apply(self, roll, value):
        if value not in self.legal_moves(roll):
            raise IllegalMove(f"非法走法：点数 {value} 不可选（已锁死或不在掷骰中）")
        n = sum(1 for d in roll if d == value)
        p, c = self.turn, value - 1
        self.placements[p][c] += n
        self.locked[p].add(value)
        self.dice_left[p] -= n
        self.turn = (self.turn + 1) % self.players
        return n

    def round_over(self):
        return all(d == 0 for d in self.dice_left)

    def forfeit(self):
        """本轮无可用点数：弃掉剩余骰子，换下家。"""
        self.dice_left[self.turn] = 0
        self.turn = (self.turn + 1) % self.players

    def settle_casino(self, c):
        """结算赌场 c，返回 {player: 奖金}。奖金单位：千美元。"""
        counts = [(self.placements[p][c], p) for p in range(self.players)
                  if self.placements[p][c] > 0]
        counts.sort(reverse=True)
        prizes = sorted(self.prizes[c], reverse=True)
        out = {}
        rank = 0
        i = 0
        while i < len(counts) and rank < len(prizes):
            j = i
            while j < len(counts) and counts[j][0] == counts[i][0]:
                j += 1
            tied = counts[i:j]
            k = len(tied)
            pot = sum(prizes[rank:rank + k])
            share = pot // k
            for _, p in tied:
                out[p] = out.get(p, 0) + share
            rank += k
            i = j
        return out

    def settle_round(self):
        for c in range(CASINOS):
            for p, amt in self.settle_casino(c).items():
                self.money[p] += amt

    # ---------- AI ----------
    def ai_choose(self, roll):
        moves = self.legal_moves(roll)
        p = self.turn
        best, best_key = None, None
        for v in moves:
            c = v - 1
            mine = self.placements[p][c] + sum(1 for d in roll if d == v)
            # 估计：赌场奖金期望 / (领先对手所需)
            opp_best = max([self.placements[q][c] for q in range(self.players) if q != p] + [0])
            lead = mine - opp_best
            prize = sum(self.prizes[c])
            key = (lead, prize, v)
            if best_key is None or key > best_key:
                best_key, best = key, v
        return best


def play_game(players=2, seed=None, verbose=False):
    g = LasVegas(players, seed)
    while not g.round_over():
        roll = g.roll()
        mv = g.ai_choose(roll)
        p = g.turn
        if mv is None:
            g.forfeit()
            if verbose:
                print(f"玩家{p} 掷 {roll} -> 无可用点数，弃掉剩余骰子")
            continue
        n = g.apply(roll, mv)
        if verbose:
            print(f"玩家{p} 掷 {roll} -> 放 {n} 个 {mv} 点到赌场{mv}")
    g.settle_round()
    if verbose:
        for c in range(CASINOS):
            print(f"赌场{c+1}（奖金{sorted(g.prizes[c], reverse=True)}k）:",
                  {f"玩家{p}": v for p, v in g.settle_casino(c).items()})
        print("最终资金：", {f"玩家{p}": f"${g.money[p]}k" for p in range(players)})
    winner = max(range(players), key=lambda p: g.money[p])
    return winner, g.money


def interactive():
    if not sys.stdin.isatty():
        print("交互模式需要终端。请使用 --auto 自动演示。")
        sys.exit(2)
    g = LasVegas(2)
    print("=== 拉斯维加斯掷骰 ===")
    print("你是玩家0，对手是 AI。每轮掷骰后输入要点数（如 4），q 退出。")
    while not g.round_over():
        p = g.turn
        roll = g.roll()
        moves = g.legal_moves(roll)
        if not moves:
            print(f"\n你掷出 {roll}，但所有点数都已锁死，弃掉剩余 {g.dice_left[p]} 个骰子。")
            g.forfeit()
            continue
        if p == 0:
            print(f"\n你的骰子还剩 {g.dice_left[p]}，掷出：{roll}")
            print(f"已锁死点数：{sorted(g.locked[p]) or '无'}")
            while True:
                s = input("放哪个点数？ ").strip()
                if s == "q":
                    return
                try:
                    v = int(s)
                    g.apply(roll, v)
                    print(f"放了 {sum(1 for d in roll if d == v)} 个 {v} 点到赌场{v}")
                    break
                except (ValueError, IllegalMove) as e:
                    print("不行：", e)
        else:
            mv = g.ai_choose(roll)
            g.apply(roll, mv)
            print(f"AI 掷 {roll}，放 {mv} 点")
    g.settle_round()
    print(f"\n最终资金：你 ${g.money[0]}k，AI ${g.money[1]}k")
    print("你赢了！" if g.money[0] > g.money[1] else ("平局！" if g.money[0] == g.money[1] else "AI 赢了。"))


def main():
    ap = argparse.ArgumentParser(description="拉斯维加斯掷骰")
    ap.add_argument("--auto", action="store_true", help="AI 自动对局演示")
    ap.add_argument("--games", type=int, default=10, help="自动对局数")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--players", type=int, default=2)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    if args.auto:
        wins = [0] * args.players
        for i in range(args.games):
            w, money = play_game(args.players, args.seed + i, args.verbose and i == 0)
            wins[w] += 1
            if not args.verbose:
                print(f"第{i+1}/{args.games}局：玩家{w}胜（资金{money}）")
        print(f"\n总计：{args.games} 局，" + "、".join(f"玩家{p}胜{wins[p]}" for p in range(args.players)))
    else:
        interactive()


if __name__ == "__main__":
    main()
