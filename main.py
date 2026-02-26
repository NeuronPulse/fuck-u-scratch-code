#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#by hypixice
#website: https://www.hypixice.top


import zipfile
import json
import sys
import os
import re
import argparse
from collections import defaultdict

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.align import Align
except ImportError:
    sys.exit(1)

BANNER = r"""
[bold red]  __             _                      __              _      [/bold red]
[bold red] / _|           | |                    / _|            | |[/bold red]
[bold red]| |_ _   _  ___ | | __  ______  _   _ | |_  ___  ___   | |     [/bold red]
[bold yellow]|  _| | | |/ __|| |/ / |______|| | | ||  _|/ __|/ _ \  | |[/bold yellow]
[bold yellow]| | | |_| | (__ |   <          | |_| || | | (__| (_) | | |____ [/bold yellow]
[bold cyan]|_|  \__,_|\___||_|\_\          \__,_||_|  \___|\___/  |______|[/bold cyan]
                                                               
      [bold magenta]TurboWarp / Scratch 屎山代码检测器 (NextGen)[/bold magenta]
      [bold magenta]By: HYPIXICE[/bold magenta]
      [italic]"让你的烂代码无处遁形！(分数越高越烂)"[/italic]
"""

class Sb3Evaluator:
    def __init__(self, file_path, lenient=False):
        self.file_path = file_path
        self.lenient = lenient  # 宽松模式
        self.project_data = None
        self.issues =[]
        self.score = 0  # 屎山指数（从 0 开始，越高越烂）
        self.signatures = defaultdict(list)
        
    def add_issue(self, sprite, dimension, reason, deduction, suggestion):
        # 如果是宽松模式，适当减轻“惩罚”
        if self.lenient:
            deduction = max(1, int(deduction * 0.6))

        self.issues.append({
            'sprite': sprite,
            'dimension': dimension,
            'reason': reason,
            'deduction': deduction,
            'suggestion': suggestion
        })
        self.score += deduction # 分数累加

    def load(self):
        with zipfile.ZipFile(self.file_path, 'r') as z:
            with z.open('project.json') as f:
                self.project_data = json.loads(f.read().decode('utf-8'))

    def count_blocks(self, start_id, blocks):
        """计算以 start_id 为起点的整个脚本的积木总数"""
        if not start_id or start_id not in blocks:
            return 0
        count = 0
        stack = [start_id]
        while stack:
            curr = stack.pop()
            b = blocks.get(curr)
            if not b or type(b) is not dict:
                continue
            count += 1
            if b.get('next'):
                stack.append(b['next'])
            for input_name, input_val in b.get('inputs', {}).items():
                if 'SUBSTACK' in input_name and isinstance(input_val, list) and len(input_val) >= 2:
                    if isinstance(input_val[1], str):
                        stack.append(input_val[1])
        return count

    def get_nesting_depth(self, block_id, blocks):
        """计算某个积木在控制流中的最大嵌套深度"""
        depth = 0
        curr = block_id
        visited = set()
        while curr:
            if curr in visited:
                break
            visited.add(curr)
            b = blocks.get(curr)
            if not b or type(b) is not dict:
                break
            parent_id = b.get('parent')
            if not parent_id:
                break
            parent_block = blocks.get(parent_id)
            if not parent_block or type(parent_block) is not dict:
                break
            
            is_substack_child = False
            for input_name, input_val in parent_block.get('inputs', {}).items():
                if isinstance(input_val, list) and len(input_val) >= 2:
                    if isinstance(input_val[1], str) and input_val[1] == curr:
                        if 'SUBSTACK' in input_name:
                            is_substack_child = True
                            break
            if is_substack_child:
                depth += 1
                
            curr = parent_id
        return depth

    def get_script_signature(self, start_id, blocks):
        """生成脚本的签名（用于检测重复CV代码）"""
        sig =[]
        def traverse(curr_id):
            if not curr_id or curr_id not in blocks: return
            b = blocks[curr_id]
            if type(b) is not dict: return
            sig.append(b.get('opcode', ''))
            for sub in ['SUBSTACK', 'SUBSTACK2']:
                if sub in b.get('inputs', {}):
                    val = b['inputs'][sub]
                    if isinstance(val, list) and len(val) >= 2 and isinstance(val[1], str):
                        sig.append("{")
                        traverse(val[1])
                        sig.append("}")
            if b.get('next'):
                 traverse(b['next'])
        traverse(start_id)
        return ",".join(sig)

    def evaluate(self):
        # --- 宽松模式阈值调整 ---
        MAX_VARS = 50 if self.lenient else 30
        MAX_BLOCKS_NO_COMMENT = 100 if self.lenient else 50
        DEPTH_RED = 8 if self.lenient else 6
        DEPTH_YELLOW = 6 if self.lenient else 5
        DEPTH_CYAN = 5 if self.lenient else 4
        LEN_RED = 200 if self.lenient else 100
        LEN_YELLOW = 100 if self.lenient else 50
        LEN_CYAN = 60 if self.lenient else 30

        targets = self.project_data.get('targets',[])
        
        for target in targets:
            name = target.get('name', 'Unknown')
            is_stage = target.get('isStage', False)
            blocks = target.get('blocks', {})
            variables = target.get('variables', {})
            lists = target.get('lists', {})
            broadcasts = target.get('broadcasts', {})
            comments = target.get('comments', {})
            
            # 1. 命名规范检查
            if re.match(r'^(Sprite|角色|背景|backdrop)\s*\d*$', name, re.IGNORECASE):
                self.add_issue(name, "命名规范", f"使用了默认的{'背景' if is_stage else '角色'}名称 '{name}'", 2, "请使用有业务意义的名字，如 'Player'")
                
            for _, var_info in variables.items():
                var_name = var_info[0]
                if re.match(r'^(my variable|variable|变量|未命名)\s*\d*$', var_name, re.IGNORECASE):
                    self.add_issue(name, "命名规范", f"使用了无意义的变量名 '{var_name}'", 1, "变量名应具备描述性")
                    
            for _, list_info in lists.items():
                list_name = list_info[0]
                if re.match(r'^(list|列表|未命名)\s*\d*$', list_name, re.IGNORECASE):
                    self.add_issue(name, "命名规范", f"使用了无意义的列表名 '{list_name}'", 1, "列表名应具备描述性")
                    
            for _, b_name in broadcasts.items():
                if re.match(r'^(message|消息|未命名)\s*\d*$', b_name, re.IGNORECASE):
                    self.add_issue(name, "命名规范", f"使用了无意义的广播消息名 '{b_name}'", 2, "广播名应清晰表明意图")
            
            if len(variables) > MAX_VARS:
                self.add_issue(name, "代码结构", f"单角色包含过多变量 ({len(variables)} 个)", 5, "状态管理过于庞大，建议使用列表或拆分角色")

            # 2. 全局遍历检查 (复杂度、空控制块、注释)
            max_depth = 0
            total_blocks = sum(1 for b in blocks.values() if type(b) is dict)
            
            if total_blocks > MAX_BLOCKS_NO_COMMENT and len(comments) == 0:
                self.add_issue(name, "代码注释", f"角色体量较大({total_blocks}个积木)，但没有任何注释", 5, "请在复杂逻辑旁右键添加注释")

            top_levels =[bid for bid, b in blocks.items() if type(b) is dict and b.get('topLevel')]
            
            for bid, b in blocks.items():
                if type(b) is not dict: continue
                opcode = b.get('opcode', '')
                
                # 自定义积木命名
                if opcode == 'procedures_prototype':
                    proccode = b.get('mutation', {}).get('proccode', '')
                    if re.match(r'^(block name|积木名称|block|未命名|my block)\s*\d*$', proccode, re.IGNORECASE):
                        self.add_issue(name, "命名规范", f"使用了无意义的自定义积木名 '{proccode}'", 2, "自定义积木应具备描述性")
                        
                # 嵌套深度 (复杂度)
                depth = self.get_nesting_depth(bid, blocks)
                if depth > max_depth: max_depth = depth
                    
                # 空控制块
                c_blocks =["control_if", "control_if_else", "control_repeat", "control_repeat_until", "control_forever"]
                if opcode in c_blocks:
                    if "SUBSTACK" not in b.get('inputs', {}) and "SUBSTACK2" not in b.get('inputs', {}):
                        self.add_issue(name, "代码结构", f"发现空的控制流积木 ({opcode})", 2, "填充逻辑或果断删除")
            
            if max_depth >= DEPTH_RED:
                self.add_issue(name, "逻辑复杂度", f"代码嵌套深度极高 (最大 {max_depth} 层)", 15, "典型的“箭头形代码”！请抽出自定义积木")
            elif max_depth >= DEPTH_YELLOW:
                self.add_issue(name, "逻辑复杂度", f"代码嵌套较深 (最大 {max_depth} 层)", 8, "建议将内部的如果或循环提取出来")
            elif max_depth >= DEPTH_CYAN:
                self.add_issue(name, "逻辑复杂度", f"代码嵌套略深 (最大 {max_depth} 层)", 3, "可以考虑平铺逻辑或提炼积木")

            # 3. TopLevel 检查 (体积、死代码、重复度)
            for start_id in top_levels:
                b = blocks[start_id]
                opcode = b.get('opcode', '')
                length = self.count_blocks(start_id, blocks)
                
                is_hat = opcode.startswith('event_') or opcode.startswith('procedures_definition') or opcode in['control_start_as_clone', 'videoSensing_whenMotionGreaterThan']
                if not is_hat:
                    if length == 1:
                        self.add_issue(name, "代码结构", f"发现未使用的孤立积木 ({opcode})", 1, "删除无用的孤立积木")
                    else:
                        self.add_issue(name, "代码结构", f"发现未连接事件的死代码 (包含 {length} 个积木)", 3, "如果不使用请果断删除")
                
                if length > LEN_RED:
                    self.add_issue(name, "代码体积", f"存在极度臃肿的“上帝脚本” ({length} 个积木)", 20, "典型的屎山标志！请将其拆分为多个自定义积木")
                elif length > LEN_YELLOW:
                    self.add_issue(name, "代码体积", f"存在过长脚本 ({length} 个积木)", 10, "建议抽离部分逻辑到自定义积木")
                elif length > LEN_CYAN:
                    self.add_issue(name, "代码体积", f"存在较长脚本 ({length} 个积木)", 3, "考虑优化或拆分")
                    
                if length >= 6:
                    sig = self.get_script_signature(start_id, blocks)
                    self.signatures[sig].append((name, opcode))

        # 4. 重复度汇总 (Duplication)
        for sig, locations in self.signatures.items():
            if len(locations) > 1:
                sprites_involved = list(set([loc[0] for loc in locations]))
                deduction = min(20, (len(locations) - 1) * 5)
                # 名称拼接加上省略号防止过长
                target_str = ", ".join(sprites_involved)
                if len(target_str) > 20: target_str = target_str[:17] + "..."
                
                self.add_issue(
                    target_str, "代码重复度", 
                    f"发现 {len(locations)} 处完全相同的长代码片段(CV大法)", 
                    deduction, "提取公共函数，或使用克隆体复用逻辑"
                )

