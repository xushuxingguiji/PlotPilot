import { ref, computed, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import { workflowApi } from '../api/workflow'
import { novelApi } from '../api/novel'
import { chapterApi } from '../api/chapter'
import { useStatsStore } from '../stores/statsStore'

// Constants for magic numbers
const PROGRESS_INITIAL = 6
const PROGRESS_MAX = 93
const PROGRESS_MIN_STEP = 2
const PROGRESS_MAX_STEP = 6
const STATS_DAYS = 30
const POLLING_INTERVAL = 1000

function formatApiErrorDetail(error: unknown): string {
  const e = error as { response?: { data?: { detail?: unknown } }; message?: string }
  const d = e?.response?.data?.detail
  if (typeof d === 'string' && d.trim()) return d
  if (Array.isArray(d)) {
    const parts = d.map((x: { msg?: string }) => (typeof x?.msg === 'string' ? x.msg : JSON.stringify(x)))
    return parts.join('; ') || ''
  }
  if (e?.message && typeof e.message === 'string') return e.message
  return ''
}

// Type definitions
export interface BookMeta {
  has_bible?: boolean
  has_outline?: boolean
}

export interface UseWorkbenchOptions {
  slug: string
}

export function useWorkbench(options: UseWorkbenchOptions) {
  const { slug } = options
  const router = useRouter()
  const message = useMessage()
  const statsStore = useStatsStore()

  // State - Business logic only, no UI state
  const bookTitle = ref('')
  const chapters = ref<{ id: number; number: number; title: string; word_count: number }[]>([])
  const bookMeta = ref<BookMeta>({})
  const pageLoading = ref(true)
  const currentChapterId = ref<number | null>(null)
  const chapterContent = ref('')
  const chapterLoading = ref(false)

  // UI state that should be in components, not composable
  // Kept for backward compatibility but marked for future migration
  const rightPanel = ref<'bible' | 'knowledge'>('bible')
  const biblePanelKey = ref(0)
  const showPlanModal = ref(false)
  const planMode = ref<'initial' | 'revise'>('initial')
  const planDryRun = ref(false)
  const showTaskModal = ref(false)
  const taskProgress = ref(0)
  const taskMessage = ref('')
  const currentJobId = ref<string | null>(null)


  const hasStructure = computed(() => {
    return bookMeta.value.has_bible || bookMeta.value.has_outline
  })

  // Methods
  const setRightPanel = (panel: 'bible' | 'knowledge') => {
    rightPanel.value = panel
  }

  const loadDesk = async () => {
    // Use new novelApi and chapterApi instead of bookApi.getDesk
    const [novelData, chaptersData] = await Promise.all([
      novelApi.getNovel(slug),
      chapterApi.listChapters(slug)
    ])

    bookTitle.value = novelData.title || slug

    // Map ChapterDTO[] to the format expected by the UI
    chapters.value = chaptersData.map(ch => ({
      id: ch.number,
      number: ch.number,
      title: ch.title,
      word_count: ch.word_count || 0
    }))

    // Use metadata from NovelDTO
    bookMeta.value = {
      has_bible: novelData.has_bible,
      has_outline: novelData.has_outline,
    }
  }

  const loadData = async (includeStats = false) => {
    pageLoading.value = true
    try {
      const promises: Promise<unknown>[] = [loadDesk()]
      if (includeStats) {
        promises.push(statsStore.loadBookAllStats(slug, STATS_DAYS, true))
      }
      await Promise.all(promises)
    } finally {
      pageLoading.value = false
    }
  }

  const handleJobCompleted = async () => {
    // Notify stats store to invalidate cache and reload
    statsStore.onJobCompleted(slug)
    // Refresh workbench data
    await loadDesk()
    // Force Bible panel refresh if visible
    if (rightPanel.value === 'bible') {
      biblePanelKey.value += 1
    }
  }

  const restoreJobState = () => {
    // Note: localStorage recovery not currently used in the architecture
    // Job state is managed through API polling and component lifecycle
    // This method is a no-op but preserved for future expansion
  }

  const openPlanModal = () => {
    planMode.value = (bookMeta.value.has_bible && bookMeta.value.has_outline) ? 'revise' : 'initial'
    planDryRun.value = false
    showPlanModal.value = true
  }

  const confirmPlan = async () => {
    showPlanModal.value = false
    try {
      const res = await workflowApi.startPlanJob(slug, planDryRun.value, planMode.value)
      startPolling(res.job_id)
    } catch (error: any) {
      message.error(error.response?.data?.detail || '启动失败')
    }
  }

  // Polling logic - Should be migrated to JobStatusIndicator component per spec
  // Kept here for backward compatibility during refactoring
  const taskTimer = ref<number | null>(null)

  const startPolling = (jobId: string) => {
    currentJobId.value = jobId
    showTaskModal.value = true
    taskProgress.value = PROGRESS_INITIAL
    taskMessage.value = '任务启动中…'
    let bump = PROGRESS_INITIAL

    // Clear any existing timer to prevent memory leaks
    if (taskTimer.value) {
      window.clearInterval(taskTimer.value)
      taskTimer.value = null
    }

    taskTimer.value = window.setInterval(async () => {
      bump = Math.min(PROGRESS_MAX, bump + PROGRESS_MIN_STEP + Math.random() * PROGRESS_MAX_STEP)
      taskProgress.value = Math.floor(bump)
      try {
        const status = await workflowApi.getJobStatus(jobId)
        taskMessage.value = status.message || status.phase || '执行中…'

        if (status.status === 'done') {
          taskProgress.value = 100
          stopPolling()
          message.success('任务完成')
          await handleJobCompleted()
        } else if (status.status === 'cancelled') {
          taskProgress.value = 100
          stopPolling()
          message.info('任务已终止')
          await loadDesk()
        } else if (status.status === 'error') {
          stopPolling()
          message.error(status.error || '任务失败')
        }
      } catch (error) {
        console.error('Polling error:', error)
        stopPolling()
        message.error('任务状态更新失败')
      }
    }, POLLING_INTERVAL)
  }

  const cancelRunningTask = async () => {
    const jid = currentJobId.value
    if (!jid) return
    try {
      await workflowApi.cancelJob(jid)
      taskMessage.value = '正在终止…'
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '终止失败')
    }
  }

  const stopPolling = () => {
    if (taskTimer.value) {
      window.clearInterval(taskTimer.value)
      taskTimer.value = null
    }
    currentJobId.value = null
    showTaskModal.value = false
  }

  const goHome = () => {
    router.push('/')
  }

  /**
   * 判断错误是否为 404（后端 EntityNotFoundError / HTTP 404）
   */
  function is404(error: unknown): boolean {
    const e = error as { response?: { status?: number }; message?: string }
    if (e?.response?.status === 404) return true
    const detail = formatApiErrorDetail(error)
    return /not\s*found|不存在/i.test(detail)
  }

  const goToChapter = async (id: number, nodeTitle?: string) => {
    if (!Number.isFinite(id) || id < 1) {
      message.error('无效的章节号')
      return
    }

    chapterLoading.value = true
    try {
      let chapter = await chapterApi.getChapter(slug, id).catch(async (err) => {
        if (!is404(err)) throw err
        // 章节正文不存在：静默创建空白记录（对应结构树手动添加的节点）
        await chapterApi.ensureChapter(slug, id, nodeTitle ?? '')
        return chapterApi.getChapter(slug, id)
      })
      currentChapterId.value = id
      chapterContent.value = chapter.content || ''
      // 若刚刚是新建的空白章节，刷新侧栏章节列表
      const existed = chapters.value.some((c) => c.number === id)
      if (!existed) {
        await loadDesk()
      }
    } catch (error) {
      const detail = formatApiErrorDetail(error)
      currentChapterId.value = null
      chapterContent.value = ''
      message.error(
        detail
          ? `加载第 ${id} 章失败：${detail}`
          : `加载第 ${id} 章失败，请确认后端已启动。`
      )
    } finally {
      chapterLoading.value = false
    }
  }

  const handleChapterSelect = async (chapterId: number, title = '') => {
    await goToChapter(chapterId, title)
  }

  const handleUpdateSettings = async (_settings: Record<string, unknown>) => {
    // Settings are managed by child components (BiblePanel, KnowledgePanel)
    // This method provides a consistent interface for future use
    // Current architecture uses delegation pattern
  }

  // Cleanup on unmount
  onUnmounted(() => {
    stopPolling()
  })

  return {
    // State
    bookTitle,
    chapters,
    rightPanel,
    biblePanelKey,
    pageLoading,
    showPlanModal,
    planMode,
    planDryRun,
    bookMeta,
    showTaskModal,
    taskProgress,
    taskMessage,
    currentJobId,
    currentChapterId,
    chapterContent,
    chapterLoading,

    // Computed
    hasStructure,

    // Methods
    setRightPanel,
    loadDesk,
    loadData,
    handleJobCompleted,
    restoreJobState,
    handleChapterSelect,
    handleUpdateSettings,
    openPlanModal,
    confirmPlan,
    startPolling,
    cancelRunningTask,
    stopPolling,
    goHome,
    goToChapter,
  }
}
