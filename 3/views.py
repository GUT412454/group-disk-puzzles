import math
import pygame
from typing import Dict, List, Tuple, Optional
from models import Position, CubeState, GameConfig, AnimationState, Move, GroupModel

# OKLab 知觉均匀色空间 → sRGB
def oklab_to_rgb(L: float, a: float, b: float) -> Tuple[int, int, int]:
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l = l_ * l_ * l_
    m = m_ * m_ * m_
    s = s_ * s_ * s_
    r_lin = 4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
    g_lin = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
    b_lin = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s
    def gamma(c):
        if c <= 0.0031308:
            return 12.92 * max(0, c)
        return 1.055 * (c ** (1/2.4)) - 0.055
    return (
        max(0, min(int(gamma(r_lin) * 255 + 0.5), 255)),
        max(0, min(int(gamma(g_lin) * 255 + 0.5), 255)),
        max(0, min(int(gamma(b_lin) * 255 + 0.5), 255)),
    )

# ---- 泰森多边形（Voronoi）函数 ----

def half_plane_clip(poly: List[Tuple[float, float]], A: complex, B: complex) -> List[Tuple[float, float]]:
    """用AB的中垂线裁剪多边形，保留A所在半平面"""
    if not poly:
        return []
    Mx = (A.real + B.real) * 0.5
    My = (A.imag + B.imag) * 0.5
    Nx = B.real - A.real
    Ny = B.imag - A.imag

    result = []
    n = len(poly)
    for i in range(n):
        curr = poly[i]
        nxt = poly[(i + 1) % n]

        d_curr = (curr[0] - Mx) * Nx + (curr[1] - My) * Ny
        d_nxt  = (nxt[0]  - Mx) * Nx + (nxt[1]  - My) * Ny

        inside_curr = d_curr < 0.0
        inside_nxt  = d_nxt  < 0.0

        if inside_curr != inside_nxt:
            denom = (nxt[0] - curr[0]) * Nx + (nxt[1] - curr[1]) * Ny
            if abs(denom) > 1e-12:
                t = -d_curr / denom
                ix = curr[0] + t * (nxt[0] - curr[0])
                iy = curr[1] + t * (nxt[1] - curr[1])
            else:
                ix, iy = (curr[0] + nxt[0]) * 0.5, (curr[1] + nxt[1]) * 0.5

        if inside_curr:
            result.append(curr)
            if not inside_nxt:
                result.append((ix, iy))
        elif inside_nxt:
            result.append((ix, iy))
    return result


def polygon_centroid(poly: List[Tuple[float, float]]) -> Optional[Tuple[float, float]]:
    """鞋带公式计算凸多边形重心"""
    n = len(poly)
    if n < 3:
        return None
    area = 0.0
    cx = 0.0
    cy = 0.0
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        cross = x0 * y1 - x1 * y0
        area += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    area *= 0.5
    if abs(area) < 1e-10:
        return None
    s = 1.0 / (6.0 * area)
    return (cx * s, cy * s)


def compute_voronoi_centroids(points: List[complex],
                               bounds: Tuple[float, float, float, float]) -> List[complex]:
    """用顶点裁剪法计算每个块的泰森多边形重心"""
    n = len(points)
    xmin, ymin, xmax, ymax = bounds
    centroids = []
    for i in range(n):
        poly = [(xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax)]
        for j in range(n):
            if i == j:
                continue
            poly = half_plane_clip(poly, points[i], points[j])
            if len(poly) < 3:
                break
        cent = polygon_centroid(poly)
        centroids.append(complex(*cent) if cent else points[i])
    return centroids


# ---- 能量优化：在 a-b 色平面上均匀摊开相邻块的颜色 ----

