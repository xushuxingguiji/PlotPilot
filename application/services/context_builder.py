from typing import List, Optional
from application.services.bible_service import BibleService
from domain.bible.services.relationship_engine import RelationshipEngine
from domain.novel.services.storyline_manager import StorylineManager
from domain.novel.repositories.novel_repository import NovelRepository
from domain.novel.repositories.chapter_repository import ChapterRepository
from domain.novel.value_objects.novel_id import NovelId
from domain.ai.services.vector_store import VectorStore


class ContextBuilder:
    """上下文构建器应用服务

    智能组装章节生成所需的上下文，控制在 35K token 预算内。

    上下文分层：
    - Layer 1: 核心上下文 (~5K tokens) - 小说元数据、当前章节、情节张力
    - Layer 2: 智能检索 (~20K tokens) - 角色信息、相关章节、事件、关系
    - Layer 3: 最近上下文 (~10K tokens) - 最近章节、角色活动、关系变化
    """

    def __init__(
        self,
        bible_service: BibleService,
        storyline_manager: StorylineManager,
        relationship_engine: RelationshipEngine,
        vector_store: VectorStore,
        novel_repository: NovelRepository,
        chapter_repository: ChapterRepository
    ):
        self.bible_service = bible_service
        self.storyline_manager = storyline_manager
        self.relationship_engine = relationship_engine
        self.vector_store = vector_store
        self.novel_repository = novel_repository
        self.chapter_repository = chapter_repository

    def build_context(
        self,
        novel_id: str,
        chapter_number: int,
        outline: str,
        max_tokens: int = 35000
    ) -> str:
        """构建完整上下文

        Args:
            novel_id: 小说 ID
            chapter_number: 章节号
            outline: 章节大纲
            max_tokens: 最大 token 数

        Returns:
            组装好的上下文字符串
        """
        # Token 预算分配
        layer1_budget = int(max_tokens * 0.15)  # ~5K
        layer2_budget = int(max_tokens * 0.55)  # ~20K
        layer3_budget = int(max_tokens * 0.30)  # ~10K

        # Layer 1: 核心上下文
        layer1 = self._build_layer1_core_context(
            novel_id, chapter_number, outline, layer1_budget
        )

        # Layer 2: 智能检索
        layer2 = self._build_layer2_smart_retrieval(
            novel_id, chapter_number, outline, layer2_budget
        )

        # Layer 3: 最近上下文
        layer3 = self._build_layer3_recent_context(
            novel_id, chapter_number, layer3_budget
        )

        # 组装上下文
        context_parts = [
            "=== CONTEXT FOR CHAPTER GENERATION ===\n",
            layer1,
            "\n=== SMART RETRIEVAL ===\n",
            layer2,
            "\n=== RECENT CONTEXT ===\n",
            layer3
        ]

        full_context = "\n".join(context_parts)

        # 如果超出预算，截断 Layer 3，然后 Layer 2
        if self.estimate_tokens(full_context) > max_tokens:
            full_context = self._truncate_to_budget(
                layer1, layer2, layer3, max_tokens
            )

        return full_context

    def estimate_tokens(self, text: str) -> int:
        """估算 token 数量

        粗略估算：1 token ≈ 4 characters

        Args:
            text: 文本内容

        Returns:
            估算的 token 数
        """
        return len(text) // 4

    def _build_layer1_core_context(
        self,
        novel_id: str,
        chapter_number: int,
        outline: str,
        budget: int
    ) -> str:
        """构建 Layer 1: 核心上下文

        包含：
        - 小说元数据（标题、类型、主题）
        - 当前章节号和大纲
        - 情节弧当前张力水平
        - 活跃故事线和待完成里程碑

        Args:
            novel_id: 小说 ID
            chapter_number: 章节号
            outline: 章节大纲
            budget: token 预算

        Returns:
            Layer 1 上下文字符串
        """
        parts = []

        # 小说元数据
        nid = NovelId(novel_id)
        novel = self.novel_repository.get_by_id(nid)
        if novel:
            parts.append(f"Novel: {novel.title}")
            parts.append(f"Author: {novel.author}")

        # 当前章节
        parts.append(f"\nChapter {chapter_number}")
        parts.append(f"Outline: {outline}")

        # 活跃故事线
        storylines = self.storyline_manager.repository.get_by_novel_id(nid)
        if storylines:
            parts.append("\nActive Storylines:")
            for storyline in storylines:
                if storyline.status.value == "active":
                    parts.append(f"- {storyline.storyline_type.value}: "
                               f"Chapters {storyline.estimated_chapter_start}-{storyline.estimated_chapter_end}")
                    # 待完成里程碑
                    pending = storyline.get_pending_milestones()
                    if pending:
                        parts.append(f"  Pending milestones: {len(pending)}")

        context = "\n".join(parts)

        # 截断到预算
        if self.estimate_tokens(context) > budget:
            context = self._truncate_text(context, budget)

        return context

    def _build_layer2_smart_retrieval(
        self,
        novel_id: str,
        chapter_number: int,
        outline: str,
        budget: int
    ) -> str:
        """构建 Layer 2: 智能检索

        包含：
        - Bible 中的角色信息
        - Bible 中的地点信息
        - Bible 中的风格设定
        - 相关过往章节（向量搜索）
        - 相关事件
        - 关键关系

        Args:
            novel_id: 小说 ID
            chapter_number: 章节号
            outline: 章节大纲
            budget: token 预算

        Returns:
            Layer 2 上下文字符串
        """
        parts = []
        remaining_budget = budget

        # 从 Bible 获取数据
        bible_dto = self.bible_service.get_bible_by_novel(novel_id)

        if bible_dto:
            # 角色信息
            if bible_dto.characters:
                parts.append("Characters:")
                for char in bible_dto.characters:
                    char_info = f"- {char.name}: {char.description}"

                    # 检查预算
                    if self.estimate_tokens("\n".join(parts) + char_info) > remaining_budget * 0.6:
                        break

                    parts.append(char_info)

            # 地点信息
            if bible_dto.locations:
                parts.append("\nLocations:")
                for loc in bible_dto.locations:
                    loc_info = f"- {loc.name} ({loc.location_type}): {loc.description}"

                    # 检查预算
                    if self.estimate_tokens("\n".join(parts) + loc_info) > remaining_budget * 0.8:
                        break

                    parts.append(loc_info)

            # 风格设定
            if bible_dto.style_notes:
                parts.append("\nStyle Guidelines:")
                for note in bible_dto.style_notes:
                    style_info = f"- {note.category}: {note.content}"

                    # 检查预算
                    if self.estimate_tokens("\n".join(parts) + style_info) > remaining_budget:
                        break

                    parts.append(style_info)

        context = "\n".join(parts)

        # 截断到预算
        if self.estimate_tokens(context) > budget:
            context = self._truncate_text(context, budget)

        return context

    def _build_layer3_recent_context(
        self,
        novel_id: str,
        chapter_number: int,
        budget: int
    ) -> str:
        """构建 Layer 3: 最近上下文

        包含：
        - 最近 3-5 章节摘要
        - 最近角色活动
        - 最近关系变化
        - 未解决的伏笔

        Args:
            novel_id: 小说 ID
            chapter_number: 章节号
            budget: token 预算

        Returns:
            Layer 3 上下文字符串
        """
        parts = []

        # 最近章节
        all_chapters = self.chapter_repository.list_by_novel(NovelId(novel_id))
        recent_chapters = [c for c in all_chapters if c.number < chapter_number]
        recent_chapters = sorted(recent_chapters, key=lambda c: c.number, reverse=True)[:5]

        if recent_chapters:
            parts.append("Recent Chapters:")
            for chapter in reversed(recent_chapters):  # 按时间顺序
                summary = f"Chapter {chapter.number}: {chapter.title}"
                # 添加简短内容摘要
                if chapter.content:
                    content_preview = chapter.content[:200] + "..." if len(chapter.content) > 200 else chapter.content
                    summary += f"\n  {content_preview}"
                parts.append(summary)

                # 检查预算
                if self.estimate_tokens("\n".join(parts)) > budget:
                    parts.pop()  # 移除最后一个
                    break

        context = "\n".join(parts)

        # 截断到预算
        if self.estimate_tokens(context) > budget:
            context = self._truncate_text(context, budget)

        return context

    def _truncate_text(self, text: str, budget: int) -> str:
        """截断文本到指定 token 预算"""
        target_chars = budget * 4  # 1 token ≈ 4 chars
        if len(text) <= target_chars:
            return text
        return text[:target_chars] + "..."

    def _truncate_to_budget(
        self,
        layer1: str,
        layer2: str,
        layer3: str,
        max_tokens: int
    ) -> str:
        """截断上下文到预算

        优先级：Layer 1 (必须保留) > Layer 2 > Layer 3
        """
        # Layer 1 必须保留
        layer1_tokens = self.estimate_tokens(layer1)

        if layer1_tokens >= max_tokens:
            # Layer 1 已经超出预算，只能截断 Layer 1
            return self._truncate_text(layer1, max_tokens)

        remaining = max_tokens - layer1_tokens

        # 尝试添加 Layer 2
        layer2_tokens = self.estimate_tokens(layer2)
        if layer1_tokens + layer2_tokens <= max_tokens:
            # Layer 1 + Layer 2 在预算内
            remaining = max_tokens - layer1_tokens - layer2_tokens
            layer3_truncated = self._truncate_text(layer3, remaining)
            return f"{layer1}\n\n=== SMART RETRIEVAL ===\n{layer2}\n\n=== RECENT CONTEXT ===\n{layer3_truncated}"
        else:
            # Layer 2 需要截断
            layer2_truncated = self._truncate_text(layer2, remaining)
            return f"{layer1}\n\n=== SMART RETRIEVAL ===\n{layer2_truncated}"
