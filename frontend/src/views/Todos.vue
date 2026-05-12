<template>
  <MainLayout>
    <div class="todos-page">
      <header class="page-header">
        <div class="header-copy">
          <div class="page-eyebrow">任务跟踪</div>
          <h1 class="page-title">我的待办</h1>
        </div>

        <div class="filter-tabs">
          <button
            v-for="f in filters"
            :key="f.val"
            class="filter-tab"
            :class="{ active: currentFilter === f.val }"
            @click="currentFilter = f.val"
          >
            {{ f.label }}
            <span class="tab-count">{{ f.count }}</span>
          </button>
        </div>
      </header>

      <section class="stats-grid">
        <div class="stat-card overdue">
          <div class="stat-accent"></div>
          <div class="stat-main">
            <div class="stat-value-wrap">
              <div class="stat-value">{{ overdueCount }}</div>
              <div class="stat-label">逾期任务</div>
            </div>
            <div class="stat-hint">优先补充说明或更新截止日期。</div>
          </div>
        </div>
        <div class="stat-card today">
          <div class="stat-accent"></div>
          <div class="stat-main">
            <div class="stat-value-wrap">
              <div class="stat-value">{{ todayCount }}</div>
              <div class="stat-label">今日截止</div>
            </div>
            <div class="stat-hint">建议今天处理完或同步最新进度。</div>
          </div>
        </div>
        <div class="stat-card active">
          <div class="stat-accent"></div>
          <div class="stat-main">
            <div class="stat-value-wrap">
              <div class="stat-value">{{ inProgressCount }}</div>
              <div class="stat-label">进行中</div>
            </div>
            <div class="stat-hint">已经开始处理的任务会集中显示在这里。</div>
          </div>
        </div>
      </section>

      <section v-if="focusTodo" class="focus-panel">
        <div class="focus-panel__main">
          <div class="focus-kicker">当前优先处理</div>
          <h1>{{ focusTodo.content }}</h1>
          <div class="focus-meta">
            <span class="status-badge" :class="displayStatus(focusTodo)">{{ statusText(focusTodo) }}</span>
            <span class="focus-meta__item">{{ focusTodo.meeting_name }}</span>
            <span class="focus-meta__item" :class="dueCls(focusTodo)">
              {{ focusTodo.due_date || '未设置截止时间' }} {{ dueLabel(focusTodo) }}
            </span>
            <span class="focus-meta__item">{{ focusTodo.owner_name }}</span>
          </div>
          <p class="focus-note">{{ focusHint }}</p>
        </div>

        <div class="focus-panel__actions">
          <el-button text @click="openNoteDialog(focusTodo)">进度备注</el-button>
          <el-button @click="openTodo(focusTodo)">查看详情</el-button>
          <el-button
            v-if="focusTodo.status !== 'done'"
            type="primary"
            @click="updateStatus(focusTodo, focusTodo.status === 'in_progress' ? 'done' : 'in_progress')"
          >
            {{ focusTodo.status === 'in_progress' ? '标记完成' : '开始处理' }}
          </el-button>
        </div>
      </section>

      <div v-if="overdueCount" class="alert-strip">
        <el-icon><WarningFilled /></el-icon>
        <span>你有 {{ overdueCount }} 项任务已逾期，建议优先补充最新进度并确认新的截止日期。</span>
      </div>

      <div v-if="loading" class="loading-wrap">
        <el-skeleton :rows="6" animated />
      </div>

      <div v-else-if="visibleGroups.length === 0" class="empty-wrap">
        <el-icon size="64" class="empty-icon"><CircleCheck /></el-icon>
        <p>当前没有待办任务，可以先去会议列表查看是否有新分发的事项。</p>
      </div>

      <div v-else class="todo-workbench">
        <div class="todo-lanes">
          <section v-for="group in visibleGroups" :key="group.key" class="todo-lane" :class="`todo-lane--${group.key}`">
