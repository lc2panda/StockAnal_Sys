"""
Input: Agent分析结果、历史决策、语义查询文本
Output: 记忆存取接口、语义相似历史检索结果
Pos: app/core/agent_memory.py - Agent长期记忆、经验学习与语义检索

一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
"""
import os
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

MEMORY_DIR = os.path.join(os.path.dirname(__file__), '../../data/agent_memory')


class AgentMemory:
    """Agent记忆系统 - 存储分析历史和决策经验"""

    def __init__(self):
        os.makedirs(MEMORY_DIR, exist_ok=True)

    def save_analysis(self, stock_code: str, analysis_result: Dict[str, Any]) -> None:
        """保存分析结果到记忆"""
        filename = os.path.join(MEMORY_DIR, f"{stock_code}_history.json")
        history = self._load_file(filename)

        entry = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'decision': analysis_result.get('final_decision', {}),
            'technical_score': self._extract_score(analysis_result.get('technical_report', {})),
            'risk_level': analysis_result.get('risk_assessment', {}).get('risk_level', 'unknown'),
            'investor_consensus': analysis_result.get('investor_consensus', ''),
        }

        history.append(entry)

        # 保留最近50条记录
        if len(history) > 50:
            history = history[-50:]

        self._save_file(filename, history)

    def get_history(self, stock_code: str, limit: int = 10) -> List[Dict]:
        """获取股票的分析历史"""
        filename = os.path.join(MEMORY_DIR, f"{stock_code}_history.json")
        history = self._load_file(filename)
        return history[-limit:]

    def search_similar(self, stock_code: str, query: str, top_k: int = 3) -> List[Dict]:
        """语义搜索相似的历史分析记录（基于TF-IDF + 余弦相似度）"""
        history = self.get_history(stock_code, limit=50)
        if not history or not query:
            return []

        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity

            # 构建历史文本
            texts = []
            for h in history:
                d = h.get('decision', {})
                text = f"{d.get('action', '')} {d.get('reasoning', '')} {h.get('risk_level', '')}"
                texts.append(text)

            if not texts:
                return []

            # TF-IDF向量化
            vectorizer = TfidfVectorizer(max_features=500)
            all_texts = texts + [query]
            tfidf_matrix = vectorizer.fit_transform(all_texts)

            # 计算查询与历史的相似度
            query_vec = tfidf_matrix[-1:]
            history_vecs = tfidf_matrix[:-1]
            similarities = cosine_similarity(query_vec, history_vecs)[0]

            # 按相似度排序返回top_k
            top_indices = similarities.argsort()[-top_k:][::-1]
            results = []
            for idx in top_indices:
                if similarities[idx] > 0.1:  # 最低相似度阈值
                    results.append({
                        **history[idx],
                        'similarity': float(similarities[idx])
                    })
            return results
        except ImportError:
            logger.warning("scikit-learn未安装，语义搜索不可用")
            return []
        except Exception as e:
            logger.warning(f"语义搜索失败: {e}")
            return []

    def get_semantic_context(self, stock_code: str, current_analysis: str, top_k: int = 3) -> str:
        """生成语义相关的历史上下文（供Agent参考）"""
        similar = self.search_similar(stock_code, current_analysis, top_k)
        if not similar:
            return ""

        lines = ["=== 语义相关历史分析 ==="]
        for s in similar:
            d = s.get('decision', {})
            lines.append(
                f"[{s.get('timestamp', '')}] (相似度:{s.get('similarity', 0):.2f}) "
                f"{d.get('action', 'N/A')} - {d.get('reasoning', '')[:100]}"
            )
        return '\n'.join(lines)

    def get_context_prompt(self, stock_code: str) -> str:
        """生成历史上下文提示（供Agent使用）"""
        history = self.get_history(stock_code, limit=5)
        if not history:
            return ""

        lines = ["=== 历史分析记录 ==="]
        for h in history:
            decision = h.get('decision', {})
            lines.append(
                f"[{h.get('timestamp', '')}] "
                f"决策: {decision.get('action', 'N/A')}, "
                f"信心度: {decision.get('confidence', 'N/A')}, "
                f"风险: {h.get('risk_level', 'N/A')}"
            )
        return '\n'.join(lines)

    def _extract_score(self, report: Dict) -> Optional[float]:
        if isinstance(report, dict):
            return report.get('score', report.get('total_score', None))
        return None

    def _load_file(self, filename: str) -> list:
        try:
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"加载记忆文件失败: {e}")
        return []

    def _save_file(self, filename: str, data: list) -> None:
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存记忆文件失败: {e}")


# 全局单例
_memory = None


def get_agent_memory() -> AgentMemory:
    global _memory
    if _memory is None:
        _memory = AgentMemory()
    return _memory
