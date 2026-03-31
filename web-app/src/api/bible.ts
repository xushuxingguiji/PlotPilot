import { apiClient } from './config'

export interface CharacterDTO {
  id: string
  name: string
  description: string
  relationships: string[]
}

export interface WorldSettingDTO {
  id: string
  name: string
  description: string
  setting_type: string
}

export interface BibleDTO {
  id: string
  novel_id: string
  characters: CharacterDTO[]
  world_settings: WorldSettingDTO[]
}

export const bibleApi = {
  /**
   * Create bible for a novel
   * POST /api/v1/bible/novels/{novelId}/bible
   */
  createBible: (novelId: string, bibleId: string) =>
    apiClient.post<BibleDTO>(`/bible/novels/${novelId}/bible`, {
      bible_id: bibleId,
      novel_id: novelId,
    }) as Promise<BibleDTO>,

  /**
   * Get bible by novel ID
   * GET /api/v1/bible/novels/{novelId}/bible
   */
  getBible: (novelId: string) =>
    apiClient.get<BibleDTO>(`/bible/novels/${novelId}/bible`) as Promise<BibleDTO>,

  /**
   * Add character to bible
   * POST /api/v1/bible/novels/{novelId}/bible/characters
   */
  addCharacter: (
    novelId: string,
    data: { character_id: string; name: string; description: string }
  ) =>
    apiClient.post<BibleDTO>(`/bible/novels/${novelId}/bible/characters`, data) as Promise<BibleDTO>,

  /**
   * Add world setting to bible
   * POST /api/v1/bible/novels/{novelId}/bible/world-settings
   */
  addWorldSetting: (
    novelId: string,
    data: { setting_id: string; name: string; description: string; setting_type: string }
  ) =>
    apiClient.post<BibleDTO>(`/bible/novels/${novelId}/bible/world-settings`, data) as Promise<BibleDTO>,
}
