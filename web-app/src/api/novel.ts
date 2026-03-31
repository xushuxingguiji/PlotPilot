import { apiClient } from './config'

export interface ChapterDTO {
  id: string
  number: number
  title: string
  content: string
  word_count: number
}

export interface NovelDTO {
  id: string
  title: string
  author: string
  target_chapters: number
  stage: string
  chapters: ChapterDTO[]
  total_word_count: number
}

export const novelApi = {
  /**
   * List all novels
   * GET /api/v1/novels
   */
  listNovels: () => apiClient.get<NovelDTO[]>('/novels') as Promise<NovelDTO[]>,

  /**
   * Get novel by ID
   * GET /api/v1/novels/{novelId}
   */
  getNovel: (novelId: string) => apiClient.get<NovelDTO>(`/novels/${novelId}`) as Promise<NovelDTO>,

  /**
   * Create a new novel
   * POST /api/v1/novels
   */
  createNovel: (data: {
    novel_id: string
    title: string
    author: string
    target_chapters: number
  }) => apiClient.post<NovelDTO>('/novels', data) as Promise<NovelDTO>,

  /**
   * Delete a novel
   * DELETE /api/v1/novels/{novelId}
   */
  deleteNovel: (novelId: string) => apiClient.delete<void>(`/novels/${novelId}`) as Promise<void>,

  /**
   * Update novel stage
   * PUT /api/v1/novels/{novelId}/stage
   */
  updateNovelStage: (novelId: string, stage: string) =>
    apiClient.put<NovelDTO>(`/novels/${novelId}/stage`, { stage }) as Promise<NovelDTO>,

  /**
   * Get novel statistics
   * GET /api/v1/novels/{novelId}/statistics
   */
  getNovelStatistics: (novelId: string) =>
    apiClient.get<any>(`/novels/${novelId}/statistics`) as Promise<any>,
}
