# -*- coding: utf-8 -*-
"""
从置换生成元构造非退化的平面圆盘拼图
带归一化：最小外接圆中心在原点、半径1，重心在正实轴，第一个非轴点在上半平面
最小外接圆采用 Welzl 算法
"""

from sage.all import *
import random
import math

# ------------------- 辅助函数 -------------------
def check_equal_cycles(perm):
    """
    检查置换 perm 是否满足：所有非平凡循环（长度 > 1）长度相等。
    恒等置换（无非平凡循环）视为合法。
    """
    cycles = perm.cycle_tuples()
    nontrivial_lengths = [len(c) for c in cycles if len(c) > 1]
    if not nontrivial_lengths:
        return True
    return all(l == nontrivial_lengths[0] for l in nontrivial_lengths)

def preprocess(generators):
    """
    预处理生成元列表，提取点集、循环结构和圆心变量。
    返回：(points, gens_info)
    """
    all_points = set()
    for g in generators:
        for cyc in g.cycle_tuples():
            all_points.update(cyc)
    points = sorted(all_points)

    gens_info = []
    for idx, g in enumerate(generators):
        if not check_equal_cycles(g):
            raise ValueError(f"生成元 {g} 的循环长度不一致，无法构造圆盘拼图")
        cycles = g.cycle_tuples()
        nontrivial_cycles = [c for c in cycles if len(c) > 1]
        if nontrivial_cycles:
            order = len(nontrivial_cycles[0])
        else:
            order = 1
        gens_info.append({
            'perm': g,
            'order': order,
            'cycles': cycles,
            'center_var': f'c{idx}'
        })
    return points, gens_info

