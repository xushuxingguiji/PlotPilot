"""生成工作流 API 端点"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import List, Optional
from application.workflows.auto_novel_generation_workflow import AutoNovelGenerationWorkflow
from domain.novel.services.storyline_manager import StorylineManager
from domain.novel.repositories.plot_arc_repository import PlotArcRepository
from domain.novel.value_objects.novel_id import NovelId
from domain.novel.value_objects.storyline_type import StorylineType
from domain.novel.value_objects.tension_level import TensionLevel
from domain.novel.value_objects.plot_point import PlotPoint, PlotPointType
from domain.novel.entities.plot_arc import PlotArc
from interfaces.api.dependencies import (
    get_auto_workflow,
    get_storyline_manager,
    get_plot_arc_repository
)

router = APIRouter(prefix="/novels", tags=["generation"])


# Request/Response Models
class GenerateChapterRequest(BaseModel):
    """生成章节请求"""
    chapter_number: int = Field(..., gt=0, description="章节号（必须 > 0）")
    outline: str = Field(..., min_length=1, description="章节大纲")


class ConsistencyIssueResponse(BaseModel):
    """一致性问题响应"""
    type: str
    severity: str
    description: str
    location: int


class ConsistencyReportResponse(BaseModel):
    """一致性报告响应"""
    issues: List[ConsistencyIssueResponse]
    warnings: List[ConsistencyIssueResponse]
    suggestions: List[str]


class GenerateChapterResponse(BaseModel):
    """生成章节响应"""
    content: str
    consistency_report: ConsistencyReportResponse
    token_count: int


class StorylineResponse(BaseModel):
    """故事线响应"""
    id: str
    storyline_type: str
    status: str
    estimated_chapter_start: int
    estimated_chapter_end: int


class CreateStorylineRequest(BaseModel):
    """创建故事线请求"""
    storyline_type: str = Field(..., description="故事线类型")
    estimated_chapter_start: int = Field(..., gt=0)
    estimated_chapter_end: int = Field(..., gt=0)


class PlotPointResponse(BaseModel):
    """情节点响应"""
    chapter_number: int
    tension: int
    description: str


class PlotArcResponse(BaseModel):
    """情节弧响应"""
    id: str
    novel_id: str
    key_points: List[PlotPointResponse]


class PlotPointRequest(BaseModel):
    """情节点请求"""
    chapter_number: int = Field(..., gt=0)
    tension: int = Field(..., ge=1, le=4)
    description: str
    point_type: str = Field(default="rising", description="情节点类型")


class CreatePlotArcRequest(BaseModel):
    """创建情节弧请求"""
    key_points: List[PlotPointRequest]


# Endpoints
@router.post(
    "/{novel_id}/generate-chapter",
    response_model=GenerateChapterResponse,
    status_code=status.HTTP_200_OK
)
async def generate_chapter(
    novel_id: str,
    request: GenerateChapterRequest,
    workflow: AutoNovelGenerationWorkflow = Depends(get_auto_workflow)
):
    """生成章节（完整工作流）

    整合所有组件完成章节生成：
    - 构建 35K token 上下文
    - 调用 LLM 生成
    - 一致性检查
    - 返回结果和报告
    """
    try:
        result = await workflow.generate_chapter(
            novel_id=novel_id,
            chapter_number=request.chapter_number,
            outline=request.outline
        )

        # 转换一致性报告
        issues = [
            ConsistencyIssueResponse(
                type=issue.type.value,
                severity=issue.severity.value,
                description=issue.description,
                location=issue.location
            )
            for issue in result.consistency_report.issues
        ]

        warnings = [
            ConsistencyIssueResponse(
                type=warning.type.value,
                severity=warning.severity.value,
                description=warning.description,
                location=warning.location
            )
            for warning in result.consistency_report.warnings
        ]

        return GenerateChapterResponse(
            content=result.content,
            consistency_report=ConsistencyReportResponse(
                issues=issues,
                warnings=warnings,
                suggestions=result.consistency_report.suggestions
            ),
            token_count=result.token_count
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Generation failed: {str(e)}"
        )


@router.get(
    "/{novel_id}/consistency-report",
    response_model=ConsistencyReportResponse,
    status_code=status.HTTP_200_OK
)
async def get_consistency_report(
    novel_id: str,
    workflow: AutoNovelGenerationWorkflow = Depends(get_auto_workflow)
):
    """获取最新的一致性报告

    注意：这需要先调用 generate_chapter 生成内容
    """
    # 简化实现：返回空报告
    # 实际应该从缓存或数据库获取最新报告
    return ConsistencyReportResponse(
        issues=[],
        warnings=[],
        suggestions=[]
    )


@router.get(
    "/{novel_id}/storylines",
    response_model=List[StorylineResponse],
    status_code=status.HTTP_200_OK
)
def get_storylines(
    novel_id: str,
    manager: StorylineManager = Depends(get_storyline_manager)
):
    """获取小说的所有故事线"""
    try:
        storylines = manager.repository.find_by_novel(NovelId(novel_id))

        return [
            StorylineResponse(
                id=storyline.id,
                storyline_type=storyline.storyline_type.value,
                status=storyline.status.value,
                estimated_chapter_start=storyline.estimated_chapter_start,
                estimated_chapter_end=storyline.estimated_chapter_end
            )
            for storyline in storylines
        ]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get storylines: {str(e)}"
        )


@router.post(
    "/{novel_id}/storylines",
    response_model=StorylineResponse,
    status_code=status.HTTP_201_CREATED
)
def create_storyline(
    novel_id: str,
    request: CreateStorylineRequest,
    manager: StorylineManager = Depends(get_storyline_manager)
):
    """创建新的故事线"""
    try:
        storyline = manager.create_storyline(
            novel_id=NovelId(novel_id),
            storyline_type=StorylineType(request.storyline_type),
            estimated_chapter_start=request.estimated_chapter_start,
            estimated_chapter_end=request.estimated_chapter_end
        )

        return StorylineResponse(
            id=storyline.id,
            storyline_type=storyline.storyline_type.value,
            status=storyline.status.value,
            estimated_chapter_start=storyline.estimated_chapter_start,
            estimated_chapter_end=storyline.estimated_chapter_end
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create storyline: {str(e)}"
        )


@router.get(
    "/{novel_id}/plot-arc",
    response_model=PlotArcResponse,
    status_code=status.HTTP_200_OK
)
def get_plot_arc(
    novel_id: str,
    repository: PlotArcRepository = Depends(get_plot_arc_repository)
):
    """获取小说的情节弧"""
    try:
        plot_arc = repository.get_by_novel_id(NovelId(novel_id))

        if plot_arc is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Plot arc not found for novel {novel_id}"
            )

        return PlotArcResponse(
            id=plot_arc.id,
            novel_id=novel_id,
            key_points=[
                PlotPointResponse(
                    chapter_number=point.chapter_number,
                    tension=point.tension.value,
                    description=point.description
                )
                for point in plot_arc.key_points
            ]
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get plot arc: {str(e)}"
        )


@router.post(
    "/{novel_id}/plot-arc",
    response_model=PlotArcResponse,
    status_code=status.HTTP_200_OK
)
def create_or_update_plot_arc(
    novel_id: str,
    request: CreatePlotArcRequest,
    repository: PlotArcRepository = Depends(get_plot_arc_repository)
):
    """创建或更新情节弧"""
    try:
        # 尝试获取现有的情节弧
        plot_arc = repository.get_by_novel_id(NovelId(novel_id))

        if plot_arc is None:
            # 创建新的情节弧
            plot_arc = PlotArc(id=f"{novel_id}-arc", novel_id=NovelId(novel_id))

        # 清空现有的情节点并添加新的
        plot_arc.key_points = []
        for point_req in request.key_points:
            plot_arc.add_plot_point(PlotPoint(
                chapter_number=point_req.chapter_number,
                point_type=PlotPointType(point_req.point_type),
                description=point_req.description,
                tension=TensionLevel(point_req.tension)
            ))

        # 保存
        repository.save(plot_arc)

        return PlotArcResponse(
            id=plot_arc.id,
            novel_id=novel_id,
            key_points=[
                PlotPointResponse(
                    chapter_number=point.chapter_number,
                    tension=point.tension.value,
                    description=point.description
                )
                for point in plot_arc.key_points
            ]
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create/update plot arc: {str(e)}"
        )
