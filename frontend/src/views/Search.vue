<template>
  <MainLayout>
    <div class="search-page">
      <header class="search-header">
        <div class="search-header__copy">
          <div class="page-kicker">全文搜索</div>
          <h1>搜索会议</h1>
          <p>可按会议名称、摘要、逐字稿和行动项搜索。</p>
        </div>
      </header>

      <section class="search-toolbar">
        <div class="search-input-wrap">
          <el-input
            v-model="keyword"
            size="large"
            clearable
            placeholder="搜索会议名称、结论、行动项、负责人"
            @keyup.enter="runSearch"
          >
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
        </div>
        <el-button type="primary" size="large" :loading="loading" @click="runSearch">开始搜索</el-button>
      </section>

      <div class="search-suggestions">
        <span class="search-suggestions__label">试试这些关键词：</span>
        <button
          v-for="example in exampleQueries"
          :key="example"
          class="search-chip"
          @click="useExample(example)"
        >
          {{ example }}
        </button>
      </div>

      <section class="search-workbench">
        <aside class="search-sidebar">
          <div class="sidebar-block">
            <div class="sidebar-title">结果范围</div>
            <button
              v-for="filter in filters"
              :key="filter.value"
              class="filter-row"
              :class="{ active: activeFilter === filter.value }"
              @click="activeFilter = filter.value"
            >
              <span>{{ filter.label }}</span>
              <strong>{{ filter.count }}</strong>
            </button>
          </div>

          <div class="sidebar-block sidebar-block--note">
            <div class="sidebar-title">搜索说明</div>
            <ul class="search-tips">
              <li>优先输入会议名称、负责人或关键词。</li>
              <li>结果较多时，可切换到“行动项”或“逐字稿”。</li>
              <li>点击结果可直接进入对应会议。</li>
            </ul>
          </div>
        </aside>

        <div class="search-results">
          <div v-if="searched" class="results-head">
            <div>
              <div class="results-count">找到 {{ filteredResults.length }} 条结果</div>
              <p>{{ resultsSummary }}</p>
            </div>
            <div class="results-filter-label">{{ currentFilterLabel }}</div>
          </div>

          <div v-if="loading" class="results-state">
            <div class="progress-spinner"></div>
            <p>正在整理搜索结果...</p>
          </div>

          <div v-else-if="!searched" class="results-placeholder">
            <h2>输入关键词开始搜索</h2>
            <p>可搜索会议名称、逐字稿、行动项或负责人。</p>
          </div>

          <TransitionGroup v-else-if="filteredResults.length" name="result-flow" tag="div" class="results-list">
            <article
              v-for="item in filteredResults"
              :key="item.key"
              class="result-item"
              :class="`result-item--${item.kind}`"
            >
              <div class="result-item__head">
                <span class="result-kind">{{ typeLabel(item.kind) }}</span>
                <span class="result-meta">{{ item.meta }}</span>
              </div>

              <div class="result-item__body">
                <div class="result-item__main">
                  <h2 v-html="highlightText(item.title)"></h2>
                  <p v-html="highlightText(item.body)"></p>
                </div>

                <div class="result-item__side">
                  <div class="result-side__label">所属会议</div>
                  <div class="result-side__value">{{ item.meetingName }}</div>
                  <div v-if="item.subMeta" class="result-side__sub">{{ item.subMeta }}</div>
                </div>
              </div>

              <div class="result-item__actions">
                <el-button text @click="goResult(item)">查看会议</el-button>
              </div>
            </article>
          </TransitionGroup>

          <div v-else class="results-placeholder">
            <h2>没有找到相关内容</h2>
            <p>试试更短的关键词，或者切换结果范围查看会议、逐字稿和行动项。</p>
          </div>
        </div>
      </section>
    </div>
  </MainLayout>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import MainLayout from '../components/MainLayout.vue'
import api from '../services/api.js'

const route = useRoute()
const router = useRouter()
const keyword = ref('')
const loading = ref(false)
const searched = ref(false)
const activeFilter = ref('all')
const results = ref({ total: 0, meetings: [], transcripts: [], actions: [] })
const exampleQueries = ['预算', '王芳', '待确认', '产品规划']

const filters = computed(() => [
  { value: 'all', label: '全部结果', count: results.value.total || 0 },
  { value: 'meeting', label: '会议', count: results.value.meetings.length },
  { value: 'transcript', label: '逐字稿', count: results.value.transcripts.length },
  { value: 'action', label: '行动项', count: results.value.actions.length },
])