def print_summary(console, evaluator):
    score = evaluator.score
    
    if score == 0:
        color = "cyan"
        rating = "A+ (完美纯净)"
        comment = "太感人了！这段代码纯洁得像一朵白莲花，没有任何坏味道！建议直接入选 Scratch 教科书！"
    elif score <= 20:
        color = "green"
        rating = "A (优秀)"
        comment = "相当不错！代码结构整洁，只有一些无关痛痒的小毛病。继续保持！"
    elif score <= 60:
        color = "yellow"
        rating = "B (良好/屎山雏形)"
        comment = "还能看，但也仅限还能看。屎山的雏形已经显现，如果现在重构还来得及！"
    elif score <= 150:
        color = "magenta"
        rating = "C (警告/深陷屎山)"
        comment = "生化武器预警！代码里充斥着重复、超长上帝脚本和神秘命名，接盘侠看了想跑路！"
    else:
        color = "red"
        rating = "D (不可救药/电子越野)"
        comment = "天哪...这代码写得就像是在键盘上撒了一把米让鸡跑出来的一样。请立即佩戴防毒面具，建议重写跑路！"

    summary_text = f"屎山指数 (Shit-Gas Index): [bold red]{score}[/bold red] 点\n"
    summary_text += f"当前评级: [bold {color}]{rating}[/bold {color}]\n\n"
    summary_text += f"[italic]{comment}[/italic]"
    
    panel = Panel(
        Align.center(summary_text), 
        title="[bold]✨ 最终诊断结果[/bold]", 
        border_style=color,
        padding=(1, 2)
    )
    console.print(panel)

