import cmath
import json
import math
import os
from dataclasses import dataclass
from typing import List, Tuple, Dict, Set, Optional, Any
from abc import ABC, abstractmethod
from collections import deque
import heapq
import random
from abc import ABC, abstractmethod

# 在文件顶部添加全局模型管理
_current_model = None

def set_current_model(model):
    global _current_model
    _current_model = model

def get_current_model():
    return _current_model

# 配置类
@dataclass
class GameConfig:
    animation_frames: int = 20
    frame_rate: int = 120
    width: int = 600
    height: int = 600
    block_radius: int = 20
    block_border: int = 2

# 位置和操作定义
@dataclass(frozen=True)
class Position:
    x: int
    y: int
    
    def __str__(self):
        return f"({self.x},{self.y})"

@dataclass(frozen=True)
class Move:
    disk_index: int
    direction: int  # 1: 顺时针, -1: 逆时针
    
    def __str__(self):
        direction_str = "顺时针" if self.direction == 1 else "逆时针"
        return f"转盘{self.disk_index}{direction_str}"
    
    def key(self, reverse=False, disk_key_order=None):
        """
        返回键盘按键字符。
        disk_key_order: [左盘索引, 右盘索引, ...] 按重心x排序。
        """
        if disk_key_order is None:
            disk_key_order = [0, 1]
        key_map = {}
        if len(disk_key_order) > 0:
            key_map[(disk_key_order[0], -1)] = 'Q'
            key_map[(disk_key_order[0], 1)] = 'S'
        if len(disk_key_order) > 1:
            key_map[(disk_key_order[1], -1)] = 'L'
            key_map[(disk_key_order[1], 1)] = 'P'
        return key_map.get((self.disk_index, self.direction * (-1 if reverse else 1)), '?')
    
    def sign(self):
        return str(self.disk_index) + {1: '+', -1: '-'}[self.direction]

# 魔方状态类
class CubeState:
    def __init__(self, positions: Dict[Position, int]):
        self.positions = positions.copy()  # Position -> block_id
        self._blocks = list(positions.keys())
        self._blocks.sort(key=lambda p: (p.x, p.y))
    
    def encode(self) -> str:
        """将状态编码为字符串用于哈希和比较"""
        return ''.join(str(self.positions[p]) for p in self._blocks)
    
    def apply_move(self, move: Move, disk_configs: List[List[List[Position]]]) -> 'CubeState':
        """应用一个操作，返回新状态"""
        new_positions = self.positions.copy()
        orbit_positions = disk_configs[move.disk_index]
        
        for orbit in orbit_positions:
            n = len(orbit)
            for i, pos in enumerate(orbit):
                new_index = (i + move.direction) % n
                new_pos = orbit[new_index]
                new_positions[new_pos] = self.positions[pos]
        
        return CubeState(new_positions)
    
    def is_solved(self, target_state: 'CubeState') -> bool:
        return self.encode() == target_state.encode()
    
    def __eq__(self, other):
        return self.encode() == other.encode()
    
    def __hash__(self):
        return hash(self.encode())

# 求解器接口和实现
class ISolver(ABC):
    @abstractmethod
    def solve(self, start_state: CubeState, target_state: CubeState, 
              disk_configs: List[List[List[Position]]]) -> List[Move]:
        pass

class BidirectionalBFSSolver(ISolver):
    def solve(self, start_state: CubeState, target_state: CubeState,
              disk_configs: List[List[List[Position]]]) -> List[Move]:
        if start_state.is_solved(target_state):
            return []
        
        # 正向搜索：从起始状态到目标状态
        forward_queue = deque([(start_state, [])])
        forward_visited = {start_state.encode(): []}
        
        # 反向搜索：从目标状态到起始状态，但记录的是逆操作
        backward_queue = deque([(target_state, [])])
        backward_visited = {target_state.encode(): []}
        
        while forward_queue and backward_queue:
            # 检查是否有交集
            intersection = self._find_intersection(forward_visited, backward_visited)
            if intersection:
                return self._reconstruct_path(intersection, forward_visited, backward_visited)
            
            # 扩展正向搜索
            if len(forward_queue) <= len(backward_queue):
                self._expand_forward(forward_queue, forward_visited, disk_configs)
            else:
                self._expand_backward(backward_queue, backward_visited, disk_configs)
        
        return []
    
    def _expand_forward(self, queue, visited, disk_configs):
        """扩展正向搜索"""
        current_state, path = queue.popleft()
        
        for disk_index in range(len(disk_configs)):
            for direction in [1, -1]:
                move = Move(disk_index, direction)
                new_state = current_state.apply_move(move, disk_configs)
                new_path = path + [move]
                
                if new_state.encode() not in visited:
                    visited[new_state.encode()] = new_path
                    queue.append((new_state, new_path))
    
    def _expand_backward(self, queue, visited, disk_configs):
        """扩展反向搜索：应用逆操作"""
        current_state, path = queue.popleft()
        
        for disk_index in range(len(disk_configs)):
            for direction in [1, -1]:
                # 注意：反向搜索时，我们应用逆操作
                inverse_move = Move(disk_index, -direction)
                new_state = current_state.apply_move(inverse_move, disk_configs)
                # 在路径开头添加原操作（不是逆操作）
                new_path = [Move(disk_index, direction)] + path
                
                if new_state.encode() not in visited:
                    visited[new_state.encode()] = new_path
                    queue.append((new_state, new_path))
    
    def _find_intersection(self, forward_visited, backward_visited):
        """查找正向和反向搜索的交集状态"""
        for state_key in forward_visited:
            if state_key in backward_visited:
                return state_key
        return None
    
    def _reconstruct_path(self, intersection_key, forward_visited, backward_visited):
        """重建完整路径"""
        forward_path = forward_visited[intersection_key]
        backward_path = backward_visited[intersection_key]
        
        # 正向路径 + 反向路径（注意反向路径已经是正确方向）
        return forward_path + backward_path