const flattenedResults = computed(() => {
  const meetingItems = results.value.meetings.map((item) => ({
    key: `meeting-${item.id}`,
    kind: 'meeting',
    title: item.name,
    body: item.summary || '暂无摘要，点击查看会议详情。',
    meta: `${item.date || '未标注日期'} · ${statusLabel(item.status)}`,
    subMeta: '会议摘要',
    meetingId: item.id,
    meetingName: item.name,
    query: {},
  }))

  const transcriptItems = results.value.transcripts.map((item) => ({
    key: `transcript-${item.meeting_id}-${item.start_ms}`,
    kind: 'transcript',
    title: item.meeting_name,
    body: item.text,
    meta: `${formatTime(item.start_ms)} - ${formatTime(item.end_ms)}`,
    subMeta: '逐字稿片段',
    meetingId: item.meeting_id,
    meetingName: item.meeting_name,
    query: {},
  }))

  const actionItems = results.value.actions.map((item) => ({
    key: `action-${item.id}`,
    kind: 'action',
    title: item.content,
    body: `负责人：${item.owner_name || '未指定'}；截止时间：${item.due_date || '未设置'}；状态：${item.status === 'done' ? '已完成' : item.status === 'in_progress' ? '进行中' : '待处理'}`,
    meta: item.meeting_name,
    subMeta: item.owner_name ? `负责人 ${item.owner_name}` : '未分配负责人',
    meetingId: item.meeting_id,
    meetingName: item.meeting_name,
    query: { tab: 'actions' },
  }))

  return [...meetingItems, ...transcriptItems, ...actionItems]
})

const filteredResults = computed(() => {
  if (activeFilter.value === 'all') return flattenedResults.value
  return flattenedResults.value.filter((item) => item.kind === activeFilter.value)
})

const currentFilterLabel = computed(() => filters.value.find((item) => item.value === activeFilter.value)?.label || '全部结果')

const resultsSummary = computed(() => {
  const query = keyword.value.trim()
  if (!query) return '按会议、逐字稿和行动项统一检索'
  return `关键词“${query}”的结果已经按会议、逐字稿和行动项整理完成`
})

function statusLabel(status) {
  return {
    uploading: '上传中',
    processing: '处理中',
    ready_for_review: '待确认',
    dispatched: '已分发',
  }[status] || status
}

function typeLabel(kind) {
  return {
    meeting: '会议',
    transcript: '逐字稿',
    action: '行动项',
  }[kind] || '结果'
}

