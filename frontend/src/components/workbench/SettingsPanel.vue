<template>
  <div class="right-panel">
    <!-- 一级：剧本基建 / 叙事脉络 / 片场 — 监控在中栏「监控大盘」 -->
    <div class="group-bar">
      <n-radio-group v-model:value="activeGroup" size="small" class="group-switch">
        <n-radio-button value="foundation">剧本基建</n-radio-button>
        <n-radio-button value="narrative">叙事脉络</n-radio-button>
        <n-radio-button value="tactical">片场</n-radio-button>
      </n-radio-group>
      <n-text v-if="currentChapter" depth="3" style="font-size:11px;flex-shrink:0">
        第{{ currentChapter.number }}章
        <n-tag :type="currentChapter.word_count > 0 ? 'success' : 'default'" size="tiny" round style="margin-left:4px">
          {{ currentChapter.word_count > 0 ? '已收稿' : '未收稿' }}
        </n-tag>
      </n-text>
    </div>

    <!-- 剧本基建：作品设定 / 世界观 / 知识库 -->
    <n-tabs
      v-if="activeGroup === 'foundation'"
      v-model:value="foundationTab"
      type="line"
      size="small"
      class="settings-tabs"
      :tabs-padding="8"
    >
      <n-tab-pane name="bible" tab="作品设定">
        <BiblePanel :key="bibleKey" :slug="slug" />
      </n-tab-pane>
      <n-tab-pane name="worldbuilding" tab="世界观">
        <WorldbuildingPanel :slug="slug" />
      </n-tab-pane>
      <n-tab-pane name="knowledge" tab="知识库">
        <KnowledgePanel :slug="slug" />
      </n-tab-pane>
    </n-tabs>

    <!-- 叙事脉络：故事线 / 情节弧 / 时间线 / 重构扫描 -->
    <n-tabs
      v-if="activeGroup === 'narrative'"
      v-model:value="narrativeTab"
      type="line"
      size="small"
      class="settings-tabs"
      :tabs-padding="8"
    >
      <n-tab-pane name="storylines" tab="故事线">
        <StorylinePanel :slug="slug" />
      </n-tab-pane>
      <n-tab-pane name="plot-arc" tab="情节弧">
        <PlotArcPanel :slug="slug" />
      </n-tab-pane>
      <n-tab-pane name="timeline" tab="时间线">
        <TimelinePanel :slug="slug" />
      </n-tab-pane>
      <n-tab-pane name="macro-refactor" tab="重构扫描">
        <MacroRefactorPanel :slug="slug" />
      </n-tab-pane>
    </n-tabs>

    <!-- 片场：绑定当前选中章 -->
    <n-tabs
      v-if="activeGroup === 'tactical'"
      v-model:value="tacticalTab"
      type="line"
      size="small"
      class="settings-tabs"
      :tabs-padding="8"
    >
      <n-tab-pane name="sandbox" tab="对话沙盒">
        <SandboxDialoguePanel :slug="slug" />
      </n-tab-pane>
      <n-tab-pane name="foreshadow" tab="伏笔">
        <ForeshadowLedgerPanel :slug="slug" />
      </n-tab-pane>
    </n-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import BiblePanel from '../panels/BiblePanel.vue'
import KnowledgePanel from '../knowledge/KnowledgePanel.vue'
import WorldbuildingPanel from './WorldbuildingPanel.vue'
import StorylinePanel from './StorylinePanel.vue'
import PlotArcPanel from './PlotArcPanel.vue'
import TimelinePanel from './TimelinePanel.vue'
import ForeshadowLedgerPanel from './ForeshadowLedgerPanel.vue'
import MacroRefactorPanel from './MacroRefactorPanel.vue'
import SandboxDialoguePanel from './SandboxDialoguePanel.vue'

/** 剧本基建组 */
const FOUNDATION_TABS = new Set(['bible', 'worldbuilding', 'knowledge'])
/** 叙事脉络组 */
const NARRATIVE_TABS = new Set(['storylines', 'plot-arc', 'timeline', 'macro-refactor'])
/** 片场（章节元素已移至中栏 Tab） */
const TACTICAL_TABS = new Set(['sandbox', 'foreshadow'])

function resolveGroup(panel: string | undefined): 'foundation' | 'narrative' | 'tactical' {
  if (!panel) return 'foundation'
  if (TACTICAL_TABS.has(panel)) return 'tactical'
  if (NARRATIVE_TABS.has(panel)) return 'narrative'
  return 'foundation'
}

interface Chapter {
  id: number
  number: number
  title: string
  word_count: number
}

interface Props {
  slug: string
  currentPanel?: string
  bibleKey?: number
  currentChapter?: Chapter | null
}

const props = withDefaults(defineProps<Props>(), {
  currentPanel: 'bible',
  bibleKey: 0,
  currentChapter: null,
})

const activeGroup = ref<'foundation' | 'narrative' | 'tactical'>(resolveGroup(props.currentPanel))

const foundationTab = ref(
  FOUNDATION_TABS.has(props.currentPanel ?? '') ? props.currentPanel! : 'bible'
)
const narrativeTab = ref(
  NARRATIVE_TABS.has(props.currentPanel ?? '') ? props.currentPanel! : 'storylines'
)
const tacticalTab = ref(
  TACTICAL_TABS.has(props.currentPanel ?? '') ? props.currentPanel! : 'sandbox'
)

watch(() => props.currentPanel, (newVal) => {
  if (!newVal) return
  if (TACTICAL_TABS.has(newVal)) {
    activeGroup.value = 'tactical'
    tacticalTab.value = newVal
  } else if (NARRATIVE_TABS.has(newVal)) {
    activeGroup.value = 'narrative'
    narrativeTab.value = newVal
  } else if (FOUNDATION_TABS.has(newVal)) {
    activeGroup.value = 'foundation'
    foundationTab.value = newVal
  } else {
    activeGroup.value = 'foundation'
    foundationTab.value = 'bible'
  }
})
</script>

<style scoped>
.right-panel {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--aitext-panel-muted);
  border-left: 1px solid var(--aitext-split-border);
}

.group-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 6px 10px;
  background: var(--app-surface);
  border-bottom: 1px solid var(--aitext-split-border);
  flex-shrink: 0;
}

.group-switch {
  flex-shrink: 0;
  flex-wrap: wrap;
}

.settings-tabs {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.settings-tabs :deep(.n-tabs-nav) {
  padding: 0 8px;
  background: var(--app-surface);
  border-bottom: 1px solid var(--aitext-split-border);
  overflow-x: auto;
  scrollbar-width: none;
}
.settings-tabs :deep(.n-tabs-nav::-webkit-scrollbar) {
  display: none;
}

.settings-tabs :deep(.n-tabs-content) {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

/* Naive UI 动画容器，必须锁死不让溢出覆盖 tab 导航栏 */
.settings-tabs :deep(.n-tabs-content-wrapper) {
  height: 100%;
  overflow: hidden;
}

.settings-tabs :deep(.n-tabs-pane-wrapper) {
  height: 100%;
  overflow: hidden;
}

.settings-tabs :deep(.n-tab-pane) {
  height: 100%;
  overflow: hidden;
}
</style>