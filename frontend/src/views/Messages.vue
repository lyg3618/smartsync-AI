<template>
  <MainLayout>
    <div class="messages-page">
      <header class="messages-header">
        <div>
          <div class="messages-kicker">消息中心</div>
          <h1>消息中心</h1>
        </div>

        <div class="messages-actions">
          <el-switch v-model="unreadOnly" inline-prompt active-text="未读" inactive-text="全部" @change="loadNotifications" />
          <el-button @click="loadNotifications">刷新</el-button>
          <el-button type="primary" :disabled="!unreadCount" @click="markAllRead">全部标记已读</el-button>
        </div>
      </header>

      <section class="message-strip">
        <div class="strip-tile">
          <span>未读消息</span>
          <strong>{{ unreadCount }}</strong>
        </div>
        <div class="strip-tile">
          <span>当前视图</span>
          <strong>{{ unreadOnly ? '仅未读' : '全部消息' }}</strong>
        </div>
      </section>

      <section class="message-list-shell">
        <div v-if="loading" class="loading-state">
          <div class="progress-spinner large"></div>
          <p>正在加载消息...</p>
        </div>

        <div v-else-if="items.length" class="message-list">
          <article v-for="item in items" :key="item.id" class="message-card" :class="{ 'message-card--unread': !item.is_read }">
            <div class="message-card__top">
              <span class="message-type">{{ categoryLabel(item.category) }}</span>
              <span class="message-time">{{ formatTime(item.created_at) }}</span>
            </div>
            <h2>{{ item.title }}</h2>
            <p>{{ item.content }}</p>
            <div class="message-card__actions">
              <el-button v-if="item.related_type === 'meeting' && item.related_id" text @click="goMeeting(item.related_id)">查看会议</el-button>
              <el-button v-if="!item.is_read" text type="primary" @click="markRead(item)">标记已读</el-button>
            </div>
          </article>
        </div>

        <div v-else class="empty-state">当前没有消息。</div>
      </section>
    </div>
  </MainLayout>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import MainLayout from '../components/MainLayout.vue'
import api from '../services/api.js'

const router = useRouter()
const loading = ref(false)
const unreadOnly = ref(false)
const unreadCount = ref(0)
const items = ref([])

function categoryLabel(category) {
  return {
    meeting: '会议',
    dispatch: '分发',
    warning: '提醒',
    system: '系统',
  }[category] || '通知'
}

function formatTime(value) {
  if (!value) return '刚刚'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return `${date.getMonth() + 1}/${date.getDate()} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

function goMeeting(id) {
  router.push(`/meetings/${id}`)
}

async function loadNotifications() {
  loading.value = true
  try {
    const res = await api.get('/notifications', { params: { unread_only: unreadOnly.value } })
    items.value = res.data.items || []
    unreadCount.value = res.data.unread_count || 0
  } catch (error) {
    ElMessage.error('加载消息失败：' + (error.response?.data?.detail || error.message))
  } finally {
    loading.value = false
  }
}

async function markRead(item) {
  try {
    await api.patch(`/notifications/${item.id}/read`)
    item.is_read = true
    unreadCount.value = Math.max(0, unreadCount.value - 1)
  } catch (error) {
    ElMessage.error('标记失败：' + (error.response?.data?.detail || error.message))
  }
}

async function markAllRead() {
  try {
    await api.post('/notifications/read-all')
    items.value = items.value.map(item => ({ ...item, is_read: true }))
    unreadCount.value = 0
    ElMessage.success('已全部标记为已读')
  } catch (error) {
    ElMessage.error('操作失败：' + (error.response?.data?.detail || error.message))
  }
}

onMounted(loadNotifications)
</script>

<style scoped>
.messages-page { padding: clamp(20px, 3vw, 32px); max-width: 1180px; margin: 0 auto; min-height: 100vh; height: 100vh; display: flex; flex-direction: column; overflow: hidden; box-sizing: border-box; }
.messages-header { display: flex; align-items: end; justify-content: space-between; gap: 20px; margin-bottom: 18px; flex-shrink: 0; }
.messages-kicker { font-size: 12px; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; color: var(--text-muted); margin-bottom: 10px; }
.messages-header h1 { font-size: clamp(34px, 5vw, 52px); letter-spacing: -.05em; color: var(--text); margin-bottom: 10px; }
.messages-header p { color: var(--text-muted); line-height: 1.7; }
.messages-actions { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.message-strip { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin-bottom: 16px; flex-shrink: 0; }
.strip-tile, .message-list-shell { border: 1px solid var(--border); background: color-mix(in oklab, var(--bg-card) 88%, var(--bg) 12%); border-radius: 24px; box-shadow: var(--shadow); }
.strip-tile { padding: 18px 20px; }
.strip-tile span { display: block; font-size: 12px; color: var(--text-muted); margin-bottom: 8px; }
.strip-tile strong { font-size: 28px; color: var(--text); }
.message-list-shell { padding: 18px; min-height: 0; flex: 1; overflow: hidden; display: flex; flex-direction: column; }
.message-list { display: flex; flex-direction: column; gap: 12px; min-height: 0; overflow: auto; padding-right: 4px; }
.message-card { border: 1px solid var(--border); background: color-mix(in oklab, var(--bg) 84%, var(--bg-card) 16%); border-radius: 20px; padding: 18px; }
.message-card--unread { border-color: color-mix(in oklab, var(--primary) 36%, var(--border)); background: color-mix(in oklab, var(--primary) 6%, var(--bg-card)); }
.message-card__top, .message-card__actions { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.message-card__top { margin-bottom: 12px; }
.message-type { display: inline-flex; align-items: center; min-height: 28px; padding: 0 10px; border-radius: 999px; background: color-mix(in oklab, var(--primary) 10%, transparent); color: var(--text); font-size: 12px; font-weight: 700; }
.message-time { color: var(--text-muted); font-size: 12px; }
.message-card h2 { font-size: 18px; color: var(--text); margin-bottom: 10px; }
.message-card p { color: var(--text); line-height: 1.7; margin-bottom: 14px; }
.empty-state, .loading-state { min-height: 0; flex: 1; display: grid; place-items: center; color: var(--text-muted); }
@media (max-width: 860px) { .messages-header, .message-strip { grid-template-columns: 1fr; display: grid; } .messages-actions { justify-content: flex-start; } }
</style>
