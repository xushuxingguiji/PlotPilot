import { apiClient } from './config'

export const aiApi = {
  /**
   * Generate chapter content using AI
   * POST /api/v1/ai/generate-chapter
   */
  generateChapter: async (data: {
    novel_id: string
    chapter_number: number
    outline: string
  }): Promise<string> => {
    const response = await apiClient.post<{ content: string }>('/ai/generate-chapter', data)
    return response.content
  },
}
