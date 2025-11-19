#!/usr/bin/env python3
"""
提取 inspect_ai 日志文件中每个成功任务的完整 CoT (Chain of Thought)。

这个脚本可以从日志文件中提取：
- 完整的对话历史（user 和 assistant 的所有消息）
- 推理过程（reasoning tokens）- 如果可用且未加密
- 最终代码答案
- 任务元数据和成功状态
"""

import json
from pathlib import Path
from typing import Dict, List, Any
import argparse


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
                    if len(reasoning_text) > 500:
                        print(f"  - {reasoning_text[:500]}...")
                        print(f"    (truncated, total length: {len(reasoning_text)})")
                    else:
                        print(f"  - {reasoning_text}")
        
        # 打印文本内容
        if turn.get('text'):
            text = turn['text']
            print("\n[TEXT]:")
            if len(text) > 1000 and not show_full_answer:
                print(text[:1000])
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


def main():
    parser = argparse.ArgumentParser(
        description='提取 inspect_ai 日志中的 CoT 信息'
    )
    parser.add_argument(
        'log_file',
        type=str,
        help='日志文件路径（JSON 格式）'
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
    
    args = parser.parse_args()
    
    log_file = Path(args.log_file)
    if not log_file.exists():
        print(f"错误: 文件不存在: {log_file}")
        return
    
    # 提取 CoT
    print(f"正在从 {log_file} 提取 CoT...")
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