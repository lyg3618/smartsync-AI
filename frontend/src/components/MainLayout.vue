<template>
  <div class="layout" :class="{ 'layout--collapsed': isCollapsed }">
    <aside class="sidebar" :class="{ 'sidebar--collapsed': isCollapsed }">
      <div class="sidebar-shell">
        <div class="sidebar-brand-row">
          <div class="brand-mark" aria-hidden="true">
            <span class="brand-mark__stroke"></span>
            <span class="brand-mark__stroke brand-mark__stroke--short"></span>
          </div>
          <div class="brand-copy">
            <div class="brand-text">AI会议助手</div>
            <div class="brand-sub">{{ dailyPulse }}</div>
          </div>
        </div>

        <nav class="sidebar-nav">
          <el-tooltip content="会议中心" placement="right" :disabled="!isCollapsed">
            <router-link to="/dashboard" class="nav-item" :class="{ active: $route.path === '/dashboard' }">
              <el-icon><House /></el-icon>
              <div class="nav-copy">
                <span class="nav-label">会议中心</span>
                <span class="nav-note">上传、确认、分发</span>
              </div>
            </router-link>
          </el-tooltip>

          <el-tooltip content="全文搜索" placement="right" :disabled="!isCollapsed">
            <router-link to="/search" class="nav-item" :class="{ active: $route.path === '/search' }">
              <el-icon><Search /></el-icon>
              <div class="nav-copy">
                <span class="nav-label">全文搜索</span>
                <span class="nav-note">定位会议内容</span>
              </div>
            </router-link>
          </el-tooltip>

          <el-tooltip content="我的待办" placement="right" :disabled="!isCollapsed">
            <router-link to="/todos" class="nav-item" :class="{ active: $route.path === '/todos' }">
              <el-icon><Bell /></el-icon>
              <div class="nav-copy">
                <span class="nav-label">我的待办</span>
                <span class="nav-note">跟进负责事项</span>
              </div>
              <span v-if="pendingCount > 0" class="nav-badge">{{ pendingCount }}</span>
            </router-link>
          </el-tooltip>

          <el-tooltip content="消息中心" placement="right" :disabled="!isCollapsed">
            <router-link to="/messages" class="nav-item" :class="{ active: $route.path === '/messages' }">
              <el-icon><ChatDotRound /></el-icon>
              <div class="nav-copy">
                <span class="nav-label">消息中心</span>
                <span class="nav-note">查看系统提醒</span>
              </div>
              <span v-if="unreadCount > 0" class="nav-badge">{{ unreadCount }}</span>
            </router-link>
          </el-tooltip>

          <el-tooltip content="系统设置" placement="right" :disabled="!isCollapsed">
            <router-link to="/settings" class="nav-item" :class="{ active: $route.path === '/settings' }">
              <el-icon><Setting /></el-icon>
              <div class="nav-copy">
                <span class="nav-label">系统设置</span>
                <span class="nav-note">账号与配置</span>
              </div>
            </router-link>
          </el-tooltip>
        </nav>
      </div>

      <button class="sidebar-handle" type="button" @click="toggleSidebar" :title="isCollapsed ? '展开侧栏' : '收起侧栏'">
        <el-icon><Fold v-if="!isCollapsed" /><Expand v-else /></el-icon>
      </button>

      <div class="sidebar-footer">
        <div class="user-info">
          <div class="user-avatar">{{ userInitial }}</div>
          <div class="user-copy">
            <div class="user-name">{{ userName }}</div>
            <div class="user-role">{{ userRole }}</div>
          </div>
        </div>

        <div class="footer-actions">
          <el-button text class="theme-toggle-btn" @click="toggleTheme" :title="isDark ? '切换为浅色模式' : '切换为深色模式'">
            <el-icon><Sunny v-if="isDark" /><Moon v-else /></el-icon>
          </el-button>
          <el-button text class="logout-btn" @click="logout">
            <el-icon><SwitchButton /></el-icon>
          </el-button>
        </div>
      </div>
    </aside>

    <main class="main-content">
      <div class="content-shell">
        <slot />
      </div>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Moon, Sunny, Fold, Expand, Search, ChatDotRound } from '@element-plus/icons-vue'
import api from '../services/api.js'

const router = useRouter()
const pendingCount = ref(0)
const unreadCount = ref(0)
const isDark = ref(false)
const isCollapsed = ref(false)

function applyTheme(dark) {
  isDark.value = dark
  document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light')
  localStorage.setItem('smartsync_theme', dark ? 'dark' : 'light')
}

