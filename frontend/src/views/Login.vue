<template>
  <div class="login-page">
    <div class="login-grid">
      <section class="login-intro fade-slide-up">
        <div class="intro-mark">
          <div class="intro-mark__bar"></div>
          <div class="intro-mark__bar intro-mark__bar--short"></div>
        </div>
        <div class="intro-copy">
          <div class="intro-eyebrow">SmartSync</div>
          <h1>AI 会议助手</h1>
        </div>
      </section>

      <section class="login-panel fade-slide-up">
        <div class="panel-top">
          <div>
            <div class="panel-kicker">登录</div>
            <h2>登录系统</h2>
          </div>
          <el-button circle @click="toggleTheme" :title="isDark ? '切换到浅色模式' : '切换到深色模式'">
            <el-icon><Sunny v-if="isDark" /><Moon v-else /></el-icon>
          </el-button>
        </div>

        <el-form :model="form" size="large" @submit.prevent="handleLogin">
          <el-form-item>
            <el-input v-model="form.username" placeholder="请输入用户名" />
          </el-form-item>
          <el-form-item>
            <el-input v-model="form.password" type="password" placeholder="请输入密码" show-password />
          </el-form-item>
          <div v-if="error" class="error-tip">{{ error }}</div>
          <el-button type="primary" native-type="submit" class="login-btn" :loading="loading" size="large">
            登录
          </el-button>
        </el-form>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Sunny, Moon } from '@element-plus/icons-vue'
import api from '../services/api.js'

const router = useRouter()
const loading = ref(false)
const error = ref('')
const form = ref({ username: '', password: '' })
const isDark = ref(false)

function applyTheme(dark) {
  isDark.value = dark
  document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light')
  localStorage.setItem('smartsync_theme', dark ? 'dark' : 'light')
}

function toggleTheme() {
  applyTheme(!isDark.value)
}

async function handleLogin() {
  if (!form.value.username || !form.value.password) {
    error.value = '请输入用户名和密码'
    return
  }
  error.value = ''
  loading.value = true
  try {
    const formData = new URLSearchParams()
    formData.append('username', form.value.username)
    formData.append('password', form.value.password)
    const res = await api.post('/auth/login', formData, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    })
    const { access_token, user } = res.data
    localStorage.setItem('smartsync_token', access_token)
    localStorage.setItem('smartsync_user', JSON.stringify(user))
    ElMessage.success(`登录成功，欢迎回来，${user.name}`)
    router.push('/dashboard')
  } catch (e) {
    const msg = e.response?.data?.detail || '登录失败，请检查用户名和密码'
    error.value = msg
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  const savedTheme = localStorage.getItem('smartsync_theme') || 'light'
  applyTheme(savedTheme === 'dark')
})
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: clamp(24px, 4vw, 48px);
}

.login-grid {
  width: min(1120px, 100%);
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(360px, 440px);
  gap: clamp(20px, 4vw, 44px);
  align-items: stretch;
}

.login-intro,
.login-panel {
  border: 1px solid var(--border);
  background: color-mix(in oklab, var(--bg-card) 85%, var(--bg) 15%);
  box-shadow: var(--shadow);
}

.login-intro {
  border-radius: 34px;
  padding: clamp(28px, 5vw, 52px);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 36px;
}

.intro-mark {
  width: 64px;
  height: 64px;
  border-radius: 22px;
  display: grid;
  place-items: center;
  gap: 6px;
  background: color-mix(in oklab, var(--primary) 14%, var(--bg-card));
  border: 1px solid color-mix(in oklab, var(--primary) 22%, var(--border));
}

.intro-mark__bar {
  width: 22px;
  height: 4px;
  border-radius: 999px;
  background: var(--text);
}

.intro-mark__bar--short {
  width: 14px;
  opacity: 0.72;
}

.intro-eyebrow,
.panel-kicker {
  margin-bottom: 12px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.intro-copy h1 {
  max-width: 9.5em;
  font-size: clamp(42px, 6vw, 72px);
  line-height: 0.98;
  letter-spacing: -0.05em;
  color: var(--text);
}

.login-panel {
  border-radius: 30px;
  padding: 28px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.panel-top {
  display: flex;
  justify-content: space-between;
  align-items: start;
  gap: 16px;
}

.panel-top h2 {
  font-size: 30px;
  letter-spacing: -0.04em;
  color: var(--text);
}

.error-tip {
  margin: -4px 0 14px;
  padding: 12px 14px;
  border-radius: 16px;
  background: color-mix(in oklab, var(--danger) 12%, transparent);
  border: 1px solid color-mix(in oklab, var(--danger) 24%, transparent);
  color: color-mix(in oklab, var(--danger) 76%, white 18%);
  font-size: 13px;
}

.login-btn {
  width: 100%;
  min-height: 48px;
  margin-top: 8px;
}

@media (max-width: 900px) {
  .login-grid {
    grid-template-columns: 1fr;
  }
}
</style>