<!--            <header class="todo-lane__header">-->
<!--              <div class="todo-lane__intro">-->
<!--                <div class="todo-lane__kicker">{{ group.kicker }}</div>-->
<!--                <h2>{{ group.title }}</h2>-->
<!--                <p>{{ group.hint }}</p>-->
<!--              </div>-->
<!--              <div class="todo-lane__summary">-->
<!--                <div class="todo-lane__count">{{ group.items.length }}</div>-->
<!--                <div class="todo-lane__summary-label">项任务</div>-->
<!--              </div>-->
<!--            </header>-->

            <div class="todo-list">
              <article
                v-for="(item, index) in group.items"
                :key="item.id"
                class="todo-card fade-slide-up"
                :class="[displayStatus(item), { overdue: isOverdue(item) }]"
                :style="[todoTransitionStyle(item), { animationDelay: `${index * 36}ms` }]"
              >
                <div class="todo-status-dot" :class="displayStatus(item)"></div>

                <div class="todo-body">
                  <div class="todo-top">
                    <div>
                      <p class="todo-content" :class="{ striked: item.status === 'done' }">{{ item.content }}</p>
                      <div class="todo-tags">
                        <span class="status-badge" :class="displayStatus(item)">{{ statusText(item) }}</span>
                        <span v-if="isOverdue(item)" class="flag-badge overdue">已逾期</span>
                        <span v-else-if="isToday(item.due_date)" class="flag-badge today">今日截止</span>
                        <span v-if="item.progress_note" class="flag-badge note">有进度备注</span>
                      </div>
                    </div>
                  </div>

                  <div class="todo-meta">
                    <span class="meta-item"><el-icon><Tickets /></el-icon>{{ item.meeting_name }}</span>
                    <span class="meta-item" :class="dueCls(item)">
                      <el-icon><Calendar /></el-icon>{{ item.due_date || '未设置截止时间' }} {{ dueLabel(item) }}
                    </span>
                    <span class="meta-item"><el-icon><User /></el-icon>{{ item.owner_name }}</span>
                    <span v-if="item.viewed_at" class="meta-item"><el-icon><View /></el-icon>已查看</span>
                    <span v-if="item.completed_at" class="meta-item"><el-icon><CircleCheck /></el-icon>已完成</span>
                  </div>

                  <div v-if="item.progress_note" class="note-preview">
                    <div class="note-title">最新进度备注 / 回复说明</div>
                    <div class="note-content">{{ item.progress_note }}</div>
                  </div>
                </div>

                <div class="todo-actions">
                  <el-button size="small" text @click="openTodo(item)">查看详情</el-button>
                  <el-button size="small" text @click="openNoteDialog(item)">进度备注</el-button>
                  <el-button
                    v-if="item.status !== 'in_progress' && item.status !== 'done'"
                    size="small"
                    @click="updateStatus(item, 'in_progress')"
                  >
                    开始处理
                  </el-button>
                  <el-button
                    v-if="item.status !== 'done'"
                    size="small"
                    type="primary"
                    @click="updateStatus(item, 'done')"
                  >
                    标记完成
                  </el-button>
                </div>
              </article>
            </div>
          </section>
        </div>
      </div>

      <el-dialog
        v-model="noteDialogVisible"
        title="更新进度备注"
        width="560px"
        destroy-on-close
      >
        <div v-if="activeTodo" class="note-dialog">
          <div class="note-dialog-item">
            <div class="note-dialog-label">任务内容</div>
            <div class="note-dialog-value">{{ activeTodo.content }}</div>
          </div>
          <div class="note-dialog-item">
            <div class="note-dialog-label">所属会议</div>
            <div class="note-dialog-value">{{ activeTodo.meeting_name }}</div>
          </div>
          <div class="note-dialog-item">
            <div class="note-dialog-label">进度备注 / 回复说明</div>
            <el-input
              v-model="noteForm.progress_note"
              type="textarea"
              :rows="6"
              maxlength="1000"
              show-word-limit
              placeholder="例如：已和相关同事确认方案，预计今天下班前提交初稿。"
            />
          </div>
        </div>
        <template #footer>
          <el-button @click="noteDialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="savingNote" @click="saveNote">保存备注</el-button>
        </template>
      </el-dialog>
    </div>
  </MainLayout>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Calendar, CircleCheck, Tickets, User, View, WarningFilled } from '@element-plus/icons-vue'
