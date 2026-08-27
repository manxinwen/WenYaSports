"""AutoClassifyAgent：智能文档分类 Agent。

基于关键词匹配 + 内容特征分析，自动识别知识文档所属类别。
支持不确定性量化：当分类置信度低于阈值时，返回候选供管理员确认。

分类体系:
  - strength:       力量训练
  - endurance:      耐力训练
  - nutrition:      运动营养
  - physiology:     运动生理学
  - technique:      运动技术
  - sports_science: 运动科学（综合）
  - general:        综合/未分类
"""

import logging
import re
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# 分类关键词库（权重 = 出现频率越高分越高）
CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "strength": [
        "力量", "strength", "power", "爆发力", "最大力量",
        "负重", "杠铃", "哑铃", "深蹲", "硬拉", "卧推",
        "hypertrophy", "肌肉肥大", "力量训练", "抗阻训练",
        "爆发力训练", "速度力量", "耐力力量",
    ],
    "endurance": [
        "耐力", "endurance", "aerobic", "anaerobic",
        "有氧", "无氧", "VO2max", "最大摄氧量",
        "长距离", "马拉松", "铁三", "triathlon",
        "配速", "pace", "乳酸阈值", "lactate threshold",
        "持续训练", "间歇训练", "interval",
    ],
    "nutrition": [
        "营养", "nutrition", "diet", "protein", "蛋白质",
        "碳水", "carbohydrate", "脂肪", "fat",
        "热量", "calorie", "kcal", "宏量", "微量",
        "维生素", "vitamin", "矿物质", "mineral",
        "补水", "hydration", "电解质", "electrolyte",
        "补剂", "supplement", "肌酸", "creatine",
        "赛前餐", "赛后恢复", "recovery meal",
    ],
    "physiology": [
        "生理", "physiology", "心率", "heart rate",
        "血氧", "VO2", "血乳酸", "blood lactate",
        "肌纤维", "muscle fiber", "快肌", "慢肌",
        "神经系统", "nervous system", "神经肌肉",
        "内分泌", "endocrine", "激素", "hormone",
        "睾酮", "testosterone", "皮质醇", "cortisol",
        "线粒体", "mitochondria", "能量代谢",
    ],
    "technique": [
        "技术", "technique", "动作", "form",
        "姿势", "posture", "步态", "gait",
        "跑步姿势", "running form", "着地", "stride",
        "周期化", "periodization", "训练周期",
        "热身", "warm-up", "拉伸", "stretching",
        "动作模式", "movement pattern", "生物力学", "biomechanics",
    ],
    "sports_science": [
        "运动科学", "sports science", "科研", "research",
        "研究", "study", "实验", "experiment",
        "数据分析", "data analysis", "统计", "statistics",
        "训练监控", "monitoring", "负荷", "load",
        "周期化训练", "periodization", "tapering", "减量",
        "过度训练", "overtraining", "应激", "stress",
    ],
}

# 分类中文名映射
CATEGORY_NAMES: Dict[str, str] = {
    "strength": "力量训练",
    "endurance": "耐力训练",
    "nutrition": "运动营养",
    "physiology": "运动生理学",
    "technique": "运动技术",
    "sports_science": "运动科学",
    "general": "综合",
}

# 分类排序（按展示优先级）
CATEGORY_ORDER: List[str] = [
    "strength", "endurance", "nutrition",
    "physiology", "technique", "sports_science", "general",
]


