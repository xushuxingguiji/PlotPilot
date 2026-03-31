import { apiClient } from './config'

export interface ChapterDTO {
  id: string
  number: number
  title: string
  content: string
  word_count: number
}

export const chapterApi = {
  /**
   * Get chapter by ID
   * GET /api/v1/chapters/{chapterId}
   */
  getChapter: (chapterId: string) =>
    apiClient.get<ChapterDTO>(`/chapters/${chapterId}`) as Promise<ChapterDTO>,

  /**
   * Update chapter content
   * PUT /api/v1/chapters/{chapterId}/content
   */
  updateChapterContent: (chapterId: string, content: string) =>
    apiClient.put<ChapterDTO>(`/chapters/${chapterId}/content`, { content }) as Promise<ChapterDTO>,

  /**
   * Delete a chapter
   * DELETE /api/v1/chapters/{chapterId}
   */
  deleteChapter: (chapterId: string) =>
    apiClient.delete<void>(`/chapters/${chapterId}`) as Promise<void>,

  /**
   * List chapters by novel
   * GET /api/v1/chapters/novels/{novelId}/chapters
   */
  listChaptersByNovel: (novelId: string) =>
    apiClient.get<ChapterDTO[]>(`/chapters/novels/${novelId}/chapters`) as Promise<ChapterDTO[]>,
}
