"""
Input: StockAnalysisState (所有已填充的分析报告) + 语义相关历史决策
Output: StockAnalysisState (final_decision已填充, progress=100)
Pos: app/agents/decision_maker.py - 投资决策Agent，综合所有分析结果与语义历史记忆

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
"""
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class DecisionMakerAgent:
    """投资决策Agent，综合所有分析和辩论结果"""

    name = "投资决策者"

    @staticmethod
    def analyze(state: Dict[str, Any]) -> Dict[str, Any]:
        from app.core.ai_client import (
            get_ai_client, chat_completion, get_completion_content
        )

        # 收集所有分析结果构建决策prompt
        reports = []
        if state.get('technical_report') and 'error' not in state['technical_report']:
            reports.append(f"【技术面】{str(state['technical_report'])[:500]}")
        if state.get('fundamental_report') and 'error' not in state.get('fundamental_report', {}):
            reports.append(f"【基本面】{str(state['fundamental_report'])[:500]}")
        if state.get('capital_flow_report') and 'error' not in state.get('capital_flow_report', {}):
            reports.append(f"【资金面】{str(state['capital_flow_report'])[:500]}")
        if state.get('sentiment_report') and 'error' not in state.get('sentiment_report', {}):
            reports.append(f"【情绪面】{str(state['sentiment_report'])[:500]}")
        if state.get('bull_case'):
            reports.append(f"【看多论据】{state['bull_case'][:300]}")
        if state.get('bear_case'):
            reports.append(f"【看空论据】{state['bear_case'][:300]}")
        if state.get('risk_assessment') and 'error' not in state.get('risk_assessment', {}):
            reports.append(f"【风险评估】{str(state['risk_assessment'])[:300]}")

        # 注入语义相关的历史决策
        try:
            from app.core.agent_memory import get_agent_memory
            memory = get_agent_memory()
            current_summary = ' '.join([str(r)[:100] for r in reports])
            semantic_context = memory.get_semantic_context(
                state['stock_code'], current_summary, top_k=3
            )
            if semantic_context:
                reports.append(f"【历史参考】{semantic_context}")
        except Exception:
            pass

        reports_text = chr(10).join(reports)
        prompt = f"""你是一位资深投资组合经理。基于以下多维度分析结果，做出最终投资决策。

股票代码: {state['stock_code']}

{reports_text}

请以JSON格式输出决策（注意：仅输出JSON，不要其他文本）：
{{
    "action": "BUY/SELL/HOLD",
    "confidence": 0.0-1.0,
    "reasoning": "综合决策理由",
    "price_targets": {{
        "support": "支撑价位",
        "resistance": "阻力价位",
        "target": "目标价位"
    }},
    "risk_level": "低/中/高",
    "position_suggestion": "建议仓位比例"
}}"""

        client = get_ai_client()
        if not client:
            return {
                'final_decision': {
                    'action': 'HOLD',
                    'confidence': 0.5,
                    'reasoning': 'AI服务不可用，建议持有观望'
                },
                'progress': 100.0,
                'execution_log': state.get('execution_log', []) + [
                    {'agent': '投资决策者', 'status': 'fallback', 'reason': 'no_ai_client'}
                ]
            }

        response, error = chat_completion(
            client,
            [{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1000
        )

        if error:
            return {
                'final_decision': {
                    'action': 'HOLD',
                    'confidence': 0.3,
                    'reasoning': f'决策分析出错: {error}'
                },
                'progress': 100.0,
                'execution_log': state.get('execution_log', []) + [
                    {'agent': '投资决策者', 'status': 'failed', 'error': str(error)}
                ]
            }

        content = get_completion_content(response)
        try:
            # 尝试解析JSON，处理markdown代码块包裹
            content = content.strip()
            if content.startswith('```'):
                content = content.split('\n', 1)[1].rsplit('```', 1)[0]
            decision = json.loads(content)
        except (json.JSONDecodeError, ValueError, AttributeError):
            decision = {
                'action': 'HOLD',
                'confidence': 0.5,
                'reasoning': content or 'AI未返回有效决策'
            }

        return {
            'final_decision': decision,
            'progress': 100.0,
            'execution_log': state.get('execution_log', []) + [
                {'agent': '投资决策者', 'status': 'success'}
            ]
        }