class AutoClassifyAgent:
    """智能文档分类 Agent。

    使用三级策略：
    1. 关键词频率匹配（快速、零依赖）
    2. 关键词权重加权（考虑术语重要性）
    3. 置信度评估（输出不确定性）
    """

    def __init__(self):
        self.categories = list(CATEGORY_KEYWORDS.keys())
        self._min_confidence_threshold = 0.3  # 低于此值需人工确认

    def classify(
        self,
        text: str,
        filename: str = "",
    ) -> Dict:
        """对文档进行分类。

        Args:
            text: 文档全文（或前 N 段文本）
            filename: 文件名（辅助识别）

        Returns:
            {
                "primary_category": str,       # 主分类
                "confidence": float,           # 置信度 [0,1]
                "candidates": [                # 候选分类排序
                    {"category": str, "score": float, "confidence": float}
                ],
                "needs_review": bool,          # 是否需要人工确认
                "reasoning": str,              # 分类理由
            }
        """
        # 1. 从文本中提取特征
        features = self._extract_features(text, filename)

        # 2. 计算每个分类的得分
        scores = {}
        for category in self.categories:
            score = self._compute_category_score(category, features, text)
            scores[category] = score

        # 3. 排序
        sorted_categories = sorted(
            scores.items(), key=lambda x: x[1], reverse=True
        )

        # 4. 归一化得分
        max_score = sorted_categories[0][1] if sorted_categories else 1.0
        candidates = []
        for cat, score in sorted_categories:
            normalized = score / max(max_score, 1.0)
            candidates.append({
                "category": cat,
                "category_name": CATEGORY_NAMES.get(cat, cat),
                "score": round(score, 4),
                "confidence": round(normalized, 4),
            })

        primary = sorted_categories[0][0]
        primary_confidence = candidates[0]["confidence"]

        # 5. 如果最高分太低，归入 general
        if max_score < 0.15:
            primary = "general"
            primary_confidence = 0.0

        # 6. 判断是否需要人工审核
        needs_review = primary_confidence < self._min_confidence_threshold

        # 7. 生成理由
        reasoning = self._build_reasoning(primary, primary_confidence, candidates[:3])

        return {
            "primary_category": primary,
            "primary_category_name": CATEGORY_NAMES.get(primary, primary),
            "confidence": primary_confidence,
            "candidates": candidates,
            "needs_review": needs_review,
            "reasoning": reasoning,
            "features_found": len(features),
        }

    def _extract_features(
        self, text: str, filename: str
    ) -> Dict[str, int]:
        """从文本中提取关键词频率特征。"""
        features = {}
        text_lower = text.lower()
        filename_lower = filename.lower()

        for category, keywords in CATEGORY_KEYWORDS.items():
            for kw in keywords:
                kw_lower = kw.lower()
                # 在全文中计数
                count = len(re.findall(re.escape(kw_lower), text_lower))
                # 在文件名中额外加权
                if kw_lower in filename_lower:
                    count += 3
                if count > 0:
                    features[kw] = count
        return features

    def _compute_category_score(
        self,
        category: str,
        features: Dict[str, int],
        text: str,
    ) -> float:
        """计算分类得分。

        得分 = 匹配关键词加权分 / 总关键词数
        至少匹配 1 个关键词才能有分数。
        """
        keywords = CATEGORY_KEYWORDS[category]
        score = 0.0
        matched = 0

        for kw in keywords:
            count = features.get(kw, 0)
            if count > 0:
                weight = min(len(kw) / 3.0, 2.0)
                score += count * weight
                matched += 1

        if matched == 0:
            return 0.0

        # 归一化：按关键词数量 + 匹配数
        max_possible = len(keywords) * 2.0
        score = min(score / max(max_possible, 1.0), 1.0)

        # 基础分：匹配到关键词就给基础分
        base_score = min(matched / max(len(keywords), 1), 0.6)

        return round(max(score, base_score), 4)

    def _build_reasoning(
        self,
        primary: str,
        confidence: float,
        top_candidates: List[Dict],
    ) -> str:
        """生成人类可读的分类理由。"""
        if confidence >= 0.7:
            level = "高置信度"
        elif confidence >= 0.4:
            level = "中等置信度"
        else:
            level = "低置信度，建议人工确认"

        primary_name = CATEGORY_NAMES.get(primary, primary)
        alt_names = [
            f"{CATEGORY_NAMES.get(c['category'], c['category'])}(置信度 {c['confidence']:.0%})"
            for c in top_candidates[1:3]
        ]

        parts = [f"{level}分类为「{primary_name}」"]
        if alt_names:
            parts.append(f"备选: {', '.join(alt_names)}")

        return "；".join(parts)

    def get_supported_categories(self) -> List[Dict]:
        """返回支持的分类列表。"""
        return [
            {"id": cat, "name": CATEGORY_NAMES.get(cat, cat)}
            for cat in CATEGORY_ORDER
        ]