import api from '../services/api.js'
import MainLayout from '../components/MainLayout.vue'

const router = useRouter()
const loading = ref(true)
const todos = ref([])
const currentFilter = ref('all')
const noteDialogVisible = ref(false)
const savingNote = ref(false)
const activeTodo = ref(null)
const noteForm = ref({ progress_note: '' })
const transitioningTodoId = ref('')

function normalizeDate(value) {
  if (!value) return null
  const plain = /^\d{4}-\d{2}-\d{2}$/.test(value) ? `${value}T00:00:00` : value
  const date = new Date(plain)
  return Number.isNaN(date.getTime()) ? null : date
}

function startOfDay(date) {
  const copy = new Date(date)
  copy.setHours(0, 0, 0, 0)
  return copy
}

function isOverdue(item) {
  if (item.status === 'done') return false
  const due = normalizeDate(item.due_date)
  if (!due) return false
  return startOfDay(due) < startOfDay(new Date())
}

function isToday(dateValue) {
  const due = normalizeDate(dateValue)
  if (!due) return false
  return startOfDay(due).getTime() === startOfDay(new Date()).getTime()
}

function displayStatus(item) {
  if (item.status === 'done') return 'done'
  if (item.status === 'in_progress') return 'in_progress'
  if (item.is_viewed) return 'viewed'
  return 'pending'
}

function statusText(item) {
  return {
    pending: '待处理',
    viewed: '已查看',
    in_progress: '进行中',
    done: '已完成',
  }[displayStatus(item)]
}

function laneMeta(key) {
  return {
    overdue: {
      kicker: '风险优先',
      title: '逾期任务',
      hint: '这些任务已经超过截止时间，建议先补充最新处理说明。',
    },
    today: {
      kicker: '当日处理',
      title: '今日截止',
      hint: '这些任务今天需要给出结果，适合集中推进。',
    },
    in_progress: {
      kicker: '继续推进',
      title: '进行中的任务',
      hint: '已经开始处理，可以补充备注并继续跟进。',
    },
    pending: {
      kicker: '待开始',
      title: '待处理任务',
      hint: '这些任务还未开始，建议尽快明确负责人和处理路径。',
    },
    viewed: {
      kicker: '已查看',
      title: '已查看未处理',
      hint: '这些任务已打开过，但还没有进入正式处理状态。',
    },
    done: {
      kicker: '已完成',
      title: '已完成任务',
      hint: '这里保留已完成事项，方便回看对应会议和历史备注。',
    },
    all: {
      kicker: '全部视图',
      title: '全部任务',
      hint: '按优先级、截止时间和处理状态综合排序，便于连续处理。',
    },
  }[key]
}

const filters = computed(() => [
  { val: 'all', label: '全部', count: todos.value.length },
  { val: 'pending', label: '待处理', count: todos.value.filter((item) => displayStatus(item) === 'pending').length },
  { val: 'viewed', label: '已查看', count: todos.value.filter((item) => displayStatus(item) === 'viewed').length },
  { val: 'in_progress', label: '进行中', count: todos.value.filter((item) => displayStatus(item) === 'in_progress').length },
  { val: 'done', label: '已完成', count: todos.value.filter((item) => displayStatus(item) === 'done').length },
])

const filtered = computed(() => {
  if (currentFilter.value === 'all') return todos.value
  return todos.value.filter((item) => displayStatus(item) === currentFilter.value)
})

