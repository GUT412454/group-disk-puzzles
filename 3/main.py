import os
import sys
import json
import pygame
from controllers import GameController
from models import GameConfig

def find_sage_puzzles(directory):
    """扫描目录下所有 .json，尝试验证是否为拼图配置，返回 [(name, data_dict), ...]"""
    puzzles = []
    if not os.path.isdir(directory):
        return puzzles
    for fname in os.listdir(directory):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(directory, fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "generators" in data and "coords" in data and "circles" in data:
                name = os.path.splitext(fname)[0]
                puzzles.append((name, data))
        except Exception:
            pass
    return puzzles

def main():
    puzzle_dir = os.path.dirname(__file__)

    # 扫描所有有效拼图配置
    sage_puzzles = find_sage_puzzles(puzzle_dir)
    if sage_puzzles:
        print(f"发现 {len(sage_puzzles)} 个拼图配置:")
        for name, _ in sage_puzzles:
            print(f"  - {name}")
    else:
        print("未发现有效的拼图配置文件")

    # 初始化Pygame
    pygame.init()

    # 创建配置
    config = GameConfig(
        animation_frames=120,
        frame_rate=120,
        width=900,
        height=600,
        block_radius=20,
        block_border=2
    )

    # 创建窗口
    screen = pygame.display.set_mode((config.width, config.height))
    title = "平面魔方转盘 - 重构版"
    pygame.display.set_caption(title)

    # 创建游戏控制器（传入所有 sage 拼图）
    sage_scale = 250
    sage_offset = (300, 300)
    game_controller = GameController(config, sage_puzzles, sage_scale, sage_offset)

    # 创建时钟
    clock = pygame.time.Clock()

    # 主循环
    running = True
    while running:
        running = game_controller.handle_events()
        game_controller.update()
        game_controller.draw(screen)
        pygame.display.flip()
        clock.tick(config.frame_rate)

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
