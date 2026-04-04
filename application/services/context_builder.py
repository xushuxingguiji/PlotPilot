import logging
from typing import List, Optional, TYPE_CHECKING, Dict, Any
from application.services.bible_service import BibleService
from domain.bible.services.relationship_engine import RelationshipEngine
from domain.novel.services.storyline_manager import StorylineManager
from domain.novel.repositories.novel_repository import NovelRepository
from domain.novel.repositories.chapter_repository import ChapterRepository
from domain.novel.repositories.plot_arc_repository import PlotArcRepository
from domain.novel.value_objects.novel_id import NovelId
from domain.ai.services.vector_store import VectorStore
from domain.ai.services.embedding_service import EmbeddingService
from application.ai.vector_retrieval_facade import VectorRetrievalFacade

if TYPE_CHECKING:
    from application.dtos.scene_director_dto import SceneDirectorAnalysis

logger = logging.getLogger(__name__)


class ContextBuilder:
    """上下文构建器应用服务

    智能组装章节生成所需的上下文，控制在 35K token 预算内。

    上下文分层：
    - Layer 1: 核心上下文 (~5K tokens) - 小说元数据、当前章节、情节张力
    - Layer 2: 智能检索 (~20K tokens) - 角色信息、相关章节、事件、关系
    - Layer 3: 最近上下文 (~10K tokens) - 最近章节、角色活动、关系变化
    """

    # Token estimation constant: 1 token ≈ 4 characters
    CHARS_PER_TOKEN = 4

    # Budget allocation ratios for context layers
    LAYER1_BUDGET_RATIO = 0.15  # ~5K tokens
    LAYER2_BUDGET_RATIO = 0.55  # ~20K tokens
    LAYER3_BUDGET_RATIO = 0.30  # ~10K tokens

    # Limits for content items
    MAX_MILESTONES_PER_STORYLINE = 4
    MAX_TIMELINE_NOTES = 16

    # Truncation thresholds for descriptions
    MILESTONE_DESC_TRUNCATE = 120
    TIMELINE_NOTE_DESC_TRUNCATE = 160
    CHAPTER_CONTENT_PREVIEW_TRUNCATE = 200

    # Budget thresholds for different content types
    # Characters get 60% of remaining budget before stopping
    CHARACTER_BUDGET_THRESHOLD = 0.6
    # Locations get 80% of remaining budget before stopping
    LOCATION_BUDGET_THRESHOLD = 0.8
    # Style notes get 100% of remaining budget before stopping
    STYLE_BUDGET_THRESHOLD = 1.0


    def __init__(
        self,
        bible_service: BibleService,
        storyline_manager: StorylineManager,
        relationship_engine: RelationshipEngine,
        vector_store: VectorStore,
        novel_repository: NovelRepository,
        chapter_repository: ChapterRepository,
        plot_arc_repository: Optional[PlotArcRepository] = None,
        embedding_service: Optional[EmbeddingService] = None,
    ):
        self.bible_service = bible_service
        self.storyline_manager = storyline_manager
        self.relationship_engine = relationship_engine
        self.vector_store = vector_store
        self.novel_repository = novel_repository
        self.chapter_repository = chapter_repository
        self.plot_arc_repository = plot_arc_repository
        self.embedding_service = embedding_service

        # 创建向量检索门面（如果两个服务都可用）
        self.vector_facade = None
        if vector_store and embedding_service:
            self.vector_facade = VectorRetrievalFacade(vector_store, embedding_service)

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
        layer1_budget = int(max_tokens * self.LAYER1_BUDGET_RATIO)
        layer2_budget = int(max_tokens * self.LAYER2_BUDGET_RATIO)
        layer3_budget = int(max_tokens * self.LAYER3_BUDGET_RATIO)

        # Layer 1: 核心上下文
        layer1 = self._build_layer1_core_context(
            novel_id, chapter_number, outline, layer1_budget
        )

        # Layer 2: 智能检索
        layer2 = self._build_layer2_smart_retrieval(
            novel_id, chapter_number, outline, layer2_budget, scene_director=None
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

    def build_structured_context(
        self,
        novel_id: str,
        chapter_number: int,
        outline: str,
        max_tokens: int = 35000,
        scene_director: Optional["SceneDirectorAnalysis"] = None,
    ) -> Dict[str, Any]:
        """构建结构化上下文，分层返回

        Args:
            novel_id: 小说 ID
            chapter_number: 章节号
            outline: 章节大纲
            max_tokens: 最大 token 数
            scene_director: 可选的场记分析，用于过滤角色和地点

        Returns:
            包含分层上下文和 token 使用情况的字典
        """
        # Token 预算分配
        layer1_budget = int(max_tokens * self.LAYER1_BUDGET_RATIO)
        layer2_budget = int(max_tokens * self.LAYER2_BUDGET_RATIO)
        layer3_budget = int(max_tokens * self.LAYER3_BUDGET_RATIO)

        # Layer 1: 核心上下文
        layer1 = self._build_layer1_core_context(
            novel_id, chapter_number, outline, layer1_budget
        )

        # Layer 2: 智能检索（可选过滤）
        layer2 = self._build_layer2_smart_retrieval(
            novel_id, chapter_number, outline, layer2_budget, scene_director=scene_director
        )

        # Layer 3: 最近上下文
        layer3 = self._build_layer3_recent_context(
            novel_id, chapter_number, layer3_budget
        )

        # 计算 token 使用情况
        layer1_tokens = self.estimate_tokens(layer1)
        layer2_tokens = self.estimate_tokens(layer2)
        layer3_tokens = self.estimate_tokens(layer3)
        total_tokens = layer1_tokens + layer2_tokens + layer3_tokens

        return {
            "layer1_text": layer1,
            "layer2_text": layer2,
            "layer3_text": layer3,
            "token_usage": {
                "layer1": layer1_tokens,
                "layer2": layer2_tokens,
                "layer3": layer3_tokens,
                "total": total_tokens,
            },
        }

    def estimate_tokens(self, text: str) -> int:
        """估算 token 数量

        粗略估算：1 token ≈ 4 characters

        Args:
            text: 文本内容

        Returns:
            估算的 token 数
        """
        return len(text) // self.CHARS_PER_TOKEN

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

        # 活跃故事线（与当前章有章节范围交集）
        storylines = self.storyline_manager.repository.get_by_novel_id(nid)
        if storylines:
            parts.append("\nActive Storylines (for this chapter):")
            for storyline in storylines:
                if storyline.status.value != "active":
                    continue
                if not (
                    storyline.estimated_chapter_start
                    <= chapter_number
                    <= storyline.estimated_chapter_end
                ):
                    continue
                parts.append(
                    f"- {storyline.storyline_type.value}: "
                    f"Chapters {storyline.estimated_chapter_start}-{storyline.estimated_chapter_end}"
                )
                pending = storyline.get_pending_milestones()
                if pending:
                    for m in pending[:self.MAX_MILESTONES_PER_STORYLINE]:
                        desc = (m.description or "")[:self.MILESTONE_DESC_TRUNCATE]
                        parts.append(
                            f"  • Milestone #{m.order} {m.title}: {desc}"
                            + ("…" if len(m.description or "") > self.MILESTONE_DESC_TRUNCATE else "")
                        )
                    if len(pending) > self.MAX_MILESTONES_PER_STORYLINE:
                        parts.append(f"  • …and {len(pending) - self.MAX_MILESTONES_PER_STORYLINE} more pending milestones")

        # 情节弧：本章期望张力与下一锚点
        if self.plot_arc_repository is not None:
            try:
                plot_arc = self.plot_arc_repository.get_by_novel_id(nid)
                if plot_arc and plot_arc.key_points:
                    tension = plot_arc.get_expected_tension(chapter_number)
                    next_point = plot_arc.get_next_plot_point(chapter_number)
                    parts.append("\nPlot arc (pacing):")
                    parts.append(f"- Expected tension for this chapter: {tension.name} ({tension.value}/4)")
                    if next_point:
                        parts.append(
                            f"- Next plot anchor: chapter {next_point.chapter_number} — {next_point.description}"
                        )
            except Exception as e:
                logger.warning(f"Failed to load plot arc: {e}")

        # Bible 时间线笔记（世界内时间参考）
        try:
            bible_dto = self.bible_service.get_bible_by_novel(novel_id)
            if bible_dto and bible_dto.timeline_notes:
                parts.append("\nBible timeline notes (story-world time, do not contradict):")
                for note in bible_dto.timeline_notes[:self.MAX_TIMELINE_NOTES]:
                    ev = (note.event or "").strip()
                    tp = (getattr(note, "time_point", None) or "").strip()
                    desc = (note.description or "").strip()
                    line = f"- {ev}" if ev else "- (event)"
                    if tp:
                        line += f" @ {tp}"
                    if desc:
                        short = desc[:self.TIMELINE_NOTE_DESC_TRUNCATE] + ("…" if len(desc) > self.TIMELINE_NOTE_DESC_TRUNCATE else "")
                        line += f": {short}"
                    parts.append(line)
                if len(bible_dto.timeline_notes) > self.MAX_TIMELINE_NOTES:
                    parts.append(f"- …and {len(bible_dto.timeline_notes) - self.MAX_TIMELINE_NOTES} more notes")
        except Exception as e:
            logger.warning(f"Failed to load Bible timeline notes: {e}")

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
        budget: int,
        scene_director: Optional["SceneDirectorAnalysis"] = None
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
            scene_director: 可选的场记分析，用于过滤角色和地点

        Returns:
            Layer 2 上下文字符串
        """
        parts = []
        running_tokens = 0
        budget_threshold_chars = budget * self.CHARS_PER_TOKEN

        # 从 Bible 获取数据
        bible_dto = self.bible_service.get_bible_by_novel(novel_id)

        if bible_dto:
            # 角色信息
            if bible_dto.characters:
                parts.append("Characters:")
                running_tokens = self.estimate_tokens("\n".join(parts))

                for char in bible_dto.characters:
                    # 如果提供了 scene_director 且指定了角色，则过滤
                    if scene_director and scene_director.characters:
                        if char.name not in scene_director.characters:
                            continue

                    char_info = f"- {char.name}: {char.description}"
                    char_tokens = self.estimate_tokens(char_info)

                    # 检查预算：字符预算阈值为 60%
                    if running_tokens + char_tokens > budget_threshold_chars * self.CHARACTER_BUDGET_THRESHOLD:
                        break

                    parts.append(char_info)
                    running_tokens += char_tokens

            # 地点信息
            if bible_dto.locations:
                parts.append("\nLocations:")
                running_tokens = self.estimate_tokens("\n".join(parts))

                for loc in bible_dto.locations:
                    # 如果提供了 scene_director 且指定了地点，则过滤
                    if scene_director and scene_director.locations:
                        if loc.name not in scene_director.locations:
                            continue

                    loc_info = f"- {loc.name} ({loc.location_type}): {loc.description}"
                    loc_tokens = self.estimate_tokens(loc_info)

                    # 检查预算：地点预算阈值为 80%
                    if running_tokens + loc_tokens > budget_threshold_chars * self.LOCATION_BUDGET_THRESHOLD:
                        break

                    parts.append(loc_info)
                    running_tokens += loc_tokens

            # 风格设定
            if bible_dto.style_notes:
                parts.append("\nStyle Guidelines:")
                running_tokens = self.estimate_tokens("\n".join(parts))

                for note in bible_dto.style_notes:
                    style_info = f"- {note.category}: {note.content}"
                    style_tokens = self.estimate_tokens(style_info)

                    # 检查预算：风格预算阈值为 100%
                    if running_tokens + style_tokens > budget_threshold_chars * self.STYLE_BUDGET_THRESHOLD:
                        break

                    parts.append(style_info)
                    running_tokens += style_tokens

        # 向量检索：相关章节片段（Top-5，±10 章窗口过滤）
        if self.vector_facade:
            try:
                collection_name = f"novel_{novel_id}_chunks"
                vector_results = self.vector_facade.sync_search(
                    collection=collection_name,
                    query_text=outline,
                    limit=5,
                )

                # 过滤：±10 章窗口
                filtered_results = [
                    hit for hit in vector_results
                    if abs(hit["payload"]["chapter_number"] - chapter_number) <= 10
                ]

                if filtered_results:
                    parts.append("\nRelevant Context (from previous chapters):")
                    running_tokens = self.estimate_tokens("\n".join(parts))

                    for hit in filtered_results:
                        text = hit["payload"]["text"]
                        vector_info = f"- {text}"
                        vector_tokens = self.estimate_tokens(vector_info)

                        # 检查预算
                        if running_tokens + vector_tokens > budget:
                            break

                        parts.append(vector_info)
                        running_tokens += vector_tokens

            except Exception as e:
                logger.warning(f"Vector retrieval failed: {e}")

        # TODO: 触发词与 Bible 切片联动（Phase 3 Task 5）
        #
        # 预期行为：
        # 1. 检查 scene_director.trigger_keywords 是否非空
        # 2. 使用 expand_triggers(scene_director.trigger_keywords) 扩展关键词
        # 3. 从 bible_dto.world_settings 中匹配 name/description/setting_type 包含关键词的条目
        # 4. 追加到 Layer2，受 token 预算约束
        #
        # 依赖缺失：
        # - BibleService 当前无 search_settings_by_keywords() 方法
        # - 需要实现简单的关键词匹配逻辑或扩展 BibleService API
        #
        # 实现方案（待选择）：
        # A. 在此处实现简单的关键词匹配（遍历 world_settings，检查字段是否包含关键词）
        # B. 扩展 BibleService 提供 search_settings_by_keywords() 方法
        # C. 扩展 KnowledgeService 提供 search_triples_by_keywords() 方法
        #
        # 参考测试：tests/unit/application/services/test_trigger_keyword_bible_integration.py
        # 当前状态：占位实现，测试标记为 @pytest.mark.skip
        #
        # if scene_director and scene_director.trigger_keywords:
        #     from application.services.trigger_keyword_catalog import expand_triggers
        #     expanded_keywords = expand_triggers(scene_director.trigger_keywords)
        #
        #     # 从 Bible world_settings 中匹配关键词
        #     if bible_dto and bible_dto.world_settings:
        #         matched_settings = []
        #         for setting in bible_dto.world_settings:
        #             # 检查 name, description, setting_type 是否包含任一关键词
        #             if any(kw in setting.name or kw in setting.description or kw in setting.setting_type
        #                    for kw in expanded_keywords):
        #                 matched_settings.append(setting)
        #
        #         if matched_settings:
        #             parts.append("\nTriggered Settings:")
        #             running_tokens = self.estimate_tokens("\n".join(parts))
        #
        #             for setting in matched_settings:
        #                 setting_info = f"- {setting.name} ({setting.setting_type}): {setting.description}"
        #                 setting_tokens = self.estimate_tokens(setting_info)
        #
        #                 if running_tokens + setting_tokens > budget:
        #                     break
        #
        #                 parts.append(setting_info)
        #                 running_tokens += setting_tokens

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
        running_tokens = 0

        # 最近章节
        all_chapters = self.chapter_repository.list_by_novel(NovelId(novel_id))
        recent_chapters = [c for c in all_chapters if c.number < chapter_number]
        recent_chapters = sorted(recent_chapters, key=lambda c: c.number, reverse=True)[:5]

        if recent_chapters:
            parts.append("Recent Chapters:")
            running_tokens = self.estimate_tokens("Recent Chapters:")

            for chapter in reversed(recent_chapters):  # 按时间顺序
                summary = f"Chapter {chapter.number}: {chapter.title}"
                # 添加简短内容摘要
                if chapter.content:
                    content_preview = chapter.content[:self.CHAPTER_CONTENT_PREVIEW_TRUNCATE] + "..." if len(chapter.content) > self.CHAPTER_CONTENT_PREVIEW_TRUNCATE else chapter.content
                    summary += f"\n  {content_preview}"

                summary_tokens = self.estimate_tokens(summary)

                # 检查预算
                if running_tokens + summary_tokens > budget:
                    break

                parts.append(summary)
                running_tokens += summary_tokens

        context = "\n".join(parts)

        # 截断到预算
        if self.estimate_tokens(context) > budget:
            context = self._truncate_text(context, budget)

        return context

    def _truncate_text(self, text: str, budget: int) -> str:
        """截断文本到指定 token 预算"""
        target_chars = budget * self.CHARS_PER_TOKEN
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