function toggleTheme() {
  applyTheme(!isDark.value)
}

function toggleSidebar() {
  isCollapsed.value = !isCollapsed.value
  localStorage.setItem('smartsync_sidebar_collapsed', isCollapsed.value ? '1' : '0')
}

const user = computed(() => {
  try {
    return JSON.parse(localStorage.getItem('smartsync_user') || '{}')
  } catch {
    return {}
  }
})

const userName = computed(() => user.value.name || '管理员')
const userInitial = computed(() => userName.value.charAt(0).toUpperCase())
const userRole = computed(() => (user.value.role === 'admin' ? '管理员' : (user.value.name || '成员')))
const dailyPulse = computed(() => {
  const hour = new Date().getHours()
  if (hour < 11) return '早上好，先看今天的新会议'
  if (hour < 14) return '中午好，记得确认待分发内容'
  if (hour < 18) return '下午好，继续推进会议事项'
  return '晚上好，收一下今天的进展'
})

async function loadPendingCount() {
  try {
    const res = await api.get('/todos', { params: { status: 'pending' } })
    pendingCount.value = res.data.length
  } catch {}
}

async function loadUnreadCount() {
  try {
    const res = await api.get('/notifications', { params: { unread_only: true, limit: 1 } })
    unreadCount.value = res.data.unread_count || 0
  } catch {}
}

function logout() {
  localStorage.removeItem('smartsync_token')
  localStorage.removeItem('smartsync_user')
  ElMessage.success('已安全退出')
  router.push('/login')
}

onMounted(() => {
  const savedTheme = localStorage.getItem('smartsync_theme') || 'light'
  applyTheme(savedTheme === 'dark')
  isCollapsed.value = localStorage.getItem('smartsync_sidebar_collapsed') === '1'
  loadPendingCount()
  loadUnreadCount()
})
</script>

<style scoped>
.layout {
  min-height: 100vh;
  --sidebar-width: 272px;
  --sidebar-collapsed-width: 94px;
}

.sidebar {
  position: fixed;
  inset: 0 auto 0 0;
  z-index: 30;
  width: var(--sidebar-width);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 24px 18px 18px;
  background: color-mix(in oklab, var(--bg-sidebar) 94%, var(--bg) 6%);
  border-right: 1px solid var(--border-soft);
  transition: width 0.22s ease, padding 0.22s ease;
}

.sidebar--collapsed {
  width: var(--sidebar-collapsed-width);
  padding-inline: 12px;
}

.sidebar-shell {
  display: flex;
  flex-direction: column;
  gap: 28px;
}

.sidebar-brand-row {
  display: flex;
  align-items: center;
  gap: 14px;
  padding-inline: 8px;
  min-height: 44px;
}

.brand-mark {
  width: 36px;
  height: 36px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  gap: 4px;
  background: color-mix(in oklab, var(--primary) 10%, var(--bg-elevated));
  border: 1px solid color-mix(in oklab, var(--primary) 16%, var(--border));
  flex-shrink: 0;
  transition: transform 0.18s ease, background 0.18s ease, border-color 0.18s ease;
}

.brand-mark__stroke {
  width: 16px;
  height: 2px;
  border-radius: 999px;
  background: var(--text);
  transition: transform 0.18s ease, opacity 0.18s ease;
}

.brand-mark__stroke--short {
  width: 10px;
  opacity: 0.72;
}

.brand-copy,
.user-copy,
.nav-copy {
  min-width: 0;
}

.brand-text {
  font-size: 16px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--text);
}

.brand-sub {
  margin-top: 2px;
  font-size: 12px;
  color: var(--text-soft);
}

.sidebar-brand-row:hover .brand-mark {
  transform: translateY(-1px);
  background: color-mix(in oklab, var(--primary) 14%, var(--bg-elevated));
  border-color: color-mix(in oklab, var(--primary) 22%, var(--border));
}

.sidebar-brand-row:hover .brand-mark__stroke:first-child {
  transform: translateX(1px);
}

.sidebar-brand-row:hover .brand-mark__stroke--short {
  transform: translateX(-1px);
}

.sidebar-nav {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.nav-item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 56px;
  padding: 0 14px;
  border-radius: 14px;
  border: 1px solid transparent;
  color: var(--text-muted);
  transition: background 0.18s ease, border-color 0.18s ease, color 0.18s ease, transform 0.18s ease;
}

.nav-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 10px;
  bottom: 10px;
  width: 3px;
  border-radius: 999px;
  background: transparent;
}