# 动画状态
class AnimationState:
    def __init__(self, block_id: int, start_pos: complex, target_pos: complex, 
                 center: complex, frames: int, direction: int = 1):
        self.block_id = block_id
        self.start_pos = start_pos
        self.target_pos = target_pos
        self.center = center
        self.frames = frames
        self.direction = direction  # 1: 顺时针, -1: 逆时针
        self.current_frame = 0
        self.is_completed = False
    
    def update(self) -> complex:
        """更新动画，返回当前位置"""
        if self.is_completed:
            return self.target_pos
        
        self.current_frame += 1
        if self.current_frame >= self.frames:
            self.is_completed = True
            return self.target_pos
        
        # 使用复数运算进行平滑旋转
        now_relative = self.start_pos - self.center
        new_relative = self.target_pos - self.center
        eps = 1e-12

        # 起点在圆心 → 直接跳到目标
        if abs(now_relative) < eps:
            return self.target_pos
        # 终点在圆心 → 直接跳到目标
        if abs(new_relative) < eps:
            progress = (self.current_frame + 1) / self.frames
            return self.center + now_relative * (1 - progress)

        quotient = new_relative / now_relative
        log_quotient = cmath.log(quotient)
        # 仅在 180° 附近强制动画方向与操作方向一致
        angle = log_quotient.imag
        if abs(abs(angle) - math.pi) < 1e-10:
            if self.direction == 1:  # 顺时针 → 正角逆时针视觉效果
                angle = abs(angle)
            else:  # 逆时针 → 负角顺时针视觉效果
                angle = -abs(angle)
        log_quotient = log_quotient.real + 1j * angle

        progress = (self.current_frame + 1) / self.frames
        interpolate_quotient = cmath.exp(log_quotient * progress)
        current_pos = self.center + now_relative * interpolate_quotient

        return current_pos

class Scrambler:
    """打乱器类"""
    
    def __init__(self, disk_configs: List[List[List[Position]]]):
        self.disk_configs = disk_configs
        self.min_scramble_moves = 41  # 最小打乱步数
        self.max_scramble_moves = 50  # 最大打乱步数
    
    def generate_scramble(self, current_state: CubeState, avoid_undo: bool = True) -> List[Move]:
        """生成随机打乱序列"""
        # 随机确定打乱步数（奇数或偶数随机，避免限制解空间）
        num_moves = random.randint(self.min_scramble_moves, self.max_scramble_moves)
        
        scramble_moves = []
        last_move = None
        
        for _ in range(num_moves):
            move = self._get_random_move(last_move, avoid_undo)
            scramble_moves.append(move)
            last_move = move
        
        return scramble_moves
    
    def _get_random_move(self, last_move: Optional[Move], avoid_undo: bool) -> Move:
        """获取随机移动，避免立即撤销上一步操作"""
        while True:
            disk_index = random.randint(0, len(self.disk_configs) - 1)
            direction = random.choice([-1, 1])
            move = Move(disk_index, direction)
            
            # 如果不需避免撤销，或者这不是对上一步的撤销操作
            if not avoid_undo or not self._is_undo_move(move, last_move):
                return move
    
    def _is_undo_move(self, current_move: Move, last_move: Optional[Move]) -> bool:
        """检查当前移动是否撤销了上一步操作"""
        if last_move is None:
            return False
        
        # 如果是同一转盘的相反方向，就是撤销操作
        return (current_move.disk_index == last_move.disk_index and 
                current_move.direction == -last_move.direction)