const overdueCount = computed(() => todos.value.filter((item) => isOverdue(item)).length)
const todayCount = computed(() => todos.value.filter((item) => item.status !== 'done' && isToday(item.due_date)).length)
const inProgressCount = computed(() => todos.value.filter((item) => item.status === 'in_progress').length)
const doneCount = computed(() => todos.value.filter((item) => item.status === 'done').length)
const completionRatio = computed(() => {
  if (!todos.value.length) return 0
  return Math.round((doneCount.value / todos.value.length) * 100)
})
const currentFilterLabel = computed(() => filters.value.find((item) => item.val === currentFilter.value)?.label || '全部')

const focusTodo = computed(() => {
  const activeTodos = todos.value.filter((item) => item.status !== 'done')
  const ranked = [...activeTodos].sort((left, right) => priorityScore(left) - priorityScore(right))
  return ranked[0] || todos.value.find((item) => item.status === 'done') || null
})

const focusHint = computed(() => {
  if (!focusTodo.value) return ''
  if (isOverdue(focusTodo.value)) return '这项任务已逾期，建议优先补充进度或调整截止时间。'
  if (isToday(focusTodo.value.due_date)) return '这项任务今天截止，建议先处理并同步最新结果。'
  if (focusTodo.value.status === 'in_progress') return '这项任务已经开始处理，适合继续补充说明并推进完成。'
  return '这项任务还未开始，建议先确认处理路径和责任人。'
})

const visibleGroups = computed(() => {
  if (currentFilter.value === 'all') {
    if (!todos.value.length) return []
    const items = [...todos.value].sort((left, right) => {
      const scoreDiff = priorityScore(left) - priorityScore(right)
      if (scoreDiff !== 0) return scoreDiff

      const leftDue = normalizeDate(left.due_date)
      const rightDue = normalizeDate(right.due_date)
      if (leftDue && rightDue) {
        const timeDiff = leftDue.getTime() - rightDue.getTime()
        if (timeDiff !== 0) return timeDiff
      } else if (leftDue && !rightDue) {
        return -1
      } else if (!leftDue && rightDue) {
        return 1
      }

      const completedDiff = Number(Boolean(right.completed_at)) - Number(Boolean(left.completed_at))
      if (completedDiff !== 0) return completedDiff

      return String(left.id).localeCompare(String(right.id))
    })
    return [{
      key: 'all',
      items,
      ...laneMeta('all'),
    }]
  }

  if (currentFilter.value !== 'all') {
    const items = filtered.value
    if (!items.length) return []
    return [{
      key: currentFilter.value,
      items,
      ...laneMeta(currentFilter.value),
    }]
  }

  return []
})

function priorityScore(item) {
  if (isOverdue(item)) return 0
  if (isToday(item.due_date)) return 1
  if (item.status === 'in_progress') return 2
  if (displayStatus(item) === 'pending') return 3
  if (displayStatus(item) === 'viewed') return 4
  return 5
}

async function loadTodos() {
  loading.value = true
  try {
    const res = await api.get('/todos')
    todos.value = res.data
  } catch (error) {
    ElMessage.error('待办加载失败：' + (error.response?.data?.detail || error.message))
  } finally {
    loading.value = false
  }
}

async function updateStatus(item, status) {
  try {
    await api.patch('/todos/' + item.id, { status })
    item.status = status
    item.is_viewed = true
    item.viewed_at = item.viewed_at || new Date().toISOString()
    item.completed_at = status === 'done' ? new Date().toISOString() : null
    ElMessage.success(status === 'done' ? '已标记为完成' : '任务已更新为进行中')
  } catch (error) {
    ElMessage.error('操作失败：' + (error.response?.data?.detail || error.message))
  }
}

function todoTransitionName(id) {
  return `todo-action-${id}`
}

function todoTransitionStyle(item) {
  if (String(transitioningTodoId.value) !== String(item.id)) return {}
  return { viewTransitionName: todoTransitionName(item.id) }
}

function supportsViewTransition() {
  return typeof document !== 'undefined' && 'startViewTransition' in document
}