def optimize_colors(centroids: List[complex],
                    initial_a: List[float],
                    initial_b: List[float],
                    pw: float, ph: float,
                    n_iters: int = 150) -> Tuple[List[float], List[float]]:
    """能量优化：邻近块的颜色互相排斥 + 弹簧拉回初始位置"""
    n = len(centroids)
    a = list(initial_a)
    b = list(initial_b)

    # 自适应空间距离阈值
    avg_nn = 0.0
    for i in range(n):
        xi, yi = centroids[i].real, centroids[i].imag
        md = float('inf')
        for j in range(n):
            if i == j: continue
            d = math.hypot(xi - centroids[j].real, yi - centroids[j].imag)
            if d < md: md = d
        avg_nn += md
    avg_nn = avg_nn / max(n, 2)
    R_spatial = avg_nn * 2.5

    D_target = 0.5 * 0.34 / math.sqrt(max(n, 2))
    w_repel, w_spring, lr0 = 0.3, 0.7, 0.05

    for it in range(n_iters):
        lr = lr0 * (1.0 - it / n_iters)

        # 排斥力：空间近且色距近 → 推开
        for i in range(n):
            xi, yi = centroids[i].real, centroids[i].imag
            ai, bi = a[i], b[i]
            for j in range(i + 1, n):
                xj, yj = centroids[j].real, centroids[j].imag
                if math.hypot(xi - xj, yi - yj) > R_spatial:
                    continue
                da, db = ai - a[j], bi - b[j]
                d_col = math.hypot(da, db)
                if d_col < D_target and d_col > 1e-10:
                    f = min((D_target - d_col) / d_col, 10.0)
                    p = lr * w_repel * f
                    a[i] += p * da; a[j] -= p * da
                    b[i] += p * db; b[j] -= p * db

        # 弹簧力：不让颜色偏离初始位置太远
        for i in range(n):
            a[i] += lr * w_spring * (initial_a[i] - a[i])
            b[i] += lr * w_spring * (initial_b[i] - b[i])

        # 钳位到安全色域
        for i in range(n):
            a[i] = max(-0.25, min(0.25, a[i]))
            b[i] = max(-0.25, min(0.25, b[i]))

    return a, b


class BlockView:
    def __init__(self, block_id: int, logical_position: Position, config: GameConfig, model=None):
        self.block_id = block_id
        self.logical_position = logical_position
        self.config = config
        self._model = model
        self._centroid = None
        if model and hasattr(model, 'display_position'):
            self.display_position = model.display_position(logical_position.x)
        else:
            self.display_position = self._grid_position(logical_position)
        self.color = self._calculate_color()

    def get_display_for(self, pos: Position) -> complex:
        if self._model and hasattr(self._model, 'display_position'):
            return self._model.display_position(pos.x)
        return self._grid_position(pos)
    
    def _grid_position(self, pos: Position) -> complex:
        """将网格位置转换为屏幕坐标"""
        x = (pos.x * 120) + 120
        y = 600 - ((pos.y * 120) + 120)  # 反转Y轴
        return complex(x, y)

    def _position_to_display(self, pos: Position) -> complex:
        """将任意 Position 转为显示坐标（支持 sage 和 grid 两种模式）"""
        if self.model and hasattr(self.model, 'display_position'):
            return self.model.display_position(pos.x)
        return self._grid_position(pos)
    
    def _calculate_color(self) -> Tuple[int, int, int]:
        """根据泰森重心计算 OKLab 知觉均匀颜色"""
        if self._centroid is not None:
            x = self._centroid.real
            y = self._centroid.imag
        else:
            x = self.display_position.real
            y = self.display_position.imag
        pw = self.config.puzzle_area_width
        ph = self.config.height
        L = 0.72
        a = (x / pw - 0.5) * 0.34
        b = (y / ph - 0.5) * 0.34
        return oklab_to_rgb(L, a, b)
    
    def draw(self, screen: pygame.Surface, display_position: complex = None):
        """绘制块"""
        pos = display_position if display_position else self.display_position
        x, y = int(pos.real), int(pos.imag)
        
        # 绘制边框
        border_radius = self.config.block_radius + self.config.block_border
        pygame.draw.circle(screen, (255, 255, 255), (x, y), border_radius, 2)
        
        # 绘制块
        pygame.draw.circle(screen, self.color, (x, y), self.config.block_radius)

def generate_background(width: int, height: int, blocks: Dict[int, BlockView], config: GameConfig) -> pygame.Surface:
    """生成灰色背景 + 每个位置有比块稍大的彩色实心圆"""
    background = pygame.Surface((width, height))
    background.fill((60, 60, 60))
    spot_radius = config.block_radius * 2
    for block_view in blocks.values():
        x, y = int(block_view.display_position.real), int(block_view.display_position.imag)
        pygame.draw.circle(background, block_view.color, (x, y), spot_radius)
    return background