def build_constraint_matrix(points, gens_info):
    """
    构建齐次线性方程组的系数矩阵。
    返回：矩阵 M（在分圆域上），变量名列表 var_names
    """
    nontrivial = [info for info in gens_info if info['order'] > 1]
    if not nontrivial:
        raise ValueError("至少需要一个非平凡生成元")

    orders = [info['order'] for info in nontrivial]
    N = lcm(orders)
    K = CyclotomicField(N)
    zeta = K.gen()

    zeta_by_order = {o: zeta ** (N // o) for o in orders}

    n_points = len(points)
    n_gens = len(gens_info)
    var_names = [f'a{p}' for p in points] + [info['center_var'] for info in gens_info]

    point_to_idx = {p: i for i, p in enumerate(points)}
    center_to_idx = {info['center_var']: n_points + j for j, info in enumerate(gens_info)}

    equations = []
    for info in nontrivial:
        order = info['order']
        zeta_o = zeta_by_order[order]
        one_minus_zeta = 1 - zeta_o
        c_idx = center_to_idx[info['center_var']]
        for cyc in info['cycles']:
            if len(cyc) <= 1:
                continue
            L = len(cyc)
            for k in range(L):
                i = point_to_idx[cyc[k]]
                j = point_to_idx[cyc[(k+1) % L]]
                coeffs = [0] * (n_points + n_gens)
                coeffs[i] = zeta_o
                coeffs[j] = -1
                coeffs[c_idx] = one_minus_zeta
                equations.append(coeffs)

    M = matrix(K, equations)
    return M, var_names

def solve_nullspace(M, name="", points=None):
    if M is None:
        return []
    ker = M.right_kernel()
    basis = ker.basis()
    print(f"[{name}] 零空间维数 = {len(basis)}")
    if basis:
        for i, v in enumerate(basis):
            vec_list = list(v)
            n_pts = (len(vec_list) - 2)  # 减去2个圆心
            g0 = CC(vec_list[n_pts]) if n_pts < len(vec_list) else None
            g1 = CC(vec_list[n_pts+1]) if n_pts+1 < len(vec_list) else None
            print(f"  基向量 {i}: 前3个点 = {[CC(vec_list[j]) for j in range(min(3, n_pts))]}, "
                  f"圆心1={g0}, 圆心2={g1}")
            if points and "M24" in name:
                for target in [2, 5, 13]:
                    if target in points:
                        idx = points.index(target)
                        print(f"    点{target}={CC(vec_list[idx])}")
    return basis

def sample_and_check(basis, points, gens_info, trials=100, epsilon=1e-8, name=""):
    if not basis:
        return None
    d = len(basis)
    basis_vecs = [list(v) for v in basis]
    n_points = len(points)
    n_gens = len(gens_info)

    n_pass_unique = 0
    n_pass_degen = 0

    for _ in range(trials):
        coeffs = [randint(-5, 5) for _ in range(d)]
        sol = [0] * len(basis_vecs[0])
        for c, vec in zip(coeffs, basis_vecs):
            for i, val in enumerate(vec):
                sol[i] += c * val

        point_vals = sol[:n_points]
        center_vals = sol[n_points:]

        # 检查点两两不同
        unique = True
        for i in range(n_points):
            for j in range(i+1, n_points):
                if point_vals[i] == point_vals[j]:
                    unique = False
                    break
            if not unique:
                break
        if not unique:
            if name and "M24" in name:
                print(f"  [DEBUG] 点重合: 系数={coeffs}")
            continue
        n_pass_unique += 1

        # 计算每个非平凡生成元的半径列表
        radii_lists = [[] for _ in range(n_gens)]
        for idx, info in enumerate(gens_info):
            if info['order'] == 1:
                continue
            center_c = ComplexField(100)(center_vals[idx])
            for cyc in info['cycles']:
                if len(cyc) <= 1:
                    continue
                p0 = cyc[0]
                p0_idx = points.index(p0)
                p_c = ComplexField(100)(point_vals[p0_idx])
                r = abs(p_c - center_c)
                radii_lists[idx].append(r)
        if name and "M24" in name:
            for idx in range(n_gens):
                if radii_lists[idx]:
                    print(f"  [DEBUG] 生成元{idx} 各cycle半径={[r.n(digits=5) for r in radii_lists[idx]]}")
            # 验证代数关系: v = g1-g0, u = 2-g1, 检查 |u+v| == |ζ²u+v|
            if len(center_vals) >= 2:
                c0 = ComplexField(100)(center_vals[0])
                c1 = ComplexField(100)(center_vals[1])
                p2_idx = points.index(2)
                p2 = ComplexField(100)(point_vals[p2_idx])
                u = p2 - c1
                v = c1 - c0
                z = ComplexField(100)(-0.5, 0.8660254037844386)  # ζ = e^(2πi/3)
                z2 = z ** 2
                lhs = abs(u + v)
                rhs = abs(z2 * u + v)
                diff_sq = (u+v)*(u+v).conjugate() - (z2*u+v)*(z2*u+v).conjugate()
                print(f"  [DEBUG] u=2-g1={u.n(digits=5)}, v=g1-g0={v.n(digits=5)}")
                print(f"  [DEBUG] |u+v|={lhs.n(digits=6)}, |ζ²u+v|={rhs.n(digits=6)}, diff_sq={diff_sq.n(digits=6)}")

        # 检查不被移动的点是否落在任何半径的圆上
        degenerate = False
        degenerate_info = ""
        for idx, info in enumerate(gens_info):
            if info['order'] == 1:
                continue
            moved_points = set()
            for cyc in info['cycles']:
                if len(cyc) > 1:
                    moved_points.update(cyc)
            center_c = ComplexField(100)(center_vals[idx])
            for p in points:
                if p not in moved_points:
                    p_idx = points.index(p)
                    p_c = ComplexField(100)(point_vals[p_idx])
                    dist = abs(p_c - center_c)
                    for ri, r in enumerate(radii_lists[idx]):
                        if abs(dist - r) < epsilon:
                            degenerate = True
                            degenerate_info = f"生成元{idx}的不动点{p}落在圆{ri}上, dist={dist.n(digits=5)}, r={r.n(digits=5)}"
                            break
                    if degenerate:
                        break
            if degenerate:
                break
        if degenerate:
            if name and "M24" in name:
                print(f"  [DEBUG] 退化: {degenerate_info}, 系数={coeffs}")
            continue
        n_pass_degen += 1

        # 通过检验
        coords = {p: ComplexField(100)(point_vals[i]) for i, p in enumerate(points)}
        circles = {idx: (ComplexField(100)(center_vals[idx]), radii_lists[idx])
                   for idx, info in enumerate(gens_info) if info['order'] > 1}
        return coords, circles

    print(f"[{name}] 采样统计: 共{trials}次, 通过唯一性检查={n_pass_unique}, 通过非退化检查={n_pass_degen}")
    return None

# ------------------- Welzl 最小外接圆算法 -------------------
def circle_from_points(points):
    """
    根据 0、1、2 或 3 个点构造最小外接圆。
    返回 (圆心, 半径) 的复数表示。
    """
    n = len(points)
    if n == 0:
        return CC(0), 0.0
    if n == 1:
        return points[0], 0.0
    if n == 2:
        a, b = points[0], points[1]
        c = (a + b) / 2
        r = abs(a - c)
        return c, r
    if n == 3:
        a, b, c = points[0], points[1], points[2]
        # 计算边长平方
        d_ab_sq = abs(a - b)**2
        d_bc_sq = abs(b - c)**2
        d_ca_sq = abs(c - a)**2
        eps = 1e-12
        # 检查是否钝角（最长边的平方大于另两边平方和）
        if d_ab_sq > d_bc_sq + d_ca_sq + eps:
            # 最长边是 AB，以 AB 为直径
            return circle_from_points([a, b])
        elif d_bc_sq > d_ab_sq + d_ca_sq + eps:
            return circle_from_points([b, c])
        elif d_ca_sq > d_ab_sq + d_bc_sq + eps:
            return circle_from_points([c, a])
        else:
            # 锐角或直角三角形，求外接圆
            x1, y1 = a.real(), a.imag()
            x2, y2 = b.real(), b.imag()
            x3, y3 = c.real(), c.imag()
            D = 2 * (x1*(y2 - y3) + x2*(y3 - y1) + x3*(y1 - y2))
            if abs(D) < eps:
                # 三点共线，退化为最长边为直径
                max_d = max(d_ab_sq, d_bc_sq, d_ca_sq)
                if abs(d_ab_sq - max_d) < eps:
                    return circle_from_points([a, b])
                elif abs(d_bc_sq - max_d) < eps:
                    return circle_from_points([b, c])
                else:
                    return circle_from_points([c, a])
            Ux = ((x1*x1 + y1*y1)*(y2 - y3) + (x2*x2 + y2*y2)*(y3 - y1) + (x3*x3 + y3*y3)*(y1 - y2)) / D
            Uy = ((x1*x1 + y1*y1)*(x3 - x2) + (x2*x2 + y2*y2)*(x1 - x3) + (x3*x3 + y3*y3)*(x2 - x1)) / D
            center = CC(Ux, Uy)
            r = abs(center - a)
            return center, r
    # 超过3个点不应调用此函数
    raise ValueError("circle_from_points 仅支持最多3个点")

def point_in_circle(p, center, r_sq, eps=1e-12):
    """检查点 p 是否在以 center 为圆心、半径为 sqrt(r_sq) 的圆内（包括边界）"""
    return (p.real() - center.real())**2 + (p.imag() - center.imag())**2 <= r_sq + eps

def welzl(points, shuffle=True):
    """
    Welzl 算法求最小外接圆。
    points : 复数列表
    shuffle : 是否随机打乱输入（保证期望线性时间）
    返回 (圆心, 半径)
    """
    if not points:
        return CC(0), 0.0
    pts = list(points)
    if shuffle:
        random.shuffle(pts)

    def welzl_rec(P, R):
        # P: 剩余点集
        # R: 边界点集 (最多3个)
        if not P or len(R) == 3:
            center, r = circle_from_points(R)
            return center, r

        # 随机选一点 p
        idx = random.randint(0, len(P)-1)
        p = P[idx]
        P_rest = P[:idx] + P[idx+1:]

        # 递归求解不含 p 的圆
        center, r = welzl_rec(P_rest, R)
        r_sq = r * r
        if point_in_circle(p, center, r_sq):
            return center, r
        else:
            # 将 p 加入边界集，重新递归
            new_R = R + [p]
            return welzl_rec(P_rest, new_R)

    center, r = welzl_rec(pts, [])
    return center, r

# ------------------- 归一化函数 -------------------
def normalize_coords(coords, circles):
    """
    对点坐标和圆进行归一化：
        - 最小外接圆圆心在原点，半径为1
        - 重心（若非零）在正实轴上
        - 通过反射使第一个不在x轴上的点位于上半平面
    如果重心为零，则先旋转使1号点在正实轴，再反射使第一个非轴点在上半平面。
    返回新的 coords 和 circles。
    """
    # 提取点列表和标签
    labels = list(coords.keys())
    pts = [CC(coords[l]) for l in labels]
    n = len(pts)
    eps = 1e-12

    # 使用 Welzl 计算最小外接圆
    Cc, R = welzl(pts)

    # 平移和缩放
    pts_scaled = [(p - Cc) / R for p in pts]

    # 重心
    G = sum(pts_scaled) / n

    # 确定旋转和反射
    if abs(G) > eps:
        # 重心非零，旋转使重心在正实轴
        theta = G.argument()
        rot = CC(cos(theta), -sin(theta))  # 旋转因子 exp(-i*theta)
        pts_rot = [p * rot for p in pts_scaled]
        # 按标签顺序找第一个不在实轴上的点
        refl = False
        for lbl in labels:
            idx = labels.index(lbl)
            p = pts_rot[idx]
            if abs(p.imag()) > eps:
                if p.imag() < 0:
                    refl = True
                break
        if refl:
            pts_final = [p.conjugate() for p in pts_rot]
        else:
            pts_final = pts_rot
    else:
        # 重心为零，旋转使1号点在正实轴
        idx1 = labels.index(1)
        p1 = pts_scaled[idx1]
        theta = p1.argument()
        rot = CC(cos(theta), -sin(theta))
        pts_rot = [p * rot for p in pts_scaled]
        # 找第一个非轴点（排除1号）
        refl = False
        for lbl in labels:
            if lbl == 1:
                continue
            idx = labels.index(lbl)
            p = pts_rot[idx]
            if abs(p.imag()) > eps:
                if p.imag() < 0:
                    refl = True
                break
        if refl:
            pts_final = [p.conjugate() for p in pts_rot]
        else:
            pts_final = pts_rot

    # 构造新坐标字典
    new_coords = {lbl: pts_final[i] for i, lbl in enumerate(labels)}

    # 处理圆
    new_circles = {}
    for idx, (center, radii) in circles.items():
        c = CC(center)
        c_new = (c - Cc) / R
        c_new = c_new * rot
        if refl:
            c_new = c_new.conjugate()
        radii_new = [r / R for r in radii]
        new_circles[idx] = (c_new, radii_new)

    return new_coords, new_circles

# ------------------- 绘图函数 -------------------
def plot_puzzle(coords, circles, points_labels=True):
    G = Graphics()
    # 点
    pts = [(c.real(), c.imag()) for c in coords.values()]
    G += points(pts, color='blue', size=30)
    if points_labels:
        for label, c in coords.items():
            G += text(str(label), (c.real(), c.imag()), fontsize=10, color='red')
    # 圆
    colors = ['red', 'green', 'purple', 'orange', 'brown']
    for idx, (center, radii) in circles.items():
        col = colors[idx % len(colors)]
        for r in radii:
            G += circle((center.real(), center.imag()), r, color=col, thickness=2)
    G.set_aspect_ratio(1)
    return G

# ------------------- 主函数 -------------------
def circle_puzzle_from_generators(generators, trials=100, plot=True, normalize=True, seed=None, name=""):
    """
    主函数。
    generators : 置换列表
    trials : 随机采样尝试次数
    plot : 是否显示图形
    normalize : 是否进行归一化
    seed : 随机种子，用于重复结果
    """
    if seed is not None:
        set_random_seed(seed)
        random.seed(seed)  # 同时设置 Python 随机种子

    points, gens_info = preprocess(generators)
    M, var_names = build_constraint_matrix(points, gens_info)
    basis = solve_nullspace(M, name=name, points=points)
    if not basis:
        print("解空间维数为零，无法构造拼图。")
        return None
    result = sample_and_check(basis, points, gens_info, trials=trials, name=name)
    if result is None:
        print("未找到非退化解。")
        return None
    coords, circles = result

    if normalize:
        coords, circles = normalize_coords(coords, circles)

    if plot:
        G = plot_puzzle(coords, circles)
        G.show()
        return coords, circles, G
    else:
        return coords, circles

# ------------------- JSON 导出 -------------------
def save_puzzle_json(coords, circles, generators, filepath):
    """将计算结果导出为 JSON，供 3/ 程序使用"""
    import json
    data = {
        "generators": [list(g.cycle_tuples()) for g in generators],
        "coords": {str(k): (float(v.real()), float(v.imag())) for k, v in coords.items()},
        "circles": {
            str(k): {
                "center": (float(v[0].real()), float(v[0].imag())),
                "radii": [float(r) for r in v[1]]
            } for k, v in circles.items()
        }
    }
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)
    print(f"已保存到 {filepath}")

# =================== 来自论坛帖子的生成元集 ===================
# 来源: https://twistypuzzles.com/forum/viewtopic.php?t=31806
# will_57 的帖子 "From groups to circle puzzles"
# 每个生成元集以 (名称, [生成元列表]) 形式组织

EXAMPLES = {
    # 注意：第一帖 (2017-05-20) 的 M12 (N1=3,N2=4) 和 S8_28pts 的生成元
    # 在原文中仅以图片形式给出，未提供显式轮换表示，故未收录。

    # --- 第二帖 (2018-01-02) ---
    "M12_N4_N4": [
        Permutation('(1,6,5,3)(9,10,11,12)'),
        Permutation('(2,7,4,9)(3,8,5,11)'),
    ],
    "PSp(6,2)_N2_N9": [
        Permutation('(1,25,15,27,2,19,4,9,12)(3,18,28,24,20,6,11,22,21)(5,10,23,14,17,26,7,8,13)'),
        Permutation('(1,27)(2,20)(4,16)(6,14)(8,13)(11,12)'),
    ],
    "PSL(2,13)_N2_N3": [
        Permutation('(1,12,11)(2,3,14)(4,10,13)(5,7,9)'),
        Permutation('(1,14)(4,12)(5,6)(7,10)(8,13)(9,11)'),
    ],
    "(S5xS5)_C2_N2_N8": [
        Permutation('(1,13,22,16,14,2,18,24)(3,23,21,11,12,17,19,4)(5,8,25,6,15,7,20,9)'),
        Permutation('(1,6)(2,7)(3,8)(4,9)(5,10)'),
    ],
    "((C2^4)_A5)_C2_emb1_N2_N5": [
        Permutation('(1,7)(2,8)(9,15)(10,16)'),
        Permutation('(1,14,3,10,9)(2,6,16,7,4)(5,8,12,13,11)'),
    ],
    "((C2^4)_A5)_C2_emb2_N2_N8": [
        Permutation('(1,10,9,7,12,3,4,14)(2,8,6,16,11,13,15,5)'),
        Permutation('(2,9)(3,12)(5,14)(8,15)'),
    ],
    "PGammaL(3,4)_3xN2": [
        Permutation('(2,17)(3,10)(6,20)(7,15)(9,13)(11,12)(18,21)'),
        Permutation('(1,11)(2,9)(4,16)(6,15)(8,21)(12,19)(14,18)'),
        Permutation('(1,14)(2,8)(3,7)(5,6)(10,11)(16,21)(18,20)'),
    ],
    "PSL(3,4)_subgroup": [
        Permutation('(2,8,17)(3,6,15)(5,21,18)(7,20,10)(9,13,14)(11,12,16)'),
        Permutation('(1,11,20)(2,10,9)(4,18,21)(5,6,15)(7,12,19)(8,14,16)'),
        Permutation('(1,5)(2,8)(4,17)(6,14)(9,15)(10,11)(16,20)(18,21)'),
    ],

    # --- 第三帖 (2018-01-02 22:58) ---
    "M24_N3_N3": [
        Permutation('(1,3,8)(4,16,18)(5,13,14)(6,17,9)(7,12,23)(11,15,22)'),
        Permutation('(1,4,10)(2,3,13)(5,24,20)(8,21,23)(9,19,15)(12,17,16)'),
    ],
    "S6_15pts_N2_N5": [
        Permutation('(1,9,4,12,6)(2,15,7,8,11)(3,5,10,13,14)'),
        Permutation('(2,4)(3,6)(5,9)(8,12)'),
    ],
    "S7_21pts_2xN2_N5": [
        Permutation('(1,2,3,5,8)(4,7,11,15,12)(6,9,13,18,16)(10,14,19,20,21)'),
        Permutation('(3,4)(7,10)(8,12)(13,17)(14,15)'),
        Permutation('(4,6)(7,9)(11,13)(12,16)(15,18)'),
    ],
    "S9_36pts_2xN2_N7": [
        Permutation('(1,2,33,4,5,27,10)(3,22,25,35,34,7,30)(6,8,12,17,20,15,11)(9,13,18,23,26,21,16)(14,19,28,32,29,31,36)'),
        Permutation('(4,6)(7,11)(8,14)(15,22)(17,19)(18,24)(20,27)'),
        Permutation('(6,9)(8,13)(11,16)(12,18)(15,21)(17,23)(20,26)'),
    ],
    "S11_55pts_2xN2_N5": [
        Permutation('(1,53,43,23,37)(2,27,20,55,42)(3,24,45,32,17)(4,28,13,44,21)(5,12,16,47,25)(6,29,51,35,15)(7,39,22,54,48)(8,41,31,9,49)(10,14,52,36,19)(11,26,33,18,50)(30,46,40,38,34)'),
        Permutation('(3,47)(5,17)(24,26)(30,52)(32,33)(34,37)(38,39)(40,41)(46,51)'),
        Permutation('(3,48)(8,24)(13,34)(17,53)(21,38)(30,55)(32,36)(40,42)(45,51)'),
    ],
    "S12_66pts_N2_N5_N7": [
        Permutation('(1,5,10,16,65)(3,12,20,66,41)(4,11,17,24,64)(6,8,31,49,39)(9,19,25,33,63)(14,59,29,57,22)(15,28,34,42,62)(23,38,43,50,61)(32,48,51,58,60)'),
        Permutation('(1,22)(2,8)(5,12)(16,20)(17,18)(25,27)(34,37)(43,47)(51,56)(59,65)'),
        Permutation('(1,15,23,32,39,4,9)(2,36,45,56,21,46,54)(5,28,38,48,6,11,19)(7,26,27,37,44,52,40)(8,17,25,10,34,43,51)(13,18,35,47,53,30,55)(16,42,50,58,31,24,33)(49,64,63,65,62,61,60)'),
    ],
    "S8_56pts_N2_N7": [
        Permutation('(1,2)(3,5)(6,9)(11,14)(12,16)(13,18)(20,25)(21,27)(22,29)(23,31)(24,33)(34,35)(36,41)(42,48)(49,54)'),
        Permutation('(1,49,36,10,24,19,13)(2,53,38,54,30,11,15)(3,28,56,31,21,6,42)(4,22,18,39,52,51,48)(5,33,23,17,7,50,44)(8,37,43,41,12,32,27)(9,47,45,25,34,40,46)(14,20,26,16,29,55,35)'),
    ],
    "S9_84pts_2xN2_N7": [
        Permutation('(1,2,4,8,14,23,36)(3,6,12,20,32,49,37)(5,10,18,29,45,24,38)(7,13,21,33,50,65,54)(9,16,27,42,15,25,40)(11,19,30,46,61,39,55)(17,28,43,58,26,41,56)(22,35,53,69,84,80,70)(31,48,64,79,66,81,71)(34,52,68,83,76,57,72)(44,60,75,51,67,82,73)(47,63,78,62,77,59,74)'),
        Permutation('(1,3)(2,5)(4,9)(8,15)(13,22)(14,24)(19,31)(21,34)(23,37)(28,44)(30,47)(33,51)(41,57)(43,59)(46,62)(50,66)(55,70)(56,71)(58,73)(61,76)(65,80)'),
        Permutation('(3,7)(5,11)(6,13)(9,17)(10,19)(12,21)(15,26)(16,28)(18,30)(20,33)(24,39)(25,41)(27,43)(29,46)(32,50)(37,54)(38,55)(40,56)(42,58)(45,61)(49,65)'),
    ],
}

# ------------------- 示例 -------------------
if __name__ == "__main__":
    import os
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "3")
    os.makedirs(out_dir, exist_ok=True)

    for example_name, gens in EXAMPLES.items():
        print(f"\n{'='*60}")
        print(f"运行示例: {example_name}")
        print(f"生成元: {gens}")
        print(f"{'='*60}")

        try:
            result = circle_puzzle_from_generators(gens, trials=200, plot=False, normalize=True, seed=42, name=example_name)
            if result:
                coords, circles = result
                print(f"成功! 归一化坐标: {coords}")
                print(f"归一化圆: {circles}")
                save_puzzle_json(coords, circles, gens, os.path.join(out_dir, f"{example_name}.json"))
            else:
                print("失败: 未找到非退化解")
        except Exception as e:
            print(f"错误: {e}")