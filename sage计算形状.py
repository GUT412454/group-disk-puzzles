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

def solve_nullspace(M):
    if M is None:
        return []
    ker = M.right_kernel()
    return ker.basis()

def sample_and_check(basis, points, gens_info, trials=100, epsilon=1e-8):
    if not basis:
        return None
    d = len(basis)
    basis_vecs = [list(v) for v in basis]
    n_points = len(points)
    n_gens = len(gens_info)

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
            continue

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

        # 检查不被移动的点是否落在任何半径的圆上
        degenerate = False
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
                    for r in radii_lists[idx]:
                        if abs(dist - r) < epsilon:
                            degenerate = True
                            break
                    if degenerate:
                        break
            if degenerate:
                break
        if degenerate:
            continue

        # 通过检验
        coords = {p: ComplexField(100)(point_vals[i]) for i, p in enumerate(points)}
        circles = {idx: (ComplexField(100)(center_vals[idx]), radii_lists[idx])
                   for idx, info in enumerate(gens_info) if info['order'] > 1}
        return coords, circles

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
def circle_puzzle_from_generators(generators, trials=100, plot=True, normalize=True, seed=None):
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
    basis = solve_nullspace(M)
    if not basis:
        print("解空间维数为零，无法构造拼图。")
        return None
    result = sample_and_check(basis, points, gens_info, trials=trials)
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

# ------------------- 示例 -------------------
if __name__ == "__main__":
    g1 = Permutation('(1,6,5,3)(9,10,11,12)')
    g2 = Permutation('(2,7,4,9)(3,8,5,11)')
    gens = [g1, g2]

    # 固定种子使结果可重复
    result = circle_puzzle_from_generators(gens, trials=200, plot=True, normalize=True, seed=42)
    if result:
        coords, circles, plot_obj = result
        print("归一化坐标：", coords)
        print("归一化圆：", circles)