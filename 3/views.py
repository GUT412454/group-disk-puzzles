import pygame
from typing import Dict, List, Tuple
from models import Position, CubeState, GameConfig, AnimationState, Move, GroupModel

# YUV 到 RGB 转换函数
def yuv_to_rgb(y: float, u: float, v: float) -> Tuple[int, int, int]:
    r = int(y + 1.2 * (v - 128))
    g = int(y - 0.6 * (u - 128) - 0.6 * (v - 128))
    b = int(y + 1.2 * (u - 128))
    return max(0, min(r, 255)), max(0, min(g, 255)), max(0, min(b, 255))

class BlockView:
    def __init__(self, block_id: int, logical_position: Position, config: GameConfig, model=None):
        self.block_id = block_id
        self.logical_position = logical_position
        self.config = config
        self._model = model
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
        """根据位置计算颜色"""
        x = int(self.display_position.real)
        y = int(self.display_position.imag)
        u = 256 * (x / self.config.width)
        v = 256 * (y / self.config.height)
        return yuv_to_rgb(128, u, v)
    
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
    
    def _initialize_blocks(self):
        """初始化所有块"""
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
    
    def draw(self, screen: pygame.Surface, 
             animation_states: Dict[int, AnimationState] = None,
             current_state: CubeState = None):
        """绘制整个魔方：背景图 + 块"""
        screen.blit(self.background, (0, 0))
        for block_id, block_view in self.blocks.items():
            display_pos = None
            if animation_states and block_id in animation_states:
                anim_state = animation_states[block_id]
                display_pos = anim_state.update()
            block_view.draw(screen, display_pos)
    
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