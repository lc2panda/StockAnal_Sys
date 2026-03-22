"""
Input: 用户请求(stock_code, market_type, research_depth, selected_analysts)
Output: 完整的StockAnalysisState(含所有分析结果和最终决策)
Pos: app/agents/coordinator.py - Agent系统的核心编排器，基于LangGraph图编排

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
"""
import logging
from typing import Dict, Any, List, Optional
from langgraph.graph import StateGraph, END
from app.agents.state import StockAnalysisState

logger = logging.getLogger(__name__)


def build_analysis_graph(
    research_depth: int = 3,
    selected_analysts: Optional[List[str]] = None
):
    """
    构建分析图，根据研究深度动态决定节点。

    深度级别:
      1 - 技术分析 + 决策
      2 - + 基本面 + 资金流
      3 - + 情绪分析
      4 - + 多空辩论
      5 - + 风险评估
    """
    from app.agents.technical_analyst import TechnicalAnalystAgent
    from app.agents.fundamental_analyst import FundamentalAnalystAgent
    from app.agents.capital_flow_analyst import CapitalFlowAnalystAgent
    from app.agents.sentiment_analyst import SentimentAnalystAgent
    from app.agents.bull_researcher import BullResearcherAgent
    from app.agents.bear_researcher import BearResearcherAgent
    from app.agents.risk_manager import RiskManagerAgent
    from app.agents.decision_maker import DecisionMakerAgent

    graph = StateGraph(StockAnalysisState)

    # 技术分析始终包含，作为入口点
    graph.add_node("technical", TechnicalAnalystAgent.analyze)
    graph.set_entry_point("technical")
    last_node = "technical"

    if research_depth >= 2:
        graph.add_node("fundamental", FundamentalAnalystAgent.analyze)
        graph.add_node("capital_flow", CapitalFlowAnalystAgent.analyze)
        graph.add_edge("technical", "fundamental")
        graph.add_edge("fundamental", "capital_flow")
        last_node = "capital_flow"

    if research_depth >= 3:
        graph.add_node("sentiment", SentimentAnalystAgent.analyze)
        graph.add_edge(last_node, "sentiment")
        last_node = "sentiment"

    if research_depth >= 4:
        graph.add_node("bull", BullResearcherAgent.analyze)
        graph.add_node("bear", BearResearcherAgent.analyze)
        graph.add_edge(last_node, "bull")
        graph.add_edge("bull", "bear")
        last_node = "bear"

    if research_depth >= 5:
        graph.add_node("risk", RiskManagerAgent.analyze)
        graph.add_edge(last_node, "risk")
        last_node = "risk"

        # 投资者人格分析（可选，在风险评估后）
        try:
            from app.agents.investors.investor_coordinator import InvestorCoordinator
            graph.add_node("investors", InvestorCoordinator.analyze)
            graph.add_edge("risk", "investors")
            last_node = "investors"
        except ImportError:
            pass  # 投资者模块未安装

    # 决策节点始终在最后
    graph.add_node("decision", DecisionMakerAgent.analyze)
    graph.add_edge(last_node, "decision")

    # 反思节点（决策后执行，从历史中学习优化）
    try:
        from app.agents.reflection import ReflectionAgent
        graph.add_node("reflection", ReflectionAgent.reflect)
        graph.add_edge("decision", "reflection")
        graph.add_edge("reflection", END)
    except ImportError:
        graph.add_edge("decision", END)

    return graph.compile()


def run_agent_analysis(
    stock_code: str,
    market_type: str = 'A',
    research_depth: int = 3,
    selected_analysts: Optional[List[str]] = None,
    progress_callback=None
) -> Dict[str, Any]:
    """
    执行Agent分析的主入口。

    Args:
        stock_code: 股票代码
        market_type: 市场类型 (A/HK/US)
        research_depth: 研究深度 1-5
        selected_analysts: 可选的指定分析师列表
        progress_callback: 进度回调函数

    Returns:
        完整的分析状态字典
    """
    logger.info(f"启动Agent分析: {stock_code}, 深度={research_depth}")

    # 构建图
    graph = build_analysis_graph(research_depth, selected_analysts)

    # 初始状态
    initial_state = {
        'stock_code': stock_code,
        'market_type': market_type,
        'research_depth': research_depth,
        'messages': [],
        'technical_report': None,
        'fundamental_report': None,
        'capital_flow_report': None,
        'sentiment_report': None,
        'bull_case': None,
        'bear_case': None,
        'debate_summary': None,
        'investor_opinions': None,
        'investor_consensus': None,
        'risk_assessment': None,
        'final_decision': None,
        'execution_log': [],
        'progress': 0.0,
        'errors': [],
    }

    # 注入自适应策略
    try:
        from app.agents.strategy_evolver import get_strategy_evolver
        strategy_prompt = get_strategy_evolver().get_strategy_prompt(stock_code)
        if strategy_prompt:
            initial_state['messages'] = [{"role": "system", "content": strategy_prompt}]
    except Exception:
        pass

    # 发布分析开始事件
    try:
        from app.core.event_bus import get_event_bus, EVENT_ANALYSIS_STARTED
        get_event_bus().publish(EVENT_ANALYSIS_STARTED, {'stock_code': stock_code})
    except Exception:
        pass

    try:
        result = graph.invoke(initial_state)
        logger.info(f"Agent分析完成: {stock_code}")

        # 保存到Agent记忆 + 发布完成事件
        try:
            from app.core.agent_memory import get_agent_memory
            from app.core.event_bus import get_event_bus, EVENT_ANALYSIS_COMPLETED
            get_agent_memory().save_analysis(stock_code, result)
            get_event_bus().publish(EVENT_ANALYSIS_COMPLETED, {
                'stock_code': stock_code,
                'decision': result.get('final_decision'),
            })
        except Exception:
            pass

        # 触发策略演化（基于历史反思）
        try:
            from app.agents.strategy_evolver import get_strategy_evolver
            from app.agents.reflection import ReflectionAgent
            evolver = get_strategy_evolver()
            past_reflections = ReflectionAgent.get_past_reflections(stock_code, limit=5)
            if len(past_reflections) >= 3:
                evolver.evolve_strategy(stock_code, past_reflections)
        except Exception:
            pass

        return result
    except Exception as e:
        logger.error(f"Agent分析失败: {e}")
        return {
            **initial_state,
            'errors': initial_state['errors'] + [str(e)],
            'final_decision': {
                'action': 'HOLD',
                'confidence': 0.0,
                'reasoning': f'分析过程出错: {str(e)}'
            }
        }


class CoordinatorAgent:
    """
    协调器Agent类封装，供外部模块导入使用。
    提供与其他Agent一致的类接口。
    """

    name = "协调器"

    @staticmethod
    def run(
        stock_code: str,
        market_type: str = 'A',
        research_depth: int = 3,
        selected_analysts: Optional[List[str]] = None,
        progress_callback=None
    ) -> Dict[str, Any]:
        """执行完整的Agent分析流程"""
        return run_agent_analysis(
            stock_code=stock_code,
            market_type=market_type,
            research_depth=research_depth,
            selected_analysts=selected_analysts,
            progress_callback=progress_callback
        )