class GroupModel(ABC):
    """群模型抽象基类"""
    
    @abstractmethod
    def get_positions(self) -> List[Position]:
        """获取所有位置"""
        pass
    
    @abstractmethod
    def get_generators(self) -> List['GroupAction']:
        """获取生成元（基本操作）"""
        pass
    
    @abstractmethod
    def get_initial_state(self) -> CubeState:
        """获取初始状态"""
        pass
    
    @abstractmethod
    def is_solved_state(self, state: CubeState) -> bool:
        """检查是否为解状态"""
        pass
    
    @abstractmethod
    def get_model_name(self) -> str:
        """获取模型名称"""
        pass

class GroupAction(ABC):
    """群作用抽象基类"""
    
    @abstractmethod
    def apply(self, state: CubeState) -> CubeState:
        """应用群作用"""
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """获取操作名称"""
        pass
    
    @abstractmethod
    def get_animation_center(self) -> complex:
        """获取动画中心点"""
        pass
    
    @abstractmethod
    def get_affected_positions(self) -> List[Position]:
        """获取受影响的位置"""
        pass

class M12Model(GroupModel):
    """M12 群模型实现"""
    
    def __init__(self):
        self.positions = [
            Position(0, 0), Position(0, 3), Position(3, 3), Position(3, 0),
            Position(1, 1), Position(1, 2), Position(2, 2), Position(2, 1),
            Position(1, 3), Position(2, 3), Position(3, 2), Position(3, 1)
        ]
        
        # 定义生成元（两个转盘的正反旋转）
        self.generators = [
            DiskRotation("left_clockwise", 0, 1, complex(300, 300)),
            DiskRotation("left_counterclockwise", 0, -1, complex(300, 300)),
            DiskRotation("right_clockwise", 1, 1, complex(360, 240)),
            DiskRotation("right_counterclockwise", 1, -1, complex(360, 240))
        ]
        
        # 转盘配置
        self.disk_configs = [
            [  # 左转盘
                [Position(0, 0), Position(0, 3), Position(3, 3), Position(3, 0)],
                [Position(1, 1), Position(1, 2), Position(2, 2), Position(2, 1)]
            ],
            [  # 右转盘
                [Position(1, 1), Position(1, 3), Position(3, 3), Position(3, 1)],
                [Position(1, 2), Position(2, 3), Position(3, 2), Position(2, 1)]
            ]
        ]
    
    def get_positions(self) -> List[Position]:
        return self.positions
    
    def get_generators(self) -> List[GroupAction]:
        return self.generators
    
    def get_initial_state(self) -> CubeState:
        positions_dict = {}
        for i, pos in enumerate(self.positions):
            positions_dict[pos] = i
        return CubeState(positions_dict)
    
    def is_solved_state(self, state: CubeState) -> bool:
        initial_state = self.get_initial_state()
        return state == initial_state
    
    def get_model_name(self) -> str:
        return "M12 Puzzle"

class DiskRotation(GroupAction):
    """转盘旋转操作"""
    
    def __init__(self, name: str, disk_index: int, direction: int, center: complex):
        self.name = name
        self.disk_index = disk_index
        self.direction = direction
        self.center = center
    
    def apply(self, state: CubeState) -> CubeState:
        # 这里需要访问模型配置，可以通过依赖注入解决
        model = get_current_model()  # 需要全局访问当前模型
        disk_configs = model.disk_configs if hasattr(model, 'disk_configs') else []
        
        if self.disk_index < len(disk_configs):
            orbit_positions = disk_configs[self.disk_index]
            new_positions = state.positions.copy()
            
            for orbit in orbit_positions:
                n = len(orbit)
                for i, pos in enumerate(orbit):
                    new_index = (i + self.direction) % n
                    new_pos = orbit[new_index]
                    new_positions[new_pos] = state.positions[pos]
            
            return CubeState(new_positions)
        return state
    
    def get_name(self) -> str:
        direction_str = "顺时针" if self.direction == 1 else "逆时针"
        return f"转盘{self.disk_index}{direction_str}"
    
    def get_animation_center(self) -> complex:
        return self.center
    
    def get_affected_positions(self) -> List[Position]:
        model = get_current_model()
        if hasattr(model, 'disk_configs') and self.disk_index < len(model.disk_configs):
            affected = []
            for orbit in model.disk_configs[self.disk_index]:
                affected.extend(orbit)
            return affected
        return []

class GenericSolver(ISolver):
    """通用求解器，适用于任何群模型"""
    
    def solve(self, start_state: CubeState, target_state: CubeState, 
              generators: List[GroupAction]) -> List[GroupAction]:
        """使用BFS寻找最短解法"""
        if start_state == target_state:
            return []
        
        queue = deque([(start_state, [])])
        visited = {start_state.encode()}
        
        while queue:
            current_state, path = queue.popleft()
            
            # 尝试所有可能的生成元操作
            for action in generators:
                new_state = action.apply(current_state)
                
                if new_state.encode() not in visited:
                    new_path = path + [action]
                    
                    if new_state == target_state:
                        return new_path
                    
                    visited.add(new_state.encode())
                    queue.append((new_state, new_path))
        
        return []  # 无解

