#!/usr/bin/env python3
"""
提取 inspect_ai 日志文件中每个成功任务的完整 CoT (Chain of Thought)。

这个脚本可以从日志文件中提取：
- 完整的对话历史（user 和 assistant 的所有消息）
- 推理过程（reasoning tokens）- 如果可用且未加密
- 最终代码答案
- 任务元数据和成功状态
python notebooks/extract_cot.py --latest
"""

import json
from pathlib import Path
from typing import Dict, List, Any
import argparse
from datetime import datetime


def extract_sample_cot(sample: Dict[str, Any]) -> Dict[str, Any]:
    """从单个 sample 中提取 CoT 信息"""
    
    sample_id = sample.get('id', 'unknown')
    messages = sample.get('messages', [])
    scores = sample.get('scores', {})
    
    # 提取对话历史
    conversation = []
    for msg in messages:
        role = msg.get('role', 'unknown')
        content = msg.get('content', '')
        
        # 如果 content 是列表（包含 reasoning 和 text）
        if isinstance(content, list):
            reasoning_parts = []
            text_parts = []
            
            for item in content:
                if isinstance(item, dict):
                    if item.get('type') == 'reasoning':
                        # 检查 reasoning 是否被加密
                        if item.get('redacted', False):
                            reasoning_parts.append({
                                'type': 'reasoning',
                                'status': 'REDACTED (encrypted)',
                                'signature': item.get('signature', 'N/A')
                            })
                        else:
                            reasoning_parts.append({
                                'type': 'reasoning',
                                'content': item.get('reasoning', '')
                            })
                    elif item.get('type') == 'text':
                        text_parts.append(item.get('text', ''))
            
            conversation.append({
                'role': role,
                'reasoning': reasoning_parts if reasoning_parts else None,
                'text': '\n'.join(text_parts) if text_parts else None
            })
        elif isinstance(content, str):
            conversation.append({
                'role': role,
                'text': content
            })
    
    # 提取评分信息
    success = False
    final_answer = None
    metadata = {}
    
    for scorer_name, scorer_data in scores.items():
        if isinstance(scorer_data, dict):
            value = scorer_data.get('value')
            answer = scorer_data.get('answer')
            scorer_metadata = scorer_data.get('metadata', {})
            
            # 判断是否成功
            if isinstance(value, (int, float)):
                success = value > 0
            elif value == 'C':  # 有些 scorer 用字母表示
                success = True
            
            if answer:
                final_answer = answer
            
            metadata.update(scorer_metadata)
    
    return {
        'sample_id': sample_id,
        'success': success,
        'conversation': conversation,
        'final_answer': final_answer,
        'metadata': metadata
    }


