import os
import pygame
from typing import List, Dict, Optional
from collections import deque
from models import Move, CubeState, Position, AnimationState, GameConfig, BidirectionalBFSSolver, Scrambler
from models import GroupModel, M12Model, SagePuzzleModel, load_sage_puzzle, set_current_model  # 添加导入
from views import CubeView, UIView

class AnimationController:
    def __init__(self, config: GameConfig, cube_view: CubeView):
        self.config = config
        self.cube_view = cube_view
        self.animations: Dict[int, AnimationState] = {}
        self.rotation_queue = deque()
        self.is_animating = False
        self.on_animation_complete = None  # 添加回调函数
    
    def set_animation_complete_callback(self, callback):
        """设置动画完成回调"""
        self.on_animation_complete = callback

    def add_rotation(self, move: Move, current_state: CubeState, 
                    disk_configs: List[List[List[Position]]]) -> CubeState:
        """添加旋转动画"""
        # 计算新状态
        new_state = current_state.apply_move(move, disk_configs)
        
        # 为每个移动的块创建动画
        disk_centers = self.cube_view.get_disk_centers()
        center = disk_centers[move.disk_index]
        orbit_positions = disk_configs[move.disk_index]
        
        for orbit in orbit_positions:
            n = len(orbit)
            for i, pos in enumerate(orbit):
                new_index = (i + move.direction) % n
                new_pos = orbit[new_index]

                # 跳过不动点（1-轮换），无需动画
                if pos == new_pos:
                    continue

                block_id = current_state.positions[pos]
                start_pos = self.cube_view.blocks[block_id].display_position
                target_block_view = self.cube_view.blocks[block_id]
                target_pos = target_block_view.get_display_for(new_pos)
                
                animation = AnimationState(
                    block_id, start_pos, target_pos, center, self.config.animation_frames,
                    direction=move.direction
                )
                self.animations[block_id] = animation
        
        self.is_animating = True
        return new_state
    
    def update(self) -> bool:
        """更新所有动画，返回是否所有动画都完成"""
        if not self.animations:
            self.is_animating = False
            # 所有动画完成时调用回调
            if self.on_animation_complete:
                self.on_animation_complete()
            return True
        
        # 移除已完成的动画
        completed = [block_id for block_id, anim in self.animations.items() 
                    if anim.is_completed]
        for block_id in completed:
            del self.animations[block_id]
        
        # 更新显示位置
        for block_id, anim in self.animations.items():
            new_pos = anim.update()
            self.cube_view.blocks[block_id].display_position = new_pos
        
        # self.is_animating = bool(self.animations)
        # return not self.is_animating

        # 检查是否所有动画都完成
        all_completed = not self.animations
        if all_completed:
            self.is_animating = False
            # 所有动画完成时调用回调
            if self.on_animation_complete:
                self.on_animation_complete()
        
        return all_completed    
    def queue_move(self, move: Move):
        """将移动加入队列"""
        self.rotation_queue.append(move)
    
    def get_queued_move(self) -> Optional[Move]:
        """获取队列中的下一个移动"""
        if self.rotation_queue and not self.is_animating:
            return self.rotation_queue.popleft()
        return None