async function goToTodoDetail(item) {
  await router.push({
    path: '/meetings/' + item.meeting_id,
    query: {
      from: 'todo',
      tab: 'actions',
      readonly: '1',
      actionId: String(item.id),
    },
  })
}

async function openTodo(item) {
  try {
    if (!item.is_viewed) {
      await api.patch('/todos/' + item.id, { viewed: true })
      item.is_viewed = true
      item.viewed_at = new Date().toISOString()
    }
  } catch {
  }

  if (supportsViewTransition()) {
    transitioningTodoId.value = String(item.id)
    const transition = document.startViewTransition(() => goToTodoDetail(item))
    transition.finished.finally(() => {
      transitioningTodoId.value = ''
    })
    return
  }

  await goToTodoDetail(item)
}

function openNoteDialog(item) {
  activeTodo.value = item
  noteForm.value = { progress_note: item.progress_note || '' }
  noteDialogVisible.value = true
}

async function saveNote() {
  if (!activeTodo.value) return
  savingNote.value = true
  try {
    await api.patch('/todos/' + activeTodo.value.id, {
      progress_note: noteForm.value.progress_note,
      viewed: true,
    })
    activeTodo.value.progress_note = noteForm.value.progress_note.trim()
    activeTodo.value.is_viewed = true
    activeTodo.value.viewed_at = activeTodo.value.viewed_at || new Date().toISOString()
    noteDialogVisible.value = false
    ElMessage.success('进度备注已保存')
  } catch (error) {
    ElMessage.error('保存失败：' + (error.response?.data?.detail || error.message))
  } finally {
    savingNote.value = false
  }
}

function dueCls(item) {
  if (isOverdue(item)) return 'overdue'
  if (isToday(item.due_date)) return 'urgent'
  return ''
}

function dueLabel(item) {
  const due = normalizeDate(item.due_date)
  if (!due) return ''
  const days = Math.ceil((startOfDay(due).getTime() - startOfDay(new Date()).getTime()) / 86400000)
  if (days < 0) return '(已逾期)'
  if (days === 0) return '(今天截止)'
  return `(${days} 天后截止)`
}

onMounted(loadTodos)
</script>

