"""
Input: StockAnalysisState (所有已完成的分析报告)
Output: StockAnalysisState (bull_case已填充)
Pos: 看多研究员Agent，纯LLM驱动，从乐观角度寻找买入理由
一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
"""
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class BullResearcherAgent:
    """看多研究员Agent"""

    name = "看多研究员"

    @staticmethod
    def analyze(state: Dict[str, Any]) -> Dict[str, Any]:
        """从乐观角度分析，寻找买入理由"""
        from app.core.ai_client import get_ai_client, chat_completion, get_completion_content

        stock_code = state['stock_code']

        try:
            client = get_ai_client()
            if not client:
                # State定义bull_case为str类型，不能返回dict
                return {
                    'bull_case': 'AI客户端不可用，无法生成看多分析',
                    'execution_log': state.get('execution_log', []) + [
                        {'agent': '看多研究员', 'status': 'failed', 'error': 'AI客户端不可用'}
                    ]
                }

            # 汇总所有已有分析报告
            reports_summary = _compile_reports(state)

            prompt = f"""你是一位资深的看多研究员（Bull Researcher）。你的职责是从所有可用分析数据中，
找出最有力的买入理由和上涨催化剂。

注意：你必须站在乐观角度分析，但分析必须基于事实和数据，不能凭空编造。

股票代码: {stock_code}

已有分析报告汇总:
{reports_summary}

请从以下维度给出看多论据：

1. **核心买入逻辑**（最强的2-3个理由）
2. **技术面利好信号**（趋势、形态、指标支撑）
3. **基本面优势**（财务亮点、成长性、护城河）
4. **资金面支撑**（主力动向、资金流入信号）
5. **舆情/催化剂**（利好消息、政策支持、行业趋势）
6. **目标预期**（合理的上涨空间估算）
7. **看多置信度**（高/中/低，并说明理由）

请确保分析有据可依，标注数据来源。"""

            response, error = chat_completion(
                client,
                [{"role": "user", "content": prompt}],
                temperature=0.8,
                max_tokens=1500
            )

            if error:
                # State定义bull_case为str类型，不能返回dict
                return {
                    'bull_case': f'AI分析失败: {error}',
                    'execution_log': state.get('execution_log', []) + [
                        {'agent': '看多研究员', 'status': 'failed', 'error': str(error)}
                    ]
                }

            bull_analysis = get_completion_content(response)

            # State定义bull_case为str类型，直接返回分析文本
            # 如果需要保留perspective元数据，以前缀方式嵌入
            bull_case_text = bull_analysis if isinstance(bull_analysis, str) else json.dumps(bull_analysis, ensure_ascii=False)

            return {
                'bull_case': bull_case_text,
                'execution_log': state.get('execution_log', []) + [
                    {'agent': '看多研究员', 'status': 'success'}
                ]
            }

        except Exception as e:
            logger.error(f"看多分析失败: {e}")
            # State定义bull_case为str类型，不能返回dict
            return {
                'bull_case': f'看多分析失败: {str(e)}',
                'execution_log': state.get('execution_log', []) + [
                    {'agent': '看多研究员', 'status': 'failed', 'error': str(e)}
                ]
            }


def _compile_reports(state: Dict[str, Any]) -> str:
    """汇总所有已完成的分析报告"""
    sections = []

    if state.get('technical_report'):
        sections.append(f"【技术分析】\n{_format_report(state['technical_report'])}")

    if state.get('fundamental_report'):
        sections.append(f"【基本面分析】\n{_format_report(state['fundamental_report'])}")

    if state.get('capital_flow_report'):
        sections.append(f"【资金流向】\n{_format_report(state['capital_flow_report'])}")

    if state.get('sentiment_report'):
        sections.append(f"【舆情分析】\n{_format_report(state['sentiment_report'])}")

    return "\n\n".join(sections) if sections else "暂无前置分析报告"


def _format_report(report: Any) -> str:
    """格式化单个报告为可读文本"""
    if report is None:
        return "无数据"
    if isinstance(report, dict):
        # 优先返回AI评论
        if 'ai_commentary' in report:
            return report['ai_commentary'][:800]
        # 否则格式化关键字段
        lines = []
        for k, v in list(report.items())[:12]:
            if k not in ('flow_data', 'news_items', 'financial_indicators'):
                lines.append(f"  {k}: {v}")
        return "\n".join(lines) if lines else "空报告"
    return str(report)[:500]
