"""
Input: Agent分析结果 + 历史决策 + 实际市场表现
Output: 反思报告 + 策略优化建议
Pos: app/agents/reflection.py - Agent自我反思和策略优化

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
"""
import logging
import json
import os
from typing import Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)

REFLECTION_DIR = os.path.join(os.path.dirname(__file__), '../../data/agent_reflections')


class ReflectionAgent:
    """Agent反思系统 - 从历史决策中学习优化"""

    name = "反思学习Agent"

    def __init__(self):
        os.makedirs(REFLECTION_DIR, exist_ok=True)

    @staticmethod
    def reflect(state: Dict[str, Any]) -> Dict[str, Any]:
        """对本次分析进行反思"""
        from app.core.ai_client import get_ai_client, chat_completion, get_completion_content
        from app.core.agent_memory import get_agent_memory

        stock_code = state.get('stock_code', '')
        memory = get_agent_memory()
        history = memory.get_history(stock_code, limit=5)

        # 构建反思prompt
        current_decision = state.get('final_decision', {})
        if not current_decision:
            current_decision = {}

        history_text = ""
        if history:
            for h in history:
                d = h.get('decision', {})
                history_text += (
                    f"- [{h.get('timestamp', '')}] "
                    f"{d.get('action', 'N/A')} "
                    f"(信心:{d.get('confidence', 'N/A')})\n"
                )

        prompt = f"""你是一位资深投资策略反思专家。请对以下分析决策进行深度反思：

股票代码: {stock_code}
本次决策: {current_decision.get('action', 'N/A')} (信心度: {current_decision.get('confidence', 'N/A')})
决策理由: {str(current_decision.get('reasoning', 'N/A'))[:300]}

历史决策记录:
{history_text if history_text else '无历史记录'}

执行日志中的错误: {state.get('errors', [])}

请从以下维度进行反思：
1. 决策一致性：与历史决策是否矛盾？如果是，原因是什么？
2. 信息充分性：哪些维度的分析数据不足或缺失？
3. 偏差检测：是否存在锚定偏差、确认偏差或过度自信？
4. 改进建议：下次分析该股票时应该重点关注什么？
5. 策略演进：基于历史决策模式，有什么策略级别的优化建议？

请以JSON格式输出：
{{"consistency": "一致性评估", "information_gaps": ["缺失信息1", "缺失信息2"], "biases_detected": ["偏差1"], "improvements": ["改进建议1", "改进建议2"], "strategy_evolution": "策略优化建议"}}"""

        client = get_ai_client()
        if not client:
            return {
                'reflection': {'error': 'AI服务不可用'},
                'execution_log': state.get('execution_log', []) + [
                    {'agent': '反思Agent', 'status': 'skipped'}
                ]
            }

        response, error = chat_completion(
            client,
            [{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=1000
        )

        if error:
            reflection = {'error': error}
        else:
            content = get_completion_content(response)
            try:
                content = content.strip()
                if content.startswith('```'):
                    content = content.split('\n', 1)[1].rsplit('```', 1)[0]
                reflection = json.loads(content)
            except Exception:
                reflection = {'raw_reflection': content}

        # 保存反思记录
        _save_reflection(stock_code, reflection)

        return {
            'execution_log': state.get('execution_log', []) + [
                {
                    'agent': '反思Agent',
                    'status': 'success',
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
            ]
        }

    @staticmethod
    def get_past_reflections(stock_code: str, limit: int = 3) -> List[Dict]:
        """获取历史反思记录，供Agent下次分析时参考"""
        filename = os.path.join(REFLECTION_DIR, f"{stock_code}_reflections.json")
        try:
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return data[-limit:]
        except Exception as e:
            logger.warning(f"读取反思记录失败: {e}")
        return []

    @staticmethod
    def get_reflection_prompt(stock_code: str) -> str:
        """生成反思上下文提示（注入到分析Agent的prompt中）"""
        reflections = ReflectionAgent.get_past_reflections(stock_code, limit=2)
        if not reflections:
            return ""
        lines = ["=== 历史反思提醒 ==="]
        for r in reflections:
            ref = r.get('reflection', {})
            if isinstance(ref, dict) and 'improvements' in ref:
                improvements = ref['improvements'][:3]
                lines.append(
                    f"[{r.get('timestamp', '')}] "
                    f"改进建议: {', '.join(improvements)}"
                )
            if isinstance(ref, dict) and 'biases_detected' in ref:
                biases = ref['biases_detected'][:2]
                lines.append(f"  偏差警告: {', '.join(biases)}")
        return '\n'.join(lines)


def _save_reflection(stock_code: str, reflection: dict):
    """保存反思记录"""
    filename = os.path.join(REFLECTION_DIR, f"{stock_code}_reflections.json")
    try:
        os.makedirs(REFLECTION_DIR, exist_ok=True)
        data = []
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
        data.append({
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'reflection': reflection
        })
        # 保留最近20条
        if len(data) > 20:
            data = data[-20:]
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存反思记录失败: {e}")
