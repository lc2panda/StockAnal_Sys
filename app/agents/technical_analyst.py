"""
Input: StockAnalysisState (stock_code, market_type)
Output: StockAnalysisState (technical_report已填充)
Pos: 技术分析Agent，包装stock_analyzer提供LLM增强分析
一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
"""
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class TechnicalAnalystAgent:
    """技术分析师Agent"""

    name = "技术分析师"

    @staticmethod
    def analyze(state: Dict[str, Any]) -> Dict[str, Any]:
        """执行技术分析"""
        from app.analysis.stock_analyzer import StockAnalyzer
        from app.core.ai_client import get_ai_client, chat_completion, get_completion_content

        stock_code = state['stock_code']
        market_type = state.get('market_type', 'A')

        try:
            analyzer = StockAnalyzer()
            result = analyzer.quick_analyze_stock(stock_code, market_type)

            if 'error' in result:
                return {
                    'technical_report': {'error': result['error']},
                    'execution_log': state.get('execution_log', []) + [
                        {'agent': '技术分析师', 'status': 'failed', 'error': result['error']}
                    ]
                }

            # 用AI增强分析
            client = get_ai_client()
            if client:
                # 注入历史反思上下文
                reflection_context = ""
                try:
                    from app.agents.reflection import ReflectionAgent
                    reflection_context = ReflectionAgent.get_reflection_prompt(stock_code)
                except ImportError:
                    pass

                prompt = ""
                if reflection_context:
                    prompt = reflection_context + "\n\n"
                prompt += f"""你是资深技术分析师。基于以下技术指标数据，给出专业分析：

股票代码: {stock_code}
评分: {result.get('score', 'N/A')}/100
价格: {result.get('price', 'N/A')}
趋势: {result.get('trend', 'N/A')}
RSI: {result.get('rsi', 'N/A')}
MACD信号: {result.get('macd_signal', 'N/A')}
成交量状态: {result.get('volume_status', 'N/A')}
建议: {result.get('recommendation', 'N/A')}

请给出：1. 趋势判断 2. 关键支撑/阻力位分析 3. 短期操作建议"""

                response, error = chat_completion(
                    client,
                    [{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=1000
                )
                if not error:
                    result['ai_commentary'] = get_completion_content(response)

            return {
                'technical_report': result,
                'execution_log': state.get('execution_log', []) + [
                    {'agent': '技术分析师', 'status': 'success'}
                ]
            }

        except Exception as e:
            logger.error(f"技术分析失败: {e}")
            return {
                'technical_report': {'error': str(e)},
                'execution_log': state.get('execution_log', []) + [
                    {'agent': '技术分析师', 'status': 'failed', 'error': str(e)}
                ]
            }