class InputController:
    def __init__(self):
        self.rotation_queue = deque()

    def handle_event(self, event: pygame.event.Event, disk_key_order) -> List[Move]:
        """
        处理输入事件。
        disk_key_order: 按重心 x 排序的盘索引，左→右。
        Q/S → 最左盘(disk_key_order[0]),  L/P → 最右盘(disk_key_order[-1])
        """
        moves = []

        if event.type == pygame.KEYDOWN:
            n_disks = len(disk_key_order)

            left_idx = disk_key_order[0] if n_disks > 0 else None
            right_idx = disk_key_order[-1] if n_disks > 1 else None

            # 直接旋转 — Q/S 控制最左盘, L/P 控制最右盘
            if event.key == pygame.K_q and left_idx is not None:
                moves.append(Move(left_idx, -1))
            elif event.key == pygame.K_s and left_idx is not None:
                moves.append(Move(left_idx, 1))
            elif event.key == pygame.K_l and right_idx is not None:
                moves.append(Move(right_idx, -1))
            elif event.key == pygame.K_p and right_idx is not None:
                moves.append(Move(right_idx, 1))

            # 队列旋转
            elif event.key == pygame.K_LEFT and left_idx is not None:
                self.rotation_queue.append(Move(left_idx, -1))
            elif event.key == pygame.K_RIGHT and left_idx is not None:
                self.rotation_queue.append(Move(left_idx, 1))
            elif event.key == pygame.K_UP and right_idx is not None:
                self.rotation_queue.append(Move(right_idx, -1))
            elif event.key == pygame.K_DOWN and right_idx is not None:
                self.rotation_queue.append(Move(right_idx, 1))

        return moves
    
    def has_queued_moves(self) -> bool:
        """检查是否有队列中的移动"""
        return len(self.rotation_queue) > 0
    
    def get_next_queued_move(self) -> Move:
        """获取队列中的下一个移动（不移除）"""
        if self.rotation_queue:
            return self.rotation_queue[0]
        return None
    
    def pop_queued_move(self) -> Move:
        """移除并返回队列中的下一个移动"""
        if self.rotation_queue:
            return self.rotation_queue.popleft()
        return None
    
    def get_solve_command(self, event: pygame.event.Event) -> bool:
        """检查是否触发求解命令"""
        return event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE
    
    def get_reset_command(self, event: pygame.event.Event) -> bool:
        """检查是否触发重置命令"""
        return event.type == pygame.KEYDOWN and event.key == pygame.K_r

    def get_scramble_command(self, event: pygame.event.Event) -> bool:
        """检查是否触发打乱命令"""
        return event.type == pygame.KEYDOWN and event.key == pygame.K_m

class ModelManager:
    """模型管理器 — 支持内置 + 多个 Sage 拼图模型"""

    SAGE_PREFIX = "sage_"

    def __init__(self, sage_puzzles=None, scale=250, offset=(300, 300)):
        """
        sage_puzzles: [(name, json_data), ...]  从 main.py 扫描得到的有效拼图列表
        """
        self.sage_scale = scale
        self.sage_offset = offset
        self._init_models(sage_puzzles or [])

    def _init_models(self, sage_puzzles):
        self.available_models = {
            "m12": M12Model(),
        }
        # 逐个加载有效 sage 拼图
        for name, data in sage_puzzles:
            key = self.SAGE_PREFIX + name
            try:
                model = SagePuzzleModel(data, self.sage_scale, self.sage_offset)
                model.set_model_name(name)
                self.available_models[key] = model
            except Exception as e:
                print(f"加载拼图 {name} 失败: {e}")

        self.current_model_name = list(self.available_models.keys())[0]
        self.current_model = self.available_models[self.current_model_name]
        set_current_model(self.current_model)

    def switch_model(self, model_name: str):
        """切换模型"""
        if model_name in self.available_models:
            self.current_model_name = model_name
            self.current_model = self.available_models[model_name]
            set_current_model(self.current_model)
            return True
        return False

    def get_current_model(self) -> GroupModel:
        return self.current_model

    def get_available_model_names(self) -> List[str]:
        return list(self.available_models.keys())

    def get_sage_model_names(self) -> List[str]:
        """返回所有 sage 模型的显示名称"""
        return [k for k in self.available_models if k.startswith(self.SAGE_PREFIX)]