def main():
    parser = argparse.ArgumentParser(description="TurboWarp/Scratch 屎山代码检测器")
    parser.add_argument("file", help="要评判的 .sb3 / .pmp 文件路径")
    parser.add_argument("--top", type=int, default=20, help="最多显示的扣分项数量 (默认: 20)")
    parser.add_argument("--name-width", type=int, default=18, help="指定第一列(角色名)的列宽，防止被截断 (默认: 18)")
    parser.add_argument("--lenient", action="store_true", help="开启【宽松模式】：降低检测标准并减少加分，适合老旧大项目")
    
    args = parser.parse_args()

    console = Console()
    console.print(BANNER)
    
    if not os.path.exists(args.file):
        console.print(f"[bold red]❌ 错误: 文件 '{args.file}' 不存在！[/bold red]")
        sys.exit(1)
        
    if args.lenient:
        console.print("[bold yellow]⚠️ 已开启宽松模式 (Lenient Mode): 评分标准已放宽！[/bold yellow]\n")

    evaluator = Sb3Evaluator(args.file, lenient=args.lenient)
    
    with console.status("[bold green]正在提取并分析项目数据，让坏味道无处遁形...", spinner="aesthetic"):
        try:
            evaluator.load()
        except Exception as e:
            console.print(f"[bold red]❌ 解析项目失败，确认这是一个有效的 .sb3 文件吗？\n错误详情: {e}[/bold red]")
            sys.exit(1)
            
        evaluator.evaluate()
        
    console.print()
    table = Table(title=f"💩 屎山检测报告: [yellow]{os.path.basename(args.file)}[/yellow]", show_header=True, header_style="bold magenta", expand=True)
    
    # 动态设定列宽，并且设置 overflow="fold" 会让长名字自动换行而不是被直接吃掉
    table.add_column("角色/位置", style="dim", width=args.name_width, overflow="fold")
    table.add_column("维度", justify="center", style="cyan", width=12)
    table.add_column("病因", style="yellow")
    table.add_column("屎指数", justify="right", style="red bold", width=8)
    table.add_column("重构建议", style="green")

    # 按照加分（屎指数）倒序排列
    sorted_issues = sorted(evaluator.issues, key=lambda x: x['deduction'], reverse=True)
    
    if len(sorted_issues) == 0:
        table.add_row("-", "完美", "没有任何问题！", "0", "继续保持卓越！")
    else:
        for i, issue in enumerate(sorted_issues[:args.top]):
            table.add_row(
                issue['sprite'],
                issue['dimension'],
                issue['reason'],
                f"+{issue['deduction']}",  # 改成加号
                issue['suggestion']
            )

    console.print(table)
    
    if len(sorted_issues) > args.top:
        console.print(f"[dim italic]... 还有 {len(sorted_issues) - args.top} 个隐患未显示，使用 --top 参数查看更多。[/dim italic]\n")
    else:
        console.print()
        
    print_summary(console, evaluator)

if __name__ == "__main__":
    main()