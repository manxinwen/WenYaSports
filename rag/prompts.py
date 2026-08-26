"""RAG Prompt 模板。

模板要求 LLM 严格基于「用户画像 + 近期训练状态 + 检索知识」回答，
知识不足时明确说明并提供通用建议，避免幻觉。
"""

KNOWLEDGE_QA_PROMPT = """你是一位专业的运动科学教练，正在为一位用户提供个性化的训练咨询。

请严格按照以下信息回答问题，**不要编造**检索知识中不存在的内容。

## 用户画像
{user_profile}

## 近期训练状态
{training_status}

## 检索到的知识片段
{knowledge}

## 用户问题
{question}

要求：
1. 优先结合用户画像、近期训练状态和检索知识给出个性化、可执行的建议。
2. 每条引用的知识请标注来源（如：根据《{source_note}》）。
3. 如果检索知识不足以回答，请明确说明"该问题超出当前知识库范围"，并基于运动科学常识给出通用建议。
4. 用简洁、专业的中文回答。"""


def format_user_profile(profile: dict) -> str:
    """将用户画像 dict 格式化为易读文本。"""
    if not profile:
        return "（暂无画像数据）"
    lines = [f"- {key}: {value}" for key, value in profile.items()]
    return "\n".join(lines)


def format_training_status(status: dict) -> str:
    """将近期训练状态 dict 格式化为易读文本。"""
    if not status:
        return "（暂无训练状态数据）"
    lines = [f"- {key}: {value}" for key, value in status.items()]
    return "\n".join(lines)


def format_knowledge(passages: list) -> tuple[str, str]:
    """格式化检索片段，返回 (知识文本, 来源说明)。

    :param passages: 每个元素为 ``{"content": ..., "source": ...}``。
    :return: ``(knowledge_text, source_note)``。
    """
    if not passages:
        return "（未检索到相关知识）", "当前知识库"
    lines = []
    sources = set()
    for i, passage in enumerate(passages, start=1):
        source = passage.get("source") or "未知来源"
        sources.add(source)
        lines.append(f"[片段{i}｜来源：{source}]\n{passage['content']}")
    return "\n\n".join(lines), "、".join(sorted(sources))