def extract_cot_from_log(log_file: Path) -> List[Dict[str, Any]]:
    """从日志文件中提取所有 sample 的 CoT"""
    
    with open(log_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    samples = data.get('samples', [])
    
    results = []
    for sample in samples:
        cot_data = extract_sample_cot(sample)
        results.append(cot_data)
    
    return results


def print_cot(cot_data: Dict[str, Any], show_full_answer: bool = False):
    """打印 CoT 信息"""
    
    print(f"\n{'='*80}")
    print(f"Sample ID: {cot_data['sample_id']}")
    print(f"Success: {cot_data['success']}")
    print(f"{'='*80}\n")
    
    # 打印对话历史
    for i, turn in enumerate(cot_data['conversation'], 1):
        role = turn['role']
        print(f"\n[Turn {i}] Role: {role.upper()}")
        print("-" * 80)
        
        # 如果有 reasoning
        if turn.get('reasoning'):
            print("\n[REASONING]:")
            for r in turn['reasoning']:
                if r.get('status') == 'REDACTED (encrypted)':
                    print(f"  - {r['status']}")
                    print(f"    Signature: {r.get('signature', 'N/A')}")
                else:
                    reasoning_text = r.get('content', '')
                    if len(reasoning_text) > 5000:
                        print(f"  - {reasoning_text[:5000]}...")
                        print(f"    (truncated, total length: {len(reasoning_text)})")
                    else:
                        print(f"  - {reasoning_text}")
        
        # 打印文本内容
        if turn.get('text'):
            text = turn['text']
            print("\n[TEXT]:")
            if len(text) > 50000 and not show_full_answer:
                print(text[:50000])
                print(f"\n... (truncated, total length: {len(text)} chars)")
            else:
                print(text)
    
    # 打印元数据
    if cot_data['metadata']:
        print(f"\n{'='*80}")
        print("METADATA:")
        print("-" * 80)
        for key, value in cot_data['metadata'].items():
            if key == 'attempt_history':
                print(f"  {key}: {len(value)} attempts")
            elif isinstance(value, str) and len(value) > 200:
                print(f"  {key}: (long string, {len(value)} chars)")
            else:
                print(f"  {key}: {value}")


def find_log_files(log_dir: Path = None) -> List[Path]:
    """查找所有日志文件"""
    if log_dir is None:
        # 默认日志目录
        script_dir = Path(__file__).parent
        log_dir = script_dir / 'logs' / 'implivecodebench'
    
    if not log_dir.exists():
        return []
    
    # 查找所有 JSON 文件，排除 logs.json 和 eval-set.json
    log_files = []
    for f in log_dir.glob('*.json'):
        if f.name not in ['logs.json', 'eval-set.json']:
            log_files.append(f)
    
    # 按修改时间排序（最新的在前）
    log_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return log_files


def select_log_file(log_files: List[Path]) -> Path:
    """让用户选择一个日志文件"""
    if not log_files:
        print("错误: 未找到日志文件")
        return None
    
    print("\n可用的日志文件:")
    print("=" * 80)
    for i, log_file in enumerate(log_files, 1):
        # 获取文件大小和修改时间
        size_mb = log_file.stat().st_size / (1024 * 1024)
        mtime = log_file.stat().st_mtime
        mtime_str = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
        
        print(f"{i}. {log_file.name}")
        print(f"   大小: {size_mb:.2f} MB | 修改时间: {mtime_str}")
    
    print(f"\n0. 使用最新的日志文件 ({log_files[0].name})")
    print("=" * 80)
    
    while True:
        try:
            choice = input("\n请选择日志文件编号 (0 或 1-{}，直接回车使用最新): ".format(len(log_files)))
            if choice == '':
                choice = '0'
            choice = int(choice)
            if choice == 0:
                return log_files[0]
            elif 1 <= choice <= len(log_files):
                return log_files[choice - 1]
            else:
                print(f"请输入 0 到 {len(log_files)} 之间的数字")
        except ValueError:
            print("请输入有效的数字")
        except KeyboardInterrupt:
            print("\n已取消")
            return None


def main():
    parser = argparse.ArgumentParser(
        description='提取 inspect_ai 日志中的 CoT 信息'
    )
    parser.add_argument(
        'log_file',
        type=str,
        nargs='?',  # 改为可选参数
        help='日志文件路径（JSON 格式）。如果不提供，将自动搜索并让你选择'
    )
    parser.add_argument(
        '--success-only',
        action='store_true',
        help='只显示成功的任务'
    )
    parser.add_argument(
        '--full-answer',
        action='store_true',
        help='显示完整的答案（不截断）'
    )
    parser.add_argument(
        '--output',
        type=str,
        help='输出到 JSON 文件'
    )
    parser.add_argument(
        '--latest',
        action='store_true',
        help='自动使用最新的日志文件（不提示选择）'
    )
    parser.add_argument(
        '--log-dir',
        type=str,
        help='指定日志目录（默认为 notebooks/logs/implivecodebench/）'
    )
    
    args = parser.parse_args()
    
    # 确定日志文件
    if args.log_file:
        # 用户指定了文件
        log_file = Path(args.log_file)
        if not log_file.exists():
            print(f"错误: 文件不存在: {log_file}")
            return
    else:
        # 自动搜索日志文件
        log_dir = Path(args.log_dir) if args.log_dir else None
        log_files = find_log_files(log_dir)
        
        if not log_files:
            print("错误: 未找到日志文件")
            if log_dir:
                print(f"搜索目录: {log_dir}")
            else:
                script_dir = Path(__file__).parent
                default_dir = script_dir / 'logs' / 'implivecodebench'
                print(f"搜索目录: {default_dir}")
            return
        
        if args.latest:
            # 自动使用最新的日志
            log_file = log_files[0]
            print(f"使用最新的日志文件: {log_file.name}")
        else:
            # 让用户选择
            log_file = select_log_file(log_files)
            if log_file is None:
                return
    
    # 提取 CoT
    print(f"\n正在从 {log_file.name} 提取 CoT...")
    cot_results = extract_cot_from_log(log_file)
    
    # 过滤成功的任务
    if args.success_only:
        cot_results = [r for r in cot_results if r['success']]
        print(f"找到 {len(cot_results)} 个成功的任务")
    else:
        success_count = sum(1 for r in cot_results if r['success'])
        print(f"找到 {len(cot_results)} 个任务，其中 {success_count} 个成功")
    
    # 打印结果
    for cot_data in cot_results:
        print_cot(cot_data, show_full_answer=args.full_answer)
    
    # 保存到文件
    if args.output:
        output_path = Path(args.output)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(cot_results, f, indent=2, ensure_ascii=False)
        print(f"\n结果已保存到: {output_path}")


if __name__ == '__main__':
    main()