<style scoped>
.todos-page { padding: clamp(20px, 3vw, 32px); max-width: 1320px; margin: 0 auto; min-height: 100vh; height: 100vh; display: flex; flex-direction: column; overflow: hidden; box-sizing: border-box; }
.page-header { display: flex; align-items: end; justify-content: space-between; margin-bottom: 24px; flex-wrap: wrap; gap: 18px; padding-bottom: 18px; border-bottom: 1px solid var(--border); }
.header-copy { max-width: 760px; }
.page-eyebrow { margin-bottom: 10px; font-size: 12px; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; color: var(--text-muted); }
.page-title { font-size: clamp(28px, 4vw, 44px); font-weight: 800; color: var(--text); letter-spacing: -.04em; }
.page-sub { margin-top: 10px; color: var(--text-muted); line-height: 1.7; max-width: 46rem; }
.filter-tabs { display: flex; gap: 8px; flex-wrap: wrap; }
.filter-tab { padding: 10px 16px; border-radius: 999px; border: 1px solid var(--border); background: transparent; color: var(--text-muted); font-size: 13px; font-weight: 600; cursor: pointer; transition: all .18s ease; display: flex; align-items: center; gap: 8px; }
.filter-tab:hover { transform: translateY(-1px); border-color: color-mix(in oklab, var(--primary) 20%, var(--border)); }
.filter-tab.active { background: color-mix(in oklab, var(--primary) 10%, transparent); border-color: color-mix(in oklab, var(--primary) 28%, var(--border)); color: var(--text); }
.tab-count { min-width: 22px; height: 22px; border-radius: 999px; padding: 0 7px; display: inline-flex; align-items: center; justify-content: center; background: color-mix(in oklab, var(--primary) 16%, transparent); color: var(--text); font-size: 11px; }
.stats-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; margin-bottom: 18px; }
.stat-card { position: relative; display: flex; align-items: stretch; gap: 14px; min-height: 108px; padding: 18px; border-radius: 22px; border: 1px solid var(--border); background: color-mix(in oklab, var(--bg-card) 86%, var(--bg) 14%); overflow: hidden; }
.stat-card.overdue { border-color: color-mix(in oklab, var(--danger) 28%, var(--border)); background: color-mix(in oklab, var(--danger) 8%, var(--bg-card)); }
.stat-card.today { border-color: color-mix(in oklab, var(--warning) 28%, var(--border)); background: color-mix(in oklab, var(--warning) 8%, var(--bg-card)); }
.stat-card.active { border-color: color-mix(in oklab, var(--accent) 28%, var(--border)); background: color-mix(in oklab, var(--accent) 8%, var(--bg-card)); }
.stat-accent { width: 6px; border-radius: 999px; align-self: stretch; background: color-mix(in oklab, currentColor 72%, transparent); opacity: .88; }
.stat-card.overdue .stat-accent { color: var(--danger); }
.stat-card.today .stat-accent { color: var(--warning); }
.stat-card.active .stat-accent { color: var(--accent); }
.stat-main { flex: 1; display: flex; flex-direction: column; justify-content: space-between; gap: 14px; }
.stat-value-wrap { display: flex; align-items: end; gap: 12px; flex-wrap: wrap; }
.stat-label { font-size: 14px; font-weight: 700; color: var(--text); line-height: 1.2; padding-bottom: 4px; }
.stat-value { font-size: clamp(34px, 4vw, 42px); font-weight: 800; color: var(--text); line-height: .95; letter-spacing: -.04em; min-width: 1.5em; }
.stat-hint { font-size: 12px; line-height: 1.6; color: var(--text-muted); max-width: 22em; }
.focus-panel { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 18px; align-items: end; padding: 20px 22px; margin-bottom: 18px; border-radius: 24px; border: 1px solid color-mix(in oklab, var(--primary) 18%, var(--border)); background: linear-gradient(135deg, color-mix(in oklab, var(--primary) 8%, var(--bg-card)) 0%, color-mix(in oklab, var(--bg-card) 92%, var(--bg) 8%) 100%); box-shadow: var(--shadow); }
.focus-kicker { font-size: 12px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; color: var(--text-soft); margin-bottom: 10px; }
.focus-panel h2 { font-size: clamp(20px, 2.6vw, 30px); line-height: 1.18; letter-spacing: -.04em; color: var(--text); max-width: 22ch; }
.focus-meta { display: flex; gap: 8px 10px; flex-wrap: wrap; margin-top: 14px; align-items: center; }
.focus-meta__item { color: var(--text-muted); font-size: 12px; }
.focus-note { margin-top: 12px; color: var(--text-muted); line-height: 1.7; max-width: 56ch; }
.focus-panel__actions { display: flex; gap: 10px; flex-wrap: wrap; justify-content: flex-end; }
.alert-strip { display: flex; align-items: center; gap: 8px; padding: 12px 16px; margin-bottom: 18px; border-radius: 16px; border: 1px solid color-mix(in oklab, var(--danger) 30%, var(--border)); background: color-mix(in oklab, var(--danger) 10%, var(--bg-card)); color: var(--danger); }
.loading-wrap,
.empty-wrap { min-height: 0; flex: 1; display: grid; place-items: center; }
.empty-wrap { text-align: center; padding: 40px; color: var(--text-muted); border: 1px dashed var(--border); border-radius: 28px; }
.empty-icon { color: var(--success); margin-bottom: 12px; }
.todo-workbench { border: 1px solid color-mix(in oklab, var(--primary) 12%, var(--border)); border-radius: 28px; background: radial-gradient(circle at top right, color-mix(in oklab, var(--primary) 8%, transparent), transparent 34%), linear-gradient(180deg, color-mix(in oklab, var(--bg-card) 94%, var(--bg) 6%) 0%, color-mix(in oklab, var(--bg-card) 88%, var(--bg) 12%) 100%); box-shadow: 0 24px 48px color-mix(in oklab, #081223 8%, transparent), var(--shadow); display: flex; flex: 1; min-height: 0; overflow: hidden; padding: 18px; }
.todo-lanes { display: grid; gap: 18px; min-height: 0; flex: 1; overflow: hidden; width: 100%; }
.todo-lane { display: flex; flex-direction: column; min-height: 0; overflow: hidden; }
.todo-lane--overdue { border-color: color-mix(in oklab, var(--danger) 26%, var(--border)); }
.todo-lane--today { border-color: color-mix(in oklab, var(--warning) 26%, var(--border)); }
.todo-lane--in_progress { border-color: color-mix(in oklab, var(--accent) 24%, var(--border)); }
.todo-lane__header { display: flex; align-items: center; justify-content: space-between; gap: 18px; padding-bottom: 18px; margin-bottom: 18px; border-bottom: 1px solid color-mix(in oklab, var(--primary) 10%, var(--border)); }
.todo-lane__intro { min-width: 0; }
.todo-lane__kicker { font-size: 12px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; color: var(--text-soft); margin-bottom: 8px; }
.todo-lane__header h2 { font-size: clamp(20px, 2.2vw, 28px); line-height: 1.08; letter-spacing: -.04em; color: var(--text); }
.todo-lane__header p { margin-top: 8px; color: var(--text-muted); line-height: 1.6; max-width: 40rem; }
.todo-lane__summary { min-width: 88px; padding: 10px 12px; border-radius: 18px; background: color-mix(in oklab, var(--primary) 8%, transparent); display: flex; flex-direction: column; align-items: center; justify-content: center; }
.todo-lane__count { line-height: 1; color: var(--text); font-weight: 800; font-size: 1.2rem; }
.todo-lane__summary-label { margin-top: 4px; font-size: 11px; color: var(--text-soft); }
.todo-list { display: flex; flex-direction: column; gap: 14px; flex: 1; min-height: 0; overflow: auto; padding-right: 8px; }
.todo-list::-webkit-scrollbar { width: 8px; }
.todo-list::-webkit-scrollbar-thumb { background: color-mix(in oklab, var(--primary) 18%, var(--border)); border-radius: 999px; }
.todo-card { background: linear-gradient(180deg, color-mix(in oklab, var(--bg) 84%, var(--bg-card) 16%) 0%, color-mix(in oklab, var(--bg) 74%, var(--bg-card) 26%) 100%); border: 1px solid color-mix(in oklab, var(--primary) 10%, var(--border)); border-radius: 24px; padding: 20px 22px; display: flex; align-items: flex-start; gap: 16px; transition: border-color .18s ease, box-shadow .18s ease, transform .18s ease, background .18s ease; }
.todo-card:hover { transform: translateY(-2px); border-color: color-mix(in oklab, var(--primary) 28%, var(--border)); box-shadow: 0 18px 36px color-mix(in oklab, var(--primary) 10%, transparent); background: linear-gradient(180deg, color-mix(in oklab, var(--bg) 90%, var(--bg-card) 10%) 0%, color-mix(in oklab, var(--bg) 78%, var(--bg-card) 22%) 100%); }
.todo-card.overdue { border-color: color-mix(in oklab, var(--danger) 34%, var(--border)); box-shadow: 0 12px 24px color-mix(in oklab, var(--danger) 12%, transparent); }
.todo-status-dot { width: 12px; height: 12px; border-radius: 999px; margin-top: 8px; flex-shrink: 0; background: var(--text-muted); }
.todo-status-dot.pending { background: var(--warning); }
.todo-status-dot.viewed { background: var(--primary); }
.todo-status-dot.in_progress { background: var(--accent); }
.todo-status-dot.done { background: var(--success); }
.todo-body { flex: 1; min-width: 0; }
.todo-top { display: flex; justify-content: space-between; gap: 14px; align-items: start; }
.todo-content { font-size: 15px; color: var(--text); margin-bottom: 10px; line-height: 1.65; font-weight: 600; }
.todo-content.striked { text-decoration: line-through; color: var(--text-muted); font-weight: 500; }
.todo-tags { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 10px; }
.status-badge, .flag-badge { display: inline-flex; align-items: center; min-height: 28px; padding: 0 12px; border-radius: 999px; font-size: 12px; font-weight: 700; border: 1px solid var(--border); }
.status-badge.pending { color: var(--warning); background: color-mix(in oklab, var(--warning) 12%, transparent); }
.status-badge.viewed { color: var(--primary); background: color-mix(in oklab, var(--primary) 12%, transparent); }
.status-badge.in_progress { color: var(--accent); background: color-mix(in oklab, var(--accent) 12%, transparent); }
.status-badge.done { color: var(--success); background: color-mix(in oklab, var(--success) 12%, transparent); }
.flag-badge.overdue { color: var(--danger); background: color-mix(in oklab, var(--danger) 10%, transparent); border-color: color-mix(in oklab, var(--danger) 20%, var(--border)); }
.flag-badge.today { color: var(--warning); background: color-mix(in oklab, var(--warning) 10%, transparent); }
.flag-badge.note { color: var(--text); background: color-mix(in oklab, var(--primary) 8%, transparent); }
.todo-meta { display: flex; gap: 10px; flex-wrap: wrap; }
.meta-item { display: inline-flex; align-items: center; gap: 5px; font-size: 12px; color: var(--text-muted); min-height: 30px; padding: 0 10px; border-radius: 999px; background: color-mix(in oklab, var(--bg-card) 82%, var(--bg) 18%); border: 1px solid color-mix(in oklab, var(--primary) 8%, var(--border)); }
.meta-item.urgent, .focus-meta__item.urgent { color: var(--warning); }
.meta-item.overdue, .focus-meta__item.overdue { color: var(--danger); }
.note-preview { margin-top: 14px; padding: 14px 16px; border-radius: 16px; background: color-mix(in oklab, var(--primary) 6%, var(--bg-card)); border: 1px solid color-mix(in oklab, var(--primary) 16%, var(--border)); }
.note-title { font-size: 12px; color: var(--text-muted); margin-bottom: 8px; }
.note-content { color: var(--text); line-height: 1.7; white-space: pre-wrap; }
.todo-actions { flex-shrink: 0; display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
.note-dialog { display: flex; flex-direction: column; gap: 16px; }
.note-dialog-item { display: flex; flex-direction: column; gap: 8px; }
.note-dialog-label { font-size: 13px; font-weight: 700; color: var(--text); }
.note-dialog-value { color: var(--text-muted); line-height: 1.7; }
@media (prefers-reduced-motion: reduce) {
  .filter-tab,
  .todo-card { transition: none; }
}
@media (max-width: 1100px) {
  .todos-page { height: auto; min-height: 100vh; overflow: visible; }
  .todo-workbench { overflow: visible; padding: 16px; }
  .todo-lanes { height: auto; overflow: visible; max-height: none; }
  .todo-lane,
  .todo-list { min-height: unset; }
  .todo-lane { overflow: visible; }
  .todo-list { overflow: visible; padding-right: 0; }
}
@media (max-width: 920px) {
  .stats-grid { grid-template-columns: 1fr; }
  .focus-panel { grid-template-columns: 1fr; }
  .focus-panel__actions { justify-content: flex-start; }
}
@media (max-width: 760px) {
  .todo-lane__header,
  .todo-card { grid-template-columns: 1fr; display: grid; }
  .todo-lane__summary { width: 100%; }
  .todo-actions { width: 100%; justify-content: flex-start; }
  .todo-top { flex-direction: column; }
}
</style>
