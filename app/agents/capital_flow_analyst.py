"""
Input: StockAnalysisState (stock_code, market_type)
Output: StockAnalysisState (capital_flow_report已填充)
Pos: 资金流向分析Agent，包装CapitalFlowAnalyzer提供LLM增强分析
一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
"""
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class CapitalFlowAnalystAgent:
    """资金流向分析师Agent"""

    name = "资金流向分析师"

    @staticmethod
    def analyze(state: Dict[str, Any]) -> Dict[str, Any]:
        """执行资金流向分析"""
        from app.analysis.capital_flow_analyzer import CapitalFlowAnalyzer
        from app.core.ai_client import get_ai_client, chat_completion, get_completion_content

        stock_code = state['stock_code']
        market_type = state.get('market_type', 'A')

        try:
            analyzer = CapitalFlowAnalyzer()

            # akshare资金流向接口需要 'sh'/'sz' 格式的market参数
            # 将 'A' 转换为基于股票代码的市场标识
            flow_market = market_type
            if market_type == 'A':
                flow_market = 'sh' if stock_code.startswith('6') else 'sz'

            # 获取个股资金流向
            flow_data = analyzer.get_individual_fund_flow(stock_code, flow_market)

            # 计算资金流向评分
            score_result = analyzer.calculate_capital_flow_score(stock_code, flow_market)

            result = {
                'flow_data': flow_data,
                'score': score_result
            }

            # 检查是否有错误
            if isinstance(score_result, dict) and 'error' in score_result:
                return {
                    'capital_flow_report': {'error': score_result['error']},
                    'execution_log': state.get('execution_log', []) + [
                        {'agent': '资金流向分析师', 'status': 'failed', 'error': score_result['error']}
                    ]
                }

            # 用AI增强分析
            client = get_ai_client()
            if client:
                flow_summary = _format_flow_data(flow_data)
                score_summary = _format_score_data(score_result)

                prompt = f"""你是资深资金分析师。基于以下资金流向数据，给出专业分析：

股票代码: {stock_code}

资金流向数据:
{flow_summary}

资金评分:
{score_summary}

请给出：
1. 主力资金动向判断（净流入/流出趋势、力度）
2. 资金意图解读（建仓/出货/洗盘/试探）
3. 大单与散户行为对比分析
4. 短期资金面展望与操作建议"""

                response, error = chat_completion(
                    client,
                    [{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=1200
                )
                if not error:
                    result['ai_commentary'] = get_completion_content(response)

            return {
                'capital_flow_report': result,
                'execution_log': state.get('execution_log', []) + [
                    {'agent': '资金流向分析师', 'status': 'success'}
                ]
            }

        except Exception as e:
            logger.error(f"资金流向分析失败: {e}")
            return {
                'capital_flow_report': {'error': str(e)},
                'execution_log': state.get('execution_log', []) + [
                    {'agent': '资金流向分析师', 'status': 'failed', 'error': str(e)}
                ]
            }


def _format_flow_data(data: Any) -> str:
    """格式化资金流向数据为可读字符串"""
    if data is None:
        return "无数据"
    if isinstance(data, dict):
        lines = []
        for k, v in list(data.items())[:15]:
            lines.append(f"  {k}: {v}")
        return "\n".join(lines) if lines else "空数据"
    if isinstance(data, list):
        return str(data[:5])
    return str(data)[:500]


def _format_score_data(data: Any) -> str:
    """格式化评分数据为可读字符串"""
    if data is None:
        return "无数据"
    if isinstance(data, dict):
        lines = []
        for k, v in list(data.items())[:10]:
            lines.append(f"  {k}: {v}")
        return "\n".join(lines) if lines else "空数据"
    return str(data)[:300]