class CubeView:
    def __init__(self, config: GameConfig, model: GroupModel = None):
        self.config = config
        self.model = model
        self.blocks: Dict[int, BlockView] = {}
        self._initialize_blocks()
        self.background = generate_background(config.width, config.height, self.blocks, config)
    
    def _get_display_position(self, pos: Position) -> complex:
        """将逻辑位置转为像素坐标（与 BlockView 保持一致）"""
        if self.model and hasattr(self.model, 'display_position'):
            return self.model.display_position(pos.x)
        x = (pos.x * 120) + 120
        y = 600 - ((pos.y * 120) + 120)
        return complex(x, y)
    
    def _initialize_blocks(self):
        """初始化所有块，并计算泰森重心"""
        if self.model:
            positions = self.model.get_positions()
        else:
            positions = [
                Position(0, 0), Position(0, 3), Position(3, 3), Position(3, 0),
                Position(1, 1), Position(1, 2), Position(2, 2), Position(2, 1),
                Position(1, 3), Position(2, 3), Position(3, 2), Position(3, 1)
            ]
        
        for i, pos in enumerate(positions):
            self.blocks[i] = BlockView(i, pos, self.config, self.model)
        
        # 计算泰森多边形重心 → 能量优化 → 回写颜色
        if len(self.blocks) >= 3:
            dps = [bv.display_position for bv in self.blocks.values()]
            bounds = (0, 0, self.config.puzzle_area_width, self.config.height)
            centroids = compute_voronoi_centroids(dps, bounds)

            pw = self.config.puzzle_area_width
            ph = self.config.height
            initial_a = [(c.real / pw - 0.5) * 0.34 for c in centroids]
            initial_b = [(c.imag / ph - 0.5) * 0.34 for c in centroids]
            opt_a, opt_b = optimize_colors(centroids, initial_a, initial_b, pw, ph)

            for i, bv in enumerate(self.blocks.values()):
                bv._centroid = centroids[i]
                bv.color = oklab_to_rgb(0.72, opt_a[i], opt_b[i])
    
    def draw(self, screen: pygame.Surface, 
             animation_states: Dict[int, AnimationState] = None,
             current_state: CubeState = None):
        """绘制整个魔方：背景图 + 块 + 分隔线"""
        screen.blit(self.background, (0, 0))
        for block_id, block_view in self.blocks.items():
            display_pos = None
            if animation_states and block_id in animation_states:
                anim_state = animation_states[block_id]
                display_pos = anim_state.update()
            block_view.draw(screen, display_pos)
        # 图像区与文字区之间的白色分隔线
        x = self.config.puzzle_area_width
        pygame.draw.line(screen, (255, 255, 255), (x, 0), (x, self.config.height), 1)
    
    def get_disk_centers(self) -> List[complex]:
        """获取转盘中心位置"""
        if self.model and hasattr(self.model, 'disk_centers') and self.model.disk_centers:
            return self.model.disk_centers
        return [
            complex(300, 300),  # 左转盘中心 (1.5, 1.5)
            complex(360, 240)   # 右转盘中心 (2, 2)
        ]

class UIView:
    def __init__(self, config: GameConfig, model: GroupModel = None):
        self.config = config
        self.model = model
        self.font = pygame.font.SysFont("SimHei", 24)
        self.small_font = pygame.font.SysFont("SimHei", 18)
    
    def draw_controls(self, screen: pygame.Surface):
        """绘制控制说明（右侧面板）"""
        x = 615
        model_name = self.model.get_model_name() if self.model else "M12 Puzzle"
        controls = [
            f"模型: {model_name}",
            "Q:左逆  S:左顺",
            "L:右逆  P:右顺",
            "方向键: 加入队列",
            "空格:求解  R:重置  M:打乱",
            "[:上模型  ]:下模型",
            "1:M12内置  2-9:Sage"
        ]
        
        for i, text in enumerate(controls):
            text_surface = self.small_font.render(text, True, (255, 255, 255))
            screen.blit(text_surface, (x, 15 + i * 23))
    
    def draw_model_info(self, screen: pygame.Surface, available_models: List[str], current_model: str):
        """绘制模型信息（右侧面板）"""
        x, y = 615, 400
        text = f"可用模型: {len(available_models)}个"
        text_surface = self.small_font.render(text, True, (200, 200, 200))
        screen.blit(text_surface, (x, y))
        
        text = f"当前: {current_model}"
        text_surface = self.small_font.render(text, True, (255, 255, 255))
        screen.blit(text_surface, (x, y + 22))
    
    def draw_solution(self, screen: pygame.Surface, solution: List[Move], current_step: int):
        """绘制解法信息（右侧面板）"""
        if not solution:
            return
        
        text_surface = self.font.render(f"解法: {current_step + 1}/{len(solution)}", True, (255, 255, 255))
        screen.blit(text_surface, (615, 500))
        text_surface = self.small_font.render(str(solution[current_step]), True, (255, 255, 255))
        screen.blit(text_surface, (615, 528))
    
    def draw_solving(self, screen: pygame.Surface):
        """显示求解中状态（右侧面板）"""
        text = "求解中..."
        text_surface = self.font.render(text, True, (255, 255, 255))
        screen.blit(text_surface, (615, 530))
    
    def draw_scrambling(self, screen: pygame.Surface):
        """显示打乱中状态（右侧面板）"""
        text = "打乱中..."
        text_surface = self.font.render(text, True, (255, 255, 255))
        screen.blit(text_surface, (615, 530))