import pygame
from typing import Dict, List, Tuple
from models import Position, CubeState, GameConfig, AnimationState, Move, GroupModel

# YUV 到 RGB 转换函数
def yuv_to_rgb(y: float, u: float, v: float) -> Tuple[int, int, int]:
    r = int(y + 1.2 * (v - 128))
    g = int(y - 0.6 * (u - 128) - 0.6 * (v - 128))
    b = int(y + 1.2 * (u - 128))
    return max(0, min(r, 255)), max(0, min(g, 255)), max(0, min(b, 255))

# 生成渐变背景图像
def generate_gradient_background(width: int, height: int) -> pygame.Surface:
    background = pygame.Surface((width, height))
    for x in range(width):
        for y in range(height):
            u = 256 * (x / width)
            v = 256 * (y / height)
            gradient_color = yuv_to_rgb(128, u, v)
            background.set_at((x, y), gradient_color)
    return background

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

class CubeView:
    def __init__(self, config: GameConfig, model: GroupModel = None):
        self.config = config
        self.model = model
        self.blocks: Dict[int, BlockView] = {}
        self.background = generate_gradient_background(config.width, config.height)
        self._initialize_blocks()
    
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
        """绘制整个魔方（内置画法：背景 + 块，无圆环）"""
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
        """绘制控制说明"""
        model_name = self.model.get_model_name() if self.model else "M12 Puzzle"
        controls = [
            f"当前模型: {model_name}",
            "Q/S - 左(重心)转盘逆/顺   L/P - 右(重心)转盘逆/顺",
            "方向键: 加入旋转队列  空格: 求解  R: 重置  M: 打乱",
            "1: M12内置  [ / ]: 上下模型  2-9: 选择Sage模型"
        ]
        
        for i, text in enumerate(controls):
            text_surface = self.font.render(text, True, (255, 255, 255))
            screen.blit(text_surface, (10, 10 + i * 25))
    
    def draw_model_info(self, screen: pygame.Surface, available_models: List[str], current_model: str):
        """绘制模型信息"""
        y_pos = 400
        text = f"可用模型: {', '.join(available_models)}"
        text_surface = self.small_font.render(text, True, (200, 200, 200))
        screen.blit(text_surface, (10, y_pos))
        
        text = f"当前模型: {current_model}"
        text_surface = self.small_font.render(text, True, (255, 255, 255))
        screen.blit(text_surface, (10, y_pos + 20))
    
    def draw_solution(self, screen: pygame.Surface, solution: List[Move], current_step: int):
        """绘制解法信息"""
        if not solution:
            return
        
        text = f"解法: {current_step + 1}/{len(solution)} - {solution[current_step]}"
        text_surface = self.font.render(text, True, (255, 255, 255))
        screen.blit(text_surface, (10, 500))
    
    def draw_solving(self, screen: pygame.Surface):
        """显示求解中状态"""
        text = "求解中..."
        text_surface = self.font.render(text, True, (255, 255, 255))
        screen.blit(text_surface, (10, 530))
    
    def draw_scrambling(self, screen: pygame.Surface):
        """显示打乱中状态"""
        text = "打乱中..."
        text_surface = self.font.render(text, True, (255, 255, 255))
        screen.blit(text_surface, (10, 530))