class GenericScrambler:
    """通用打乱器，适用于任何群模型"""
    
    def __init__(self, generators: List[GroupAction]):
        self.generators = generators
        self.min_scramble_moves = 20
        self.max_scramble_moves = 30
    
    def generate_scramble(self, current_state: CubeState, avoid_undo: bool = True) -> List[GroupAction]:
        """生成随机打乱序列"""
        num_moves = random.randint(self.min_scramble_moves, self.max_scramble_moves)
        
        scramble_actions = []
        last_action = None
        
        for _ in range(num_moves):
            action = self._get_random_action(last_action, avoid_undo)
            scramble_actions.append(action)
            last_action = action
        
        return scramble_actions
    
    def _get_random_action(self, last_action: Optional[GroupAction], avoid_undo: bool) -> GroupAction:
        """获取随机操作，避免立即撤销上一步操作"""
        while True:
            action = random.choice(self.generators)
            
            # 如果不需避免撤销，或者这不是对上一步的撤销操作
            if not avoid_undo or not self._is_undo_action(action, last_action):
                return action
    
    def _is_undo_action(self, current_action: GroupAction, last_action: Optional[GroupAction]) -> bool:
        """检查当前操作是否撤销了上一步操作"""
        if last_action is None:
            return False
        
        # 这里需要根据具体操作类型判断是否为撤销
        # 对于简单的旋转操作，可以检查是否为相反方向
        # 对于复杂操作，可能需要更复杂的逻辑
        return False  # 简化实现


class SagePuzzleModel(GroupModel):
    """从 sage 计算结果加载的拼图模型 — 坐标预计算为像素，完全使用内置画法"""

    def __init__(self, json_data, scale=250, offset=(300, 300)):
        self.scale = scale
        self.offset = offset
        self._model_name = "Sage Puzzle"

        generators_raw = json_data["generators"]
        coords_raw = json_data["coords"]
        circles_raw = json_data["circles"]

        sage_coords = {int(k): complex(v[0], v[1]) for k, v in coords_raw.items()}

        # 预计算像素坐标
        ox, oy = offset
        self._pixel_coords = {}
        for lbl, c in sage_coords.items():
            self._pixel_coords[lbl] = complex(ox + c.real * scale, oy - c.imag * scale)

        all_labels = sorted(sage_coords.keys())
        self.positions = [Position(lbl, 0) for lbl in all_labels]

        self.disk_configs = []
        self.disk_centers = []

        for idx in range(len(generators_raw)):
            cycles = generators_raw[idx]

            circle_data = circles_raw.get(str(idx))
            if circle_data:
                cx, cy = circle_data["center"]
                center_norm = complex(cx, cy)
            else:
                center_norm = complex(0, 0)

            orbit_list = []
            for cycle in cycles:
                if len(cycle) > 1:
                    # 按顺时针几何顺序重排：幅角降序
                    cycle_sorted = sorted(cycle, key=lambda lbl: -math.atan2(
                        sage_coords[lbl].imag - center_norm.imag,
                        sage_coords[lbl].real - center_norm.real
                    ))
                    orbit_list.append([Position(lbl, 0) for lbl in cycle_sorted])
                else:
                    orbit_list.append([Position(lbl, 0) for lbl in cycle])
            self.disk_configs.append(orbit_list)

            if circle_data:
                center_pixel = complex(ox + center_norm.real * scale, oy - center_norm.imag * scale)
                self.disk_centers.append(center_pixel)
            else:
                self.disk_centers.append(complex(ox, oy))

        self.generators = []
        for idx in range(len(self.disk_configs)):
            center = self.disk_centers[idx] if idx < len(self.disk_centers) else complex(300, 300)
            self.generators.append(DiskRotation(f"disk_{idx}_cw", idx, 1, center))
            self.generators.append(DiskRotation(f"disk_{idx}_ccw", idx, -1, center))

    def get_positions(self) -> List[Position]:
        return self.positions

    def get_generators(self) -> List[GroupAction]:
        return self.generators

    def get_initial_state(self) -> CubeState:
        return CubeState({pos: i for i, pos in enumerate(self.positions)})

    def is_solved_state(self, state: CubeState) -> bool:
        return state == self.get_initial_state()

    def get_model_name(self) -> str:
        return self._model_name

    def set_model_name(self, name: str):
        self._model_name = name

    def display_position(self, label: int) -> complex:
        """O(1) 像素坐标查找"""
        return self._pixel_coords[label]


def load_sage_puzzle(json_path, scale=250, offset=(300, 300)):
    """从 JSON 文件加载 sage 拼图数据"""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return SagePuzzleModel(data, scale, offset)