.nav-item:hover {
  color: var(--text);
  background: color-mix(in oklab, var(--bg-elevated) 92%, var(--bg) 8%);
  border-color: var(--border-soft);
  transform: translateX(2px);
}

.nav-item.active {
  color: var(--text);
  background: color-mix(in oklab, var(--primary) 7%, var(--bg-elevated));
  border-color: color-mix(in oklab, var(--primary) 18%, var(--border));
}

.nav-item.active::before {
  background: var(--primary);
}

.nav-item.active .el-icon {
  color: var(--primary);
}

.nav-label {
  display: block;
  font-size: 14px;
  font-weight: 700;
  color: currentColor;
}

.nav-note {
  display: block;
  margin-top: 2px;
  font-size: 12px;
  color: var(--text-soft);
}

.nav-badge {
  margin-left: auto;
  min-width: 24px;
  height: 24px;
  padding: 0 7px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: color-mix(in oklab, var(--primary) 16%, transparent);
  color: var(--text);
  font-size: 11px;
  font-weight: 700;
}

.sidebar-handle {
  position: absolute;
  top: 28px;
  right: -15px;
  width: 30px;
  height: 56px;
  border-radius: 16px;
  border: 1px solid var(--border-soft);
  background: var(--bg-elevated);
  color: var(--text-soft);
  display: grid;
  place-items: center;
  box-shadow: var(--shadow-sm);
  cursor: pointer;
  transition: transform 0.18s ease, color 0.18s ease;
}

.sidebar-handle:hover {
  color: var(--text);
  transform: translateX(2px);
}

.sidebar-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 16px 10px 8px;
  border-top: 1px solid var(--border-soft);
}

.user-info {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.user-avatar {
  width: 36px;
  height: 36px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  background: color-mix(in oklab, var(--primary) 12%, var(--bg-elevated));
  border: 1px solid color-mix(in oklab, var(--primary) 16%, var(--border));
  color: var(--text);
  font-weight: 700;
  flex-shrink: 0;
}

.user-name {
  font-size: 13px;
  font-weight: 700;
  color: var(--text);
}

.user-role {
  margin-top: 2px;
  font-size: 11px;
  color: var(--text-soft);
}

.footer-actions {
  display: flex;
  align-items: center;
  gap: 2px;
}

.logout-btn,
.theme-toggle-btn {
  color: var(--text-muted) !important;
  padding: 8px !important;
}

.logout-btn:hover,
.theme-toggle-btn:hover {
  color: var(--text) !important;
}

.main-content {
  height: 100vh;
  min-height: 100vh;
  margin-left: var(--sidebar-width);
  transition: margin-left 0.22s ease;
  overflow: hidden;
}

.layout--collapsed .main-content {
  margin-left: var(--sidebar-collapsed-width);
}

.content-shell {
  height: 100%;
  min-height: 100vh;
  overflow: auto;
}

.sidebar--collapsed .brand-copy,
.sidebar--collapsed .nav-copy,
.sidebar--collapsed .user-copy {
  display: none;
}

.sidebar--collapsed .sidebar-brand-row {
  justify-content: center;
  padding-inline: 0;
}

.sidebar--collapsed .nav-item {
  justify-content: center;
  padding-inline: 0;
}

.sidebar--collapsed .nav-badge {
  position: absolute;
  top: 8px;
  right: 8px;
  min-width: 18px;
  height: 18px;
  padding: 0 4px;
  font-size: 10px;
}

.sidebar--collapsed .user-info {
  justify-content: center;
}

.sidebar--collapsed .sidebar-footer {
  flex-direction: column;
  gap: 10px;
}

@media (max-width: 1024px) {
  .layout {
    --sidebar-width: 234px;
  }
}

@media (max-width: 760px) {
  .sidebar {
    position: sticky;
    inset: 0 0 auto 0;
    width: 100%;
    padding: 14px 14px 12px;
    border-right: none;
    border-bottom: 1px solid var(--border-soft);
  }

  .sidebar--collapsed {
    width: 100%;
  }

  .sidebar-handle {
    display: none;
  }

  .main-content,
  .layout--collapsed .main-content {
    margin-left: 0;
  }

  .sidebar--collapsed .brand-copy,
  .sidebar--collapsed .nav-copy,
  .sidebar--collapsed .user-copy {
    display: block;
  }

  .sidebar-nav {
    gap: 8px;
  }

  .sidebar-footer {
    padding-bottom: 0;
  }
}
</style>
