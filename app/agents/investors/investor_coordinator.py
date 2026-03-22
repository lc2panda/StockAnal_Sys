"""
Input: StockAnalysisState (所有已完成的分析报告)
Output: Dict 包含 investor_consensus 字段 (综合建议 + 投票结果)
Pos: app/agents/investors/investor_coordinator.py - 投资者人格协调器

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
"""
import logging
import time
from typing import Dict, Any, List
from collections import Counter

logger = logging.getLogger(__name__)


class InvestorCoordinator:
    """投资者人格协调器

    职责：
    - 依次调用4个投资者人格Agent（巴菲特、芒格、林奇、达摩达兰）
    - 汇总各人格的建议
    - 投票机制：多数一致则高信心，分歧则中等信心
    - 返回综合建议
    """

    name = "投资者人格协调器"

    @staticmethod
    def analyze(state: Dict[str, Any]) -> Dict[str, Any]:
        """协调所有投资者人格Agent并汇总建议"""
        from .buffett import BuffettAgent
        from .munger import MungerAgent
        from .lynch import LynchAgent
        from .damodaran import DamodaranAgent

        stock_code = state.get('stock_code', '未知')
        results = {}
        execution_log = list(state.get('execution_log', []))

        # 依次调用4个投资者人格Agent
        agents = [
            ('buffett', BuffettAgent),
            ('munger', MungerAgent),
            ('lynch', LynchAgent),
            ('damodaran', DamodaranAgent),
        ]

        for key, agent_cls in agents:
            try:
                logger.info(f"[投资者协调器] 调用 {agent_cls.name}...")
                result = agent_cls.analyze(state)
                investor_key = f'investor_{key}'

                if investor_key in result:
                    results[investor_key] = result[investor_key]

                # 合并execution_log
                if 'execution_log' in result:
                    for entry in result['execution_log']:
                        if entry not in execution_log:
                            execution_log.append(entry)

            except Exception as e:
                logger.error(f"[投资者协调器] {agent_cls.name} 执行异常: {e}")
                results[f'investor_{key}'] = {
                    'analyst': agent_cls.name,
                    'recommendation': 'HOLD',
                    'confidence': '低',
                    'reasoning': f'执行异常: {str(e)}',
                    'error': str(e)
                }
                execution_log.append({
                    'agent': agent_cls.name,
                    'status': 'failed',
                    'error': str(e)
                })

        # 汇总投票
        consensus = _build_consensus(results, stock_code)

        execution_log.append({
            'agent': '投资者人格协调器',
            'status': 'success',
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        })

        # 将各投资者结果打包到State定义的investor_opinions字段中
        # State不包含investor_buffett等独立字段，需统一归入investor_opinions
        investor_opinions = {
            'buffett': results.get('investor_buffett', {}),
            'munger': results.get('investor_munger', {}),
            'lynch': results.get('investor_lynch', {}),
            'damodaran': results.get('investor_damodaran', {}),
        }

        return {
            'investor_opinions': investor_opinions,
            'investor_consensus': consensus,
            'execution_log': execution_log
        }


def _build_consensus(results: Dict[str, Any], stock_code: str) -> Dict[str, Any]:
    """基于投票机制构建投资者共识"""
    recommendations: List[str] = []
    individual_views: List[Dict[str, Any]] = []

    for key, result in results.items():
        if not key.startswith('investor_'):
            continue

        rec = result.get('recommendation', 'HOLD').upper()
        # 标准化推荐
        if rec not in ('BUY', 'SELL', 'HOLD'):
            rec = 'HOLD'

        recommendations.append(rec)
        individual_views.append({
            'analyst': result.get('analyst', key),
            'recommendation': rec,
            'confidence': result.get('confidence', '中'),
            'reasoning': result.get('reasoning', '无')[:200]
        })

    if not recommendations:
        return {
            'stock_code': stock_code,
            'final_recommendation': 'HOLD',
            'consensus_confidence': '低',
            'consensus_reasoning': '无有效投资者分析结果',
            'vote_summary': {},
            'individual_views': [],
            'agreement_level': '无数据'
        }

    # 投票计数
    vote_count = Counter(recommendations)
    total_votes = len(recommendations)
    majority_rec, majority_count = vote_count.most_common(1)[0]

    # 共识度判定
    agreement_ratio = majority_count / total_votes

    if agreement_ratio >= 0.75:
        consensus_confidence = '高'
        agreement_level = '强共识'
    elif agreement_ratio >= 0.5:
        consensus_confidence = '中'
        agreement_level = '多数一致'
    else:
        consensus_confidence = '低'
        agreement_level = '意见分歧'

    # 构建共识推理
    consensus_reasoning = _build_consensus_reasoning(
        individual_views, majority_rec, agreement_level, vote_count
    )

    return {
        'stock_code': stock_code,
        'final_recommendation': majority_rec,
        'consensus_confidence': consensus_confidence,
        'consensus_reasoning': consensus_reasoning,
        'vote_summary': dict(vote_count),
        'total_votes': total_votes,
        'agreement_ratio': round(agreement_ratio, 2),
        'agreement_level': agreement_level,
        'individual_views': individual_views
    }


def _build_consensus_reasoning(
    views: List[Dict[str, Any]],
    majority_rec: str,
    agreement_level: str,
    vote_count: Counter
) -> str:
    """构建共识推理文本"""
    rec_cn = {'BUY': '买入', 'SELL': '卖出', 'HOLD': '持有'}

    lines = [f"投资者人格共识分析（{agreement_level}）："]
    lines.append(f"多数建议：{rec_cn.get(majority_rec, majority_rec)}")
    lines.append(f"投票分布：{', '.join(f'{rec_cn.get(r, r)}={c}票' for r, c in vote_count.items())}")
    lines.append("")

    for view in views:
        rec_text = rec_cn.get(view['recommendation'], view['recommendation'])
        lines.append(
            f"- {view['analyst']}：{rec_text}（信心{view['confidence']}）"
            f"—— {view['reasoning'][:100]}"
        )

    return "\n".join(lines)