function formatTime(ms) {
  const totalSec = Math.floor((ms || 0) / 1000)
  const min = Math.floor(totalSec / 60)
  const sec = totalSec % 60
  return `${String(min).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
}

function escapeHtml(value) {
  return String(value || '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}

function highlightText(value) {
  const safeText = escapeHtml(value)
  const query = keyword.value.trim()
  if (!query) return safeText

  const escapedQuery = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return safeText.replace(new RegExp(escapedQuery, 'ig'), (match) => `<mark>${match}</mark>`)
}

function goResult(item) {
  router.push({
    path: `/meetings/${item.meetingId}`,
    query: item.query,
  })
}

function useExample(example) {
  keyword.value = example
  runSearch()
}

async function runSearch() {
  if (!keyword.value.trim()) {
    ElMessage.warning('请输入搜索关键词')
    return
  }

  loading.value = true
  try {
    const query = keyword.value.trim()
    const res = await api.get('/search', { params: { q: query } })
    results.value = res.data
    searched.value = true
    router.replace({ path: '/search', query: { q: query } })
  } catch (error) {
    ElMessage.error('搜索失败：' + (error.response?.data?.detail || error.message))
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  const initialKeyword = String(route.query.q || '').trim()
  if (initialKeyword) {
    keyword.value = initialKeyword
    runSearch()
  }
})
</script>

<style scoped>
.search-page {
  max-width: 1380px;
  margin: 0 auto;
  padding: clamp(28px, 4vw, 44px);
}

.page-kicker,
.sidebar-title,
.result-side__label {
  margin-bottom: 10px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-soft);
}

.search-header h1,
.results-placeholder h2 {
  font-size: clamp(2rem, 4.2vw, 3.4rem);
  line-height: 0.98;
  letter-spacing: -0.05em;
  color: var(--text);
}

.search-header p,
.results-head p,
.results-placeholder p {
  margin-top: 14px;
  max-width: 56ch;
  color: var(--text-muted);
  line-height: 1.72;
}

.search-toolbar {
  margin-top: 26px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
}

.search-workbench {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  gap: 20px;
  margin-top: 24px;
}

.search-suggestions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-top: 12px;
}

.search-suggestions__label {
  color: var(--text-soft);
  font-size: 13px;
}

.search-chip {
  min-height: 32px;
  padding: 0 12px;
  border-radius: 999px;
  border: 1px solid var(--border-soft);
  background: color-mix(in oklab, var(--bg-elevated) 92%, var(--bg) 8%);
  color: var(--text);
  cursor: pointer;
  transition: transform 0.16s ease, border-color 0.18s ease, background 0.18s ease;
}

.search-chip:hover {
  transform: translateY(-1px);
  border-color: color-mix(in oklab, var(--primary) 18%, var(--border));
  background: color-mix(in oklab, var(--primary) 6%, var(--bg-elevated));
}

.search-sidebar,
.search-results {
  border: 1px solid var(--border-soft);
  background: color-mix(in oklab, var(--bg-elevated) 94%, var(--bg) 6%);
  box-shadow: var(--shadow-sm);
}

.search-sidebar {
  border-radius: 24px;
  padding: 18px;
  align-self: start;
  display: grid;
  gap: 16px;
}

.sidebar-block {
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border-soft);
}

.sidebar-block:last-child {
  padding-bottom: 0;
  border-bottom: none;
}

.filter-row {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid transparent;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  transition: background 0.18s ease, border-color 0.18s ease, color 0.18s ease;
}

.filter-row + .filter-row {
  margin-top: 6px;
}

.filter-row strong {
  color: var(--text);
  font-size: 13px;
}

.filter-row:hover,
.filter-row.active {
  color: var(--text);
  background: color-mix(in oklab, var(--primary) 6%, var(--bg-elevated));
  border-color: color-mix(in oklab, var(--primary) 18%, var(--border));
}

.search-tips {
  display: grid;
  gap: 10px;
  padding-left: 18px;
  color: var(--text-muted);
  line-height: 1.65;
}

.search-results {
  border-radius: 26px;
  padding: 22px;
  min-height: 560px;
}

.results-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: end;
  padding-bottom: 18px;
  margin-bottom: 18px;
  border-bottom: 1px solid var(--border-soft);
}

.results-count {
  font-size: 1.5rem;
  font-weight: 700;
  letter-spacing: -0.03em;
  color: var(--text);
}

.results-filter-label {
  display: inline-flex;
  align-items: center;
  min-height: 34px;
  padding: 0 12px;
  border-radius: 999px;
  border: 1px solid var(--border-soft);
  color: var(--text);
  font-size: 13px;
  font-weight: 700;
}

.results-state,
.results-placeholder {
  min-height: 420px;
  display: grid;
  place-items: center;
  text-align: center;
}

.results-list {
  display: grid;
  gap: 14px;
}

.result-item {
  padding: 18px 18px 16px;
  border-bottom: 1px solid var(--border-soft);
  border-radius: 18px;
  transition: transform 0.18s ease, background 0.18s ease, box-shadow 0.18s ease;
}

.result-item:last-child {
  border-bottom: none;
}

.result-item:hover {
  transform: translateY(-1px);
  background: color-mix(in oklab, var(--primary) 4%, transparent);
  box-shadow: 0 12px 24px rgba(37, 99, 235, 0.08);
}

.result-item__head,
.result-item__actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.result-item__head {
  margin-bottom: 12px;
}

.result-kind {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  background: color-mix(in oklab, var(--primary) 10%, transparent);
  color: color-mix(in oklab, var(--primary) 78%, var(--text) 22%);
  font-size: 12px;
  font-weight: 700;
}

.result-meta {
  color: var(--text-soft);
  font-size: 13px;
}

.result-item__body {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 220px;
  gap: 18px;
}

.result-item__main h2 {
  font-size: 1.08rem;
  line-height: 1.45;
  color: var(--text);
}

.result-item__main p {
  margin-top: 8px;
  color: var(--text-muted);
  line-height: 1.7;
}

.result-item__main :deep(mark) {
  background: color-mix(in oklab, var(--warning) 32%, transparent);
  color: inherit;
  padding: 0 2px;
}

.result-item__side {
  padding-left: 18px;
  border-left: 1px solid var(--border-soft);
}

.result-side__label {
  margin-bottom: 6px;
}

.result-side__value {
  color: var(--text);
  font-weight: 700;
  line-height: 1.55;
}

.result-side__sub {
  margin-top: 6px;
  color: var(--text-muted);
  font-size: 13px;
  line-height: 1.6;
}

.result-item__actions {
  margin-top: 14px;
}

.progress-spinner {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  border: 3px solid color-mix(in oklab, var(--primary) 16%, transparent);
  border-top-color: var(--primary);
  margin: 0 auto 14px;
  animation: spin 1s linear infinite;
}

.result-flow-enter-active,
.result-flow-leave-active {
  transition: opacity 0.24s ease, transform 0.24s ease;
}

.result-flow-enter-from,
.result-flow-leave-to {
  opacity: 0;
  transform: translateY(8px);
}

.result-flow-move {
  transition: transform 0.24s ease;
}

@media (max-width: 1080px) {
  .search-workbench {
    grid-template-columns: 1fr;
  }

  .search-sidebar {
    order: 2;
  }
}

@media (max-width: 760px) {
  .search-toolbar,
  .results-head,
  .result-item__body {
    grid-template-columns: 1fr;
    display: grid;
  }

  .result-item__side {
    padding-left: 0;
    border-left: none;
    border-top: 1px solid var(--border-soft);
    padding-top: 12px;
  }
}
</style>
