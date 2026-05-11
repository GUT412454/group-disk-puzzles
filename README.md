# Group Disk Puzzles / 群转盘拼图

**From group generators to interactive planar disk puzzles.**
**从群的生成元到交互式平面转盘拼图。**

A **SageMath** tool that computes geometric realizations of finite group actions as rotating disk puzzles, with a **Pygame**-based interactive viewer.

本工具用 **SageMath** 计算有限群作用的几何实现（转盘拼图），并提供 **Pygame** 交互式可视化界面。

---

## Overview / 概述

Given a set of permutation generators of a finite group, this project:
给定有限群的置换生成元，本项目：

1. Builds a constraint matrix over a cyclotomic field encoding the geometric constraints / 在分圆域上构建约束矩阵
2. Solves for valid point coordinates on the complex plane / 求解复平面上的有效点坐标
3. Normalizes the configuration via Welzl's minimum enclosing circle / 用 Welzl 算法归一化（最小外接圆在原点、半径1）
4. Exports the result as JSON / 导出为 JSON
5. Loads into an interactive Pygame application where you can play the puzzle / 加载到 Pygame 交互程序中游玩

---

## Project Structure / 项目结构

```
├── sage计算形状_批量输出.py    # SageMath batch computation script
├── sage计算形状.py             # Single-computation variant / 单次计算版
├── 3/                          # Pygame interactive viewer / 交互式查看器
│   ├── main.py                 # Entry point / 入口
│   ├── controllers.py          # Game logic, animation, input / 游戏逻辑、动画、输入
│   ├── models.py               # Data models, solvers / 数据模型、求解器
│   ├── views.py                # Rendering / 渲染
│   └── *.json                  # Pre-computed puzzle configurations / 预生成拼图配置
```

---

## Pre-computed Puzzles / 预生成拼图

| File / 文件 | Group / 群 | Disk Structure / 盘结构 |
|-------------|------------|------------------------|
| `M12_N4_N4.json` | M12 | 2 disks, order 4 each / 2盘，阶数4 |
| `PSp(6,2)_N2_N9.json` | PSp(6,2) | N2 + N9 |
| `PSL(2,13)_N2_N3.json` | PSL(2,13) | N2 + N3 |
| `(S5×S5)_C2_N2_N8.json` | (S5×S5):C2 | N2 + N8 |
| `((C2^4):A5):C2_emb1_N2_N5.json` | ((C2^4):A5):C2 | N2 + N5 (embedding 1) |
| `((C2^4):A5):C2_emb2_N2_N8.json` | ((C2^4):A5):C2 | N2 + N8 (embedding 2) |
| `PGammaL(3,4)_3×N2.json` | PΓL(3,4) | 3 disks, order 2 each / 3盘，阶数2 |
| `S6_15pts_N2_N5.json` | S6 | N2 + N5 |
| `S7_21pts_2×N2_N5.json` | S7 | 2×N2 + N5 |
| `S8_56pts_N2_N7.json` | S8 | N2 + N7 |
| `S9_36pts_2×N2_N7.json` | S9 | 2×N2 + N7 |
| `S9_84pts_2×N2_N7.json` | S9 | 2×N2 + N7 |
| `S11_55pts_2×N2_N5.json` | S11 | 2×N2 + N5 |
| `S12_66pts_N2_N5_N7.json` | S12 | N2 + N5 + N7 |

---

## Known Issue: M24 / 已知问题：M24

The script defines generators for **M24** (`M24_N3_N3` in `EXAMPLES`), but currently fails to produce a valid non-degenerate configuration. The original forum post confirms M24 should work — the cause is likely insufficient random sampling, a missing normalization edge case, or a subtle constraint in the solver. Contributions to fix this are welcome.

脚本中定义了 **M24** 的生成元，但目前无法产生有效的非退化配置。原帖确认 M24 是可解的——原因可能是采样不足、归一化边界情况缺失或求解器中的细微约束问题。欢迎修复。

---

## Usage / 使用方法

### Prerequisites / 依赖

- [SageMath](https://www.sagemath.org/) — for puzzle generation / 用于生成拼图
- Python 3 + [Pygame](https://www.pygame.org/) — for interactive viewer / 用于交互查看器

### Generate Puzzles / 生成拼图

```bash
sage sage计算形状_批量输出.py
```

Computes all examples and saves JSON files to `3/`.
计算所有示例，JSON 文件保存到 `3/` 目录。

### Play Puzzles / 游玩拼图

```bash
cd 3
python main.py
```

### Controls / 操作说明

| Key / 按键 | Action / 功能 |
|------------|---------------|
| Q / S | Leftmost disk (by center x) CCW / CW / 最左盘逆/顺时针 |
| L / P | Rightmost disk CCW / CW / 最右盘逆/顺时针 |
| ← → ↑ ↓ | Queue disk rotations / 加入旋转队列 |
| Space / 空格 | Solve (BFS) / 求解 |
| R | Reset / 重置 |
| M | Scramble / 打乱 |
| 1 | Switch to built-in M12 model / 切换到内置 M12 模型 |
| [ / ] | Cycle models / 循环切换模型 |
| 2-9 | Switch to Sage puzzle models / 切换到 Sage 拼图模型 |

---

## How It Works / 原理

1. **Constraint Matrix / 约束矩阵**: For each generator of order *k*, assign a primitive *k*-th root of unity ζ. For each cycle `(a₀, a₁, ..., a_{ℓ-1})` with center *c*:  
   对阶数为 *k* 的生成元，取本原 *k* 次单位根 ζ。每个循环 `(a₀, a₁, ..., a_{ℓ-1})` 和圆心 *c* 满足：

   `ζ·aᵢ - a_{i+1} + (1-ζ)·c = 0`

2. **Nullspace / 零空间**: Solving the homogeneous linear system over the cyclotomic field gives the solution space / 在分圆域上求解齐次线性方程组得到解空间。

3. **Sampling / 采样**: Random linear combinations are tested for distinct points and non-degeneracy (no fixed point on any disk's circle) / 随机线性组合经过检验：点不重合、无退化（不动点不在任何盘的圆上）。

4. **Normalization / 归一化**: Welzl algorithm computes the minimum enclosing circle, then translate/scale/rotate/reflect to canonical form / Welzl 算法求最小外接圆，然后平移、缩放、旋转、反射到规范形式。

5. **Visualization / 可视化**: Coordinates are converted to pixel space and rendered with Pygame. Each disk's cycles define orbits that rotate together / 坐标转为像素坐标，用 Pygame 渲染。每个盘的循环定义一起旋转的轨道。

---

## Credits / 致谢

Based on [will_57's forum post](https://twistypuzzles.com/forum/viewtopic.php?t=31806) "From groups to circle puzzles" on the Twisty Puzzles Forum.

基于 Twisty Puzzles 论坛上 will_57 的帖子 [From groups to circle puzzles](https://twistypuzzles.com/forum/viewtopic.php?t=31806)。