class GameController:
    def __init__(self, config: GameConfig, sage_puzzles=None, sage_scale=250, sage_offset=(300, 300)):
        self.config = config
        self.model_manager = ModelManager(sage_puzzles, sage_scale, sage_offset)
        self._initialize_with_current_model()
    
    def _initialize_with_current_model(self):
        """使用当前模型重新初始化"""
        model = self.model_manager.get_current_model()
        
        self.cube_view = CubeView(self.config, model)
        self.ui_view = UIView(self.config, model)
        
        # 重新创建控制器
        self.animation_controller = AnimationController(self.config, self.cube_view)
        self.input_controller = InputController()
        
        # 设置动画完成回调
        self.animation_controller.set_animation_complete_callback(self._on_animation_complete)
        
        # 使用新的求解器
        self.solver = BidirectionalBFSSolver()
        
        # 重置游戏状态
        self.initial_state = model.get_initial_state()
        self.current_state = self.initial_state
        self.target_state = self.initial_state
        self.solution = []
        self.current_solution_step = 0
        self.is_solving = False
        self.is_auto_playing = False
        self.waiting_for_animation = False  # 新增：等待动画完成的标志
        
        # 获取转盘配置
        if hasattr(model, 'disk_configs'):
            self.disk_configs = model.disk_configs
        else:
            # 默认配置
            self.disk_configs = self._create_disk_configs()
        
        # 创建打乱器
        self.scrambler = Scrambler(self.disk_configs)
        self.is_scrambling = False

    def _on_animation_complete(self):
        """动画完成回调"""
        if self.waiting_for_animation:
            # 动画完成，递增步数
            self.current_solution_step += 1
            self.waiting_for_animation = False
            
            # 检查是否完成所有步骤
            if self.current_solution_step >= len(self.solution):
                self.is_auto_playing = False
            else:
                # 执行下一步
                move = self.solution[self.current_solution_step]
                self.current_state = self.animation_controller.add_rotation(
                    move, self.current_state, self.disk_configs
                )
                # 设置等待标志
                self.waiting_for_animation = True

    def _create_disk_configs(self) -> List[List[List[Position]]]:
        """创建默认转盘配置"""
        return [
            [  # 左转盘
                [Position(0, 0), Position(0, 3), Position(3, 3), Position(3, 0)],  # 外轨道
                [Position(1, 1), Position(1, 2), Position(2, 2), Position(2, 1)]   # 内轨道
            ],
            [  # 右转盘
                [Position(1, 1), Position(1, 3), Position(3, 3), Position(3, 1)],  # 外轨道
                [Position(1, 2), Position(2, 3), Position(3, 2), Position(2, 1)]   # 内轨道
            ]
        ]
    
    def switch_model(self, model_name: str):
        """切换模型并重新初始化"""
        if self.model_manager.switch_model(model_name):
            self._initialize_with_current_model()
            return True
        return False
    
    def handle_events(self):
        """处理所有事件"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False

            # 模型切换快捷键
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_1:
                    self.switch_model("m12")
                elif event.key == pygame.K_LEFTBRACKET:
                    self._cycle_model(-1)
                elif event.key == pygame.K_RIGHTBRACKET:
                    self._cycle_model(1)
                else:
                    # 数字键 2~9 映射到 sage 模型
                    sage_names = self.model_manager.get_sage_model_names()
                    for i, name in enumerate(sage_names[:8]):
                        if event.key == getattr(pygame, f"K_{i+2}"):
                            self.switch_model(name)

            # 按重心 x 排序转盘：Q/S 控制最左，L/P 控制最右
            centers = self.cube_view.get_disk_centers()
            disk_order = sorted(range(len(centers)), key=lambda i: centers[i].real)
            moves = self.input_controller.handle_event(event, disk_order)
            for move in moves:
                self.current_state = self.animation_controller.add_rotation(
                    move, self.current_state, self.disk_configs
                )
                self.is_auto_playing = False

            # 求解命令
            if self.input_controller.get_solve_command(event):
                self.solve_cube()

            # 重置命令
            if self.input_controller.get_reset_command(event):
                self.reset_cube()

            # 打乱命令
            if self.input_controller.get_scramble_command(event):
                self.scramble_cube()

        return True

    def _cycle_model(self, direction):
        """循环切换模型：direction=1 下一个, -1 上一个"""
        names = self.model_manager.get_available_model_names()
        if len(names) <= 1:
            return
        idx = names.index(self.model_manager.current_model_name)
        idx = (idx + direction) % len(names)
        self.switch_model(names[idx])
    
    def solve_cube(self):
        """开始求解魔方"""
        if not self.animation_controller.is_animating and not self.is_solving:
            self.is_solving = True
            # 在实际应用中，这里应该在单独的线程中进行求解
            self.solution = self.solver.solve(
                self.current_state, self.target_state, self.disk_configs
            )
            if self.solution:
                print(f"[{self.model_manager.current_model_name}]", end=' ')
                print(' '.join([i.sign() for i in self.solution]), end=',')
                print(''.join([i.key() for i in self.solution]), end=',')
                print(''.join([i.key(reverse=True) for i in self.solution][::-1]))
            self.is_solving = False
            self.is_auto_playing = bool(self.solution)
            self.current_solution_step = 0  # 重置为0
            self.waiting_for_animation = False  # 重置等待标志
    
    def reset_cube(self):
        """重置魔方到初始状态"""
        if not self.animation_controller.is_animating:
            self.current_state = self.initial_state
            self.solution = []
            self.is_auto_playing = False
            self.current_solution_step = 0
            
            # 重置块位置
            for block_id, block_view in self.cube_view.blocks.items():
                block_view.display_position = block_view.get_display_for(block_view.logical_position)
    
    def scramble_cube(self):
        """瞬间打乱魔方"""
        if not self.animation_controller.is_animating and not self.is_scrambling:
            self.is_scrambling = True
            
            # 生成打乱序列
            scramble_moves = self.scrambler.generate_scramble(self.current_state)
            
            # 直接应用所有打乱步骤，不显示动画
            temp_state = self.current_state
            for move in scramble_moves:
                temp_state = temp_state.apply_move(move, self.disk_configs)
            
            # 更新当前状态
            self.current_state = temp_state
            
            # 更新块的位置显示
            for block_id, block_view in self.cube_view.blocks.items():
                # 找到块的新位置
                for pos, bid in self.current_state.positions.items():
                    if bid == block_id:
                        block_view.display_position = block_view.get_display_for(pos)
                        break
            
            # 重置其他状态
            self.solution = []
            self.is_auto_playing = False
            self.current_solution_step = 0
            self.is_scrambling = False  # 瞬间完成

    def update(self):
        """更新游戏状态"""
        # 更新动画
        animation_done = self.animation_controller.update()
        
        # 自动播放解法 - 修正版本
        if self.is_auto_playing and not self.waiting_for_animation and not self.animation_controller.is_animating:
            if animation_done:
                # 动画完成后才处理下一步
                if self.current_solution_step < len(self.solution):
                    # 获取并执行当前步骤
                    move = self.solution[self.current_solution_step]
                    self.current_state = self.animation_controller.add_rotation(
                        move, self.current_state, self.disk_configs
                    )
                    # 注意：这里不递增步数，步数将在下一步动画开始时递增
                    # self.current_solution_step += 1
                    # 设置等待标志，等待动画完成
                    self.waiting_for_animation = True
                else:
                    # 所有步骤完成
                    self.is_auto_playing = False
        
        # 处理输入队列中的移动（方向键加入的队列）
        if not self.animation_controller.is_animating and not self.is_auto_playing:
            # 从输入控制器获取队列中的移动
            if self.input_controller.has_queued_moves():
                move = self.input_controller.pop_queued_move()
                # 将移动添加到动画控制器的队列中
                self.animation_controller.queue_move(move)
        
        # 处理动画控制器队列中的移动
        if not self.animation_controller.is_animating and not self.is_auto_playing:
            queued_move = self.animation_controller.get_queued_move()
            if queued_move:
                self.current_state = self.animation_controller.add_rotation(
                    queued_move, self.current_state, self.disk_configs
                )
    
    def draw(self, screen: pygame.Surface):
        """绘制游戏"""
        animation_states = self.animation_controller.animations
        self.cube_view.draw(screen, animation_states, self.current_state)
        self.ui_view.draw_controls(screen)
        self.ui_view.draw_model_info(
            screen,
            self.model_manager.get_available_model_names(),
            self.model_manager.current_model_name
        )

        if self.solution and self.current_solution_step < len(self.solution):
            self.ui_view.draw_solution(screen, self.solution, self.current_solution_step)

        if self.is_solving:
            self.ui_view.draw_solving(screen)

        if self.is_scrambling:
            self.ui_view.draw_scrambling(screen)

