<template>
  <MainLayout>
    <div class="settings-page">
      <header class="settings-header">
        <div class="settings-header__copy">
          <div class="page-kicker">系统设置</div>
          <h1>系统设置</h1>
        </div>
      </header>

      <section class="identity-strip">
        <div class="identity-strip__main">
          <div class="identity-avatar">{{ profileInitial }}</div>
          <div>
            <div class="identity-name">{{ profile.name || '未设置姓名' }}</div>
            <div class="identity-meta">{{ profile.email || '未填写邮箱' }}</div>
            <div class="identity-tip">{{ activeTabHint }}</div>
          </div>
        </div>

        <div class="identity-strip__side">
          <span class="identity-stat">
            <em>角色</em>
            <strong>{{ roleLabel }}</strong>
          </span>
        </div>
      </section>

      <section class="settings-shell">
        <aside class="settings-nav">
          <button
            v-for="item in navItems"
            :key="item.value"
            class="settings-nav__item"
            :class="{ active: activeTab === item.value }"
            @click="activeTab = item.value"
          >
            <span class="settings-nav__label">{{ item.label }}</span>
            <span class="settings-nav__note">{{ item.note }}</span>
          </button>
        </aside>

        <div class="settings-panel" :key="activeTab">
          <section v-if="activeTab === 'account'" class="settings-section">

            <div class="form-grid">
              <div class="field field--full">
                <label for="profile-name">显示名称</label>
                <el-input id="profile-name" v-model="profile.name" size="large" placeholder="请输入显示名称" />
              </div>
              <div class="field">
                <label for="profile-role">角色</label>
                <el-input id="profile-role" :model-value="roleLabel" size="large" disabled />
              </div>
              <div class="field">
                <label for="profile-email">邮箱</label>
                <el-input id="profile-email" v-model="profile.email" size="large" placeholder="name@company.com" />
              </div>
            </div>

            <div class="section-actions">
              <el-button type="primary" :loading="savingProfile" @click="saveProfile">保存资料</el-button>
            </div>
          </section>

          <section v-else-if="activeTab === 'security'" class="settings-section">
            <div class="form-grid form-grid--single">
              <div class="field">
                <label for="old-password">当前密码</label>
                <el-input id="old-password" v-model="pwdForm.old_password" type="password" show-password size="large" placeholder="请输入当前密码" />
              </div>
              <div class="field">
                <label for="new-password">新密码</label>
                <el-input id="new-password" v-model="pwdForm.new_password" type="password" show-password size="large" placeholder="请输入新密码" />
              </div>
              <div class="field">
                <label for="confirm-password">确认新密码</label>
                <el-input id="confirm-password" v-model="pwdForm.confirm_password" type="password" show-password size="large" placeholder="请再次输入新密码" />
              </div>
            </div>

            <div class="section-actions">
              <el-button type="primary" :loading="changingPwd" @click="changePassword">更新密码</el-button>
            </div>
          </section>

          <section v-else-if="activeTab === 'notifications'" class="settings-section">
            <div class="settings-list">
              <div v-for="item in notifications" :key="item.key" class="settings-list__row">
                <div>
                  <div class="settings-list__title">{{ item.label }}</div>
                  <div class="settings-list__sub">{{ item.sub }}</div>
                </div>
                <el-switch v-model="item.enabled" />
              </div>
            </div>

            <div class="section-actions">
              <el-button type="primary" @click="saveNotifications">保存偏好</el-button>
            </div>
          </section>

          <section v-else-if="activeTab === 'dispatch'" class="settings-section">

            <div class="form-grid">
              <div class="field field--full">
                <div class="switch-card">
                  <div>
                    <div class="switch-row__title">邮箱发送</div>
                    <div class="switch-row__sub">按负责人聚合行动项，发送任务邮件。</div>
                  </div>
                  <el-switch v-model="dispatchConfig.email_enabled" disabled />
                </div>
              </div>
            </div>

            <div class="section-actions">
              <el-button type="primary" :loading="savingDispatch" @click="saveDispatchConfig">保存邮件配置</el-button>
            </div>
          </section>

          <section v-else-if="activeTab === 'llm'" class="settings-section">
            <div class="section-header">
              <el-button @click="startCreateLlmConfig">新建配置</el-button>
            </div>

            <div class="llm-shell">
              <div class="llm-list">
                <button
                  v-for="item in llmConfigs"
                  :key="item.id"
                  class="llm-item"
                  :class="{ 'llm-item--active': editingLlmId === item.id }"
                  @click="selectLlmConfig(item)"
                >
                  <div class="llm-item__title">{{ item.name }}</div>
                  <div class="llm-item__meta">{{ item.model }}</div>
                  <span v-if="item.is_active" class="llm-item__tag">当前生效</span>
                </button>

                <div v-if="!llmConfigs.length" class="llm-empty">
                  <h3>还没有模型配置</h3>
                  <p>先创建配置，再测试连接。</p>
                </div>
              </div>

              <div class="llm-editor">
                <div class="form-grid">
                  <div class="field">
                    <label for="llm-name">配置名称</label>
                    <el-input id="llm-name" v-model="llmForm.name" size="large" placeholder="例如：默认生产配置" />
                  </div>
                  <div class="field">
                    <label for="llm-model">模型名称</label>
                    <el-input id="llm-model" v-model="llmForm.model" size="large" placeholder="例如：gpt-4o-mini" />
                  </div>
                  <div class="field field--full">
                    <label for="llm-base-url">接口地址</label>
                    <el-input id="llm-base-url" v-model="llmForm.base_url" size="large" placeholder="https://api.example.com/v1" />
                  </div>
                  <div class="field field--full">
                    <label for="llm-api-key">API Key（可选）</label>
                    <el-input id="llm-api-key" v-model="llmForm.api_key" type="password" show-password size="large" placeholder="请输入 API Key" />
                  </div>
                  <div class="field field--full">
                    <div class="switch-card">
                      <div>
                        <div class="switch-row__title">设为当前生效配置</div>
                        <div class="switch-row__sub">开启后会自动切换到这个模型配置。</div>
                      </div>
                      <el-switch v-model="llmForm.is_active" />
                    </div>
                  </div>
                </div>

                <div class="section-actions">
                  <el-button :loading="testingLLM" @click="testLLM">测试连接</el-button>
                  <el-button type="primary" :loading="savingLlm" @click="saveLlmConfig">保存配置</el-button>
                  <el-button v-if="editingLlmId" text type="danger" @click="deleteLlmConfig(editingLlmId)">删除配置</el-button>
                </div>
              </div>
            </div>
          </section>

          <section v-else-if="activeTab === 'members'" class="settings-section">
            <div class="members-shell">
              <div class="members-hero">
                <div class="members-hero__copy">
                  <p class="members-hero__eyebrow">成员名录</p>
                  <h3>维护任务分发成员</h3>
                </div>
                <div class="members-hero__stats">
                  <div class="members-stat">
                    <span>成员数量</span>
                    <strong>{{ contacts.length }}</strong>
                  </div>
                  <div class="members-stat">
                    <span>已配置邮箱</span>
                    <strong>{{ contactsWithEmailCount }}</strong>
                  </div>
                </div>
              </div>

              <div class="members-toolbar">
                <div class="members-toolbar__hint">
                  <span class="members-toolbar__label">成员列表</span>
                </div>
                <el-button type="primary" size="large" @click="openAddContactDialog">新增成员</el-button>
              </div>

              <div class="members-table-shell">
                <el-table
                  :data="contacts"
                  v-loading="loadingContacts"
                  class="contacts-table"
                  height="100%"
                  empty-text="暂无成员数据。"
                >
                  <el-table-column prop="name" label="姓名" min-width="140" />
                  <el-table-column prop="email" label="邮箱" min-width="220" />
                  <el-table-column label="操作" width="180" fixed="right">
                    <template #default="{ row }">
                      <el-button text type="primary" @click="openEditContact(row)">编辑</el-button>
                      <el-button text type="danger" @click="deleteContact(row.id)">删除</el-button>
                    </template>
                  </el-table-column>
                </el-table>
              </div>
            </div>
          </section>
        </div>
      </section>

      <el-dialog v-model="addContactDialogVisible" title="新增成员" width="560px" destroy-on-close>
        <div class="member-dialog">
          <div class="member-dialog__intro">
            <h3>创建分发成员</h3>
            <p>新增成员后可用于会议任务分发，默认登录密码为 123456。</p>
          </div>
          <div class="form-grid member-grid">
            <div class="field">
              <label for="member-name">姓名</label>
              <el-input id="member-name" v-model="newContact.name" size="large" placeholder="请输入成员姓名" />
            </div>
            <div class="field">
              <label for="member-email">邮箱</label>
              <el-input id="member-email" v-model="newContact.email" size="large" placeholder="可留空" />
            </div>
          </div>
        </div>
        <template #footer>
          <div class="section-actions">
            <el-button @click="addContactDialogVisible = false">取消</el-button>
            <el-button type="primary" :loading="addingContact" @click="addContact">添加成员</el-button>
          </div>
        </template>
      </el-dialog>

      <el-dialog v-model="editContactDialogVisible" title="编辑成员" width="520px" destroy-on-close>
        <div class="form-grid member-grid">
          <div class="field">
            <label for="edit-member-name">姓名</label>
            <el-input id="edit-member-name" v-model="editingContact.name" size="large" placeholder="请输入成员姓名" />
          </div>
          <div class="field">
            <label for="edit-member-email">邮箱</label>
            <el-input id="edit-member-email" v-model="editingContact.email" size="large" placeholder="可留空" />
          </div>
        </div>
        <template #footer>
          <div class="section-actions">
            <el-button @click="editContactDialogVisible = false">取消</el-button>
            <el-button type="primary" :loading="savingContactEdit" @click="updateContact">保存修改</el-button>
          </div>
        </template>
      </el-dialog>
    </div>
  </MainLayout>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../services/api.js'
import MainLayout from '../components/MainLayout.vue'

const SETTINGS_TAB_KEY = 'smartsync_settings_active_tab'

const activeTab = ref('account')
const savingProfile = ref(false)
const savingDispatch = ref(false)
const changingPwd = ref(false)
const testingLLM = ref(false)
const savingLlm = ref(false)
const loadingContacts = ref(false)
const addingContact = ref(false)
const savingContactEdit = ref(false)

const profile = ref({ id: '', username: '', name: '', role: '', email: '' })
const pwdForm = ref({ old_password: '', new_password: '', confirm_password: '' })
const llmConfigs = ref([])
const editingLlmId = ref(null)
const llmForm = ref(createEmptyLlmForm())
const notifications = ref([
  { key: 'task_assigned', label: '任务分配', sub: '有新任务分配给我时提醒', enabled: true },
  { key: 'task_due', label: '任务即将到期', sub: '截止前提醒我跟进处理', enabled: true },
  { key: 'meeting_done', label: '会议处理完成', sub: '会议转写和摘要生成完成后提醒', enabled: false },
])
const dispatchConfig = ref(createDefaultDispatchConfig())
const contacts = ref([])
const newContact = ref({ name: '', email: '' })
const addContactDialogVisible = ref(false)
const editContactDialogVisible = ref(false)
const editingContact = ref({ id: '', name: '', email: '' })

const profileInitial = computed(() => (profile.value.name || 'S').trim().charAt(0).toUpperCase())
const roleLabel = computed(() => (profile.value.role === 'admin' ? '管理员' : '成员'))
const contactsWithEmailCount = computed(() => contacts.value.filter((item) => String(item.email || "").trim()).length)
const navItems = computed(() => {
  const items = [
    { value: 'account', label: '个人资料', note: '名称与邮箱' },
    { value: 'security', label: '账户安全', note: '修改登录密码' },
    { value: 'notifications', label: '通知偏好', note: '控制个人提醒展示' },
  ]
  if (profile.value.role === 'admin') {
    items.push(
      { value: 'dispatch', label: '邮件分发', note: '任务邮件发送配置' },
      { value: 'llm', label: '模型连接', note: '接口与模型配置' },
      { value: 'members', label: '成员管理', note: '维护成员与邮箱' },
    )
  }
  return items
})
const activeTabHint = computed(() => {
  return {
    account: '当前正在维护个人资料',
    security: '密码修改后需要重新登录',
    notifications: '当前为本地浏览器设置',
    dispatch: '邮件配置会影响任务分发与变更同步',
    llm: '先测试连接，再保存配置',
    members: '成员邮箱用于任务邮件分发',
  }[activeTab.value] || '设置会立即生效'
})

function createEmptyLlmForm() {
  return { name: '', model: 'gpt-4o-mini', base_url: '', api_key: '', is_active: false }
}

function createDefaultDispatchConfig() {
  return { email_enabled: true }
}

function normalizeActiveTab() {
  const allowedTabs = navItems.value.map((item) => item.value)
  if (!allowedTabs.includes(activeTab.value)) activeTab.value = 'account'
}

function loadNotificationPrefs() {
  try {
    const saved = JSON.parse(localStorage.getItem('smartsync_settings') || '{}')
    if (saved.notifications) {
      notifications.value.forEach((item, index) => {
        if (saved.notifications[index] !== undefined) item.enabled = saved.notifications[index]
      })
    }
  } catch {}
}

function saveNotifications() {
  localStorage.setItem(
    'smartsync_settings',
    JSON.stringify({ notifications: notifications.value.map((item) => item.enabled) }),
  )
  ElMessage.success('通知偏好已保存')
}

function syncLocalUser(user) {
  localStorage.setItem('smartsync_user', JSON.stringify(user))
}

async function loadProfile() {
  const res = await api.get('/settings/profile')
  profile.value = res.data
  syncLocalUser({
    id: res.data.id,
    username: res.data.username,
    name: res.data.name,
    role: res.data.role,
    email: res.data.email,
  })
}

async function saveProfile() {
  if (!profile.value.name.trim()) {
    ElMessage.warning('请输入显示名称')
    return
  }
  savingProfile.value = true
  try {
    const res = await api.put('/settings/profile', {
      name: profile.value.name,
      email: profile.value.email,
    })
    profile.value = res.data
    syncLocalUser({
      id: res.data.id,
      username: res.data.username,
      name: res.data.name,
      role: res.data.role,
      email: res.data.email,
    })
    ElMessage.success('个人资料已保存')
  } catch (error) {
    ElMessage.error('保存失败：' + (error.response?.data?.detail || error.message))
  } finally {
    savingProfile.value = false
  }
}

async function changePassword() {
  if (!pwdForm.value.old_password || !pwdForm.value.new_password || !pwdForm.value.confirm_password) {
    ElMessage.warning('请完整填写密码信息')
    return
  }
  if (pwdForm.value.new_password.length < 6) {
    ElMessage.warning('新密码至少需要 6 位')
    return
  }
  if (pwdForm.value.new_password !== pwdForm.value.confirm_password) {
    ElMessage.warning('两次输入的新密码不一致')
    return
  }

  changingPwd.value = true
  try {
    const res = await api.put('/auth/password', {
      old_password: pwdForm.value.old_password,
      new_password: pwdForm.value.new_password,
    })
    ElMessage.success(res.data.message || '密码修改成功')
    pwdForm.value = { old_password: '', new_password: '', confirm_password: '' }
    setTimeout(() => {
      localStorage.removeItem('smartsync_token')
      localStorage.removeItem('smartsync_user')
      window.location.href = '/login'
    }, 1200)
  } catch (error) {
    ElMessage.error('密码修改失败：' + (error.response?.data?.detail || error.message))
  } finally {
    changingPwd.value = false
  }
}

async function loadDispatchConfig() {
  if (profile.value.role !== 'admin') return
  try {
    const res = await api.get('/settings/dispatch')
    dispatchConfig.value = { ...createDefaultDispatchConfig(), ...res.data }
  } catch (error) {
    ElMessage.error('分发配置加载失败：' + (error.response?.data?.detail || error.message))
  }
}

async function saveDispatchConfig() {
  savingDispatch.value = true
  try {
    const res = await api.put('/settings/dispatch', dispatchConfig.value)
    dispatchConfig.value = { ...createDefaultDispatchConfig(), ...res.data }
    ElMessage.success('邮件分发配置已保存')
  } catch (error) {
    ElMessage.error('保存失败：' + (error.response?.data?.detail || error.message))
  } finally {
    savingDispatch.value = false
  }
}

function applyLlmConfigToForm(config) {
  llmForm.value = config
    ? {
        name: config.name || '',
        model: config.model || 'gpt-4o-mini',
        base_url: config.base_url || '',
        api_key: config.api_key || '',
        is_active: !!config.is_active,
      }
    : createEmptyLlmForm()
}

function selectLlmConfig(config) {
  editingLlmId.value = config.id
  applyLlmConfigToForm(config)
}

function startCreateLlmConfig() {
  editingLlmId.value = null
  applyLlmConfigToForm(null)
}

async function loadLlmConfigs() {
  if (profile.value.role !== 'admin') return
  try {
    const res = await api.get('/llm-configs')
    llmConfigs.value = res.data
    const active = llmConfigs.value.find((item) => item.is_active) || llmConfigs.value[0]
    if (active) selectLlmConfig(active)
    else startCreateLlmConfig()
  } catch {
    ElMessage.error('模型配置加载失败')
  }
}

async function testLLM() {
  if (!llmForm.value.base_url || !llmForm.value.model) {
    ElMessage.warning('请先填写接口地址和模型名称')
    return
  }
  testingLLM.value = true
  try {
    await api.post('/ai/test-connection', {
      model: llmForm.value.model,
      base_url: llmForm.value.base_url,
      api_key: llmForm.value.api_key,
    })
    ElMessage.success('连接成功，可以开始使用')
  } catch (error) {
    ElMessage.error('连接失败：' + (error.response?.data?.detail || error.message))
  } finally {
    testingLLM.value = false
  }
}

async function saveLlmConfig() {
  if (!llmForm.value.name.trim() || !llmForm.value.model.trim() || !llmForm.value.base_url.trim()) {
    ElMessage.warning('请填写配置名称、模型名称和接口地址')
    return
  }


  savingLlm.value = true
  try {
    const payload = {
      name: llmForm.value.name,
      model: llmForm.value.model,
      base_url: llmForm.value.base_url,
      api_key: llmForm.value.api_key,
      is_active: llmForm.value.is_active,
    }
    const res = editingLlmId.value
      ? await api.put(`/llm-configs/${editingLlmId.value}`, payload)
      : await api.post('/llm-configs', payload)
    editingLlmId.value = res.data.id
    ElMessage.success('模型配置已保存')
    await loadLlmConfigs()
  } catch (error) {
    ElMessage.error('保存失败：' + (error.response?.data?.detail || error.message))
  } finally {
    savingLlm.value = false
  }
}

async function deleteLlmConfig(id) {
  if (!id) return
  try {
    await api.delete(`/llm-configs/${id}`)
    ElMessage.success('模型配置已删除')
    editingLlmId.value = null
    await loadLlmConfigs()
  } catch (error) {
    ElMessage.error('删除失败：' + (error.response?.data?.detail || error.message))
  }
}

async function loadContacts() {
  if (profile.value.role !== 'admin') return
  loadingContacts.value = true
  try {
    const res = await api.get('/contacts')
    contacts.value = res.data
  } catch (error) {
    ElMessage.error('成员列表加载失败：' + (error.response?.data?.detail || error.message))
  } finally {
    loadingContacts.value = false
  }
}

async function addContact() {
  if (!newContact.value.name.trim()) {
    ElMessage.warning('请输入成员姓名')
    return
  }
  addingContact.value = true
  try {
    await api.post('/contacts', newContact.value)
    ElMessage.success('成员已添加，默认密码为 123456')
    newContact.value = { name: '', email: '' }
    addContactDialogVisible.value = false
    await loadContacts()
  } catch (error) {
    ElMessage.error('添加失败：' + (error.response?.data?.detail || error.message))
  } finally {
    addingContact.value = false
  }
}

function openAddContactDialog() {
  newContact.value = { name: '', email: '' }
  addContactDialogVisible.value = true
}

function openEditContact(contact) {
  editingContact.value = {
    id: contact.id,
    name: contact.name || '',
    email: contact.email || '',
  }
  editContactDialogVisible.value = true
}

async function updateContact() {
  if (!editingContact.value.id) return
  if (!editingContact.value.name.trim()) {
    ElMessage.warning('请输入成员姓名')
    return
  }
  savingContactEdit.value = true
  try {
    await api.put(`/contacts/${editingContact.value.id}`, {
      name: editingContact.value.name,
      email: editingContact.value.email,
    })
    ElMessage.success('成员信息已更新')
    editContactDialogVisible.value = false
    await loadContacts()
  } catch (error) {
    ElMessage.error('更新失败：' + (error.response?.data?.detail || error.message))
  } finally {
    savingContactEdit.value = false
  }
}

async function deleteContact(id) {
  try {
    await api.delete(`/contacts/${id}`)
    ElMessage.success('成员已删除')
    await loadContacts()
  } catch (error) {
    ElMessage.error('删除失败：' + (error.response?.data?.detail || error.message))
  }
}

watch(activeTab, (value) => {
  localStorage.setItem(SETTINGS_TAB_KEY, value)
})

watch(navItems, () => {
  normalizeActiveTab()
})

onMounted(async () => {
  loadNotificationPrefs()
  activeTab.value = localStorage.getItem(SETTINGS_TAB_KEY) || 'account'
  try {
    await loadProfile()
    normalizeActiveTab()
    if (profile.value.role === 'admin') {
      await loadDispatchConfig()
      await loadLlmConfigs()
      await loadContacts()
    }
  } catch (error) {
    ElMessage.error('设置页初始化失败：' + (error.response?.data?.detail || error.message))
  }
})
</script>

<style scoped>
.settings-page {
  max-width: 1400px;
  margin: 0 auto;
  padding: clamp(28px, 4vw, 44px);
}

.page-kicker,
.section-kicker,
.switch-row__title,
.settings-nav__note {
  font-size: 12px;
}

.page-kicker,
.section-kicker {
  margin-bottom: 10px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-soft);
}

.settings-header h1,
.section-header h2 {
  font-size: clamp(2rem, 4.2vw, 3.4rem);
  line-height: 0.98;
  letter-spacing: -0.05em;
  color: var(--text);
}

.settings-header p,
.section-header p,
.llm-empty p {
  margin-top: 14px;
  max-width: 56ch;
  color: var(--text-muted);
  line-height: 1.72;
}

.identity-strip,
.settings-nav,
.settings-panel {
  border: 1px solid var(--border-soft);
  background: color-mix(in oklab, var(--bg-elevated) 94%, var(--bg) 6%);
  box-shadow: var(--shadow-sm);
}

.identity-strip {
  margin-top: 26px;
  border-radius: 22px;
  padding: 20px 22px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  flex-wrap: wrap;
}

.identity-strip__main,
.identity-strip__side {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}

.identity-avatar {
  width: 52px;
  height: 52px;
  border-radius: 16px;
  display: grid;
  place-items: center;
  background: color-mix(in oklab, var(--primary) 12%, var(--bg-elevated));
  border: 1px solid color-mix(in oklab, var(--primary) 18%, var(--border));
  font-size: 18px;
  font-weight: 700;
  color: var(--text);
}

.identity-name {
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--text);
}

.identity-meta {
  margin-top: 6px;
  color: var(--text-muted);
}

.identity-tip {
  margin-top: 8px;
  color: var(--text-soft);
  font-size: 13px;
}

.identity-stat {
  min-width: 120px;
  padding: 12px 14px;
  border-radius: 14px;
  background: color-mix(in oklab, var(--bg-panel) 80%, var(--bg) 20%);
  border: 1px solid var(--border-soft);
}

.identity-stat em {
  display: block;
  margin-bottom: 8px;
  font-style: normal;
  font-size: 12px;
  color: var(--text-soft);
}

.identity-stat strong {
  color: var(--text);
  font-size: 1rem;
}

.settings-shell {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  gap: 18px;
  margin-top: 22px;
  align-items: start;
}

.settings-nav {
  border-radius: 22px;
  padding: 14px;
  display: grid;
  gap: 8px;
}

.settings-nav__item {
  width: 100%;
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px solid transparent;
  background: transparent;
  text-align: left;
  color: var(--text-muted);
  cursor: pointer;
  transition: background 0.18s ease, border-color 0.18s ease, color 0.18s ease;
}

.settings-nav__item:hover,
.settings-nav__item.active {
  color: var(--text);
  background: color-mix(in oklab, var(--primary) 7%, var(--bg-elevated));
  border-color: color-mix(in oklab, var(--primary) 18%, var(--border));
}

.settings-nav__label {
  display: block;
  font-size: 14px;
  font-weight: 700;
}

.settings-nav__note {
  display: block;
  margin-top: 6px;
  color: var(--text-soft);
  line-height: 1.5;
}

.settings-panel {
  border-radius: 24px;
  padding: 26px;
}

.settings-section {
  display: grid;
  gap: 22px;
}

.section-header {
  display: flex;
  align-items: start;
  justify-content: space-between;
  gap: 18px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}

.form-grid--single {
  grid-template-columns: 1fr;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.field--full {
  grid-column: 1 / -1;
}

.field label {
  color: var(--text);
  font-size: 14px;
  font-weight: 700;
}

.section-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  justify-content: flex-end;
  padding-top: 18px;
  border-top: 1px solid var(--border-soft);
}

.settings-list {
  display: grid;
}

.settings-list__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 0;
  border-bottom: 1px solid var(--border-soft);
}

.settings-list__row:last-child {
  border-bottom: none;
}

.settings-list__title,
.llm-item__title {
  font-weight: 700;
  color: var(--text);
}

.settings-list__sub,
.llm-item__meta,
.switch-row__sub {
  margin-top: 6px;
  color: var(--text-muted);
  font-size: 13px;
  line-height: 1.6;
}

.switch-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 18px;
  border: 1px solid var(--border-soft);
  border-radius: 18px;
  background: color-mix(in oklab, var(--bg-panel) 82%, var(--bg) 18%);
}

.llm-shell {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  gap: 18px;
}

.llm-list,
.llm-editor,
.member-create {
  border: 1px solid var(--border-soft);
  border-radius: 20px;
  background: color-mix(in oklab, var(--bg-panel) 82%, var(--bg) 18%);
}

.llm-list {
  padding: 14px;
  display: grid;
  gap: 8px;
  align-self: start;
}

.llm-item {
  width: 100%;
  text-align: left;
  padding: 14px;
  border-radius: 16px;
  border: 1px solid transparent;
  background: transparent;
  cursor: pointer;
  transition: background 0.18s ease, border-color 0.18s ease;
}

.llm-item:hover,
.llm-item--active {
  background: color-mix(in oklab, var(--primary) 7%, var(--bg-elevated));
  border-color: color-mix(in oklab, var(--primary) 18%, var(--border));
}

.llm-item__tag {
  display: inline-flex;
  margin-top: 10px;
  padding: 4px 10px;
  border-radius: 999px;
  background: color-mix(in oklab, var(--success) 12%, transparent);
  color: var(--success);
  font-size: 12px;
  font-weight: 700;
}

.llm-empty {
  padding: 16px 8px 8px;
}

.llm-empty h3 {
  font-size: 1rem;
  color: var(--text);
}

.llm-editor,
.member-create {
  padding: 18px;
}

.members-shell {
  display: grid;
  gap: 18px;
  min-height: 0;
}

.members-hero {
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) minmax(280px, .9fr);
  gap: 18px;
  align-items: stretch;
  padding: 22px;
  border: 1px solid color-mix(in oklab, var(--primary) 14%, var(--border-soft));
  border-radius: 24px;
  background:
    radial-gradient(circle at top left, color-mix(in oklab, var(--primary) 14%, transparent), transparent 42%),
    linear-gradient(135deg, color-mix(in oklab, var(--bg-panel) 90%, var(--bg) 10%), color-mix(in oklab, var(--bg-elevated) 88%, var(--primary) 12%));
}

.members-hero__copy h3 {
  margin: 8px 0 10px;
  font-size: clamp(22px, 2.2vw, 30px);
  line-height: 1.1;
  letter-spacing: -.04em;
  color: var(--text);
}

.members-hero__copy p:last-child {
  margin: 0;
  max-width: 58ch;
  color: var(--text-muted);
  line-height: 1.7;
}

.members-hero__eyebrow {
  margin: 0;
  font-size: 12px;
  letter-spacing: .16em;
  text-transform: uppercase;
  color: var(--text-muted);
  font-weight: 700;
}

.members-hero__stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.members-stat {
  padding: 16px 14px;
  border-radius: 18px;
  border: 1px solid color-mix(in oklab, var(--border-soft) 88%, transparent);
  background: color-mix(in oklab, var(--bg-panel) 78%, var(--bg) 22%);
}

.members-stat span {
  display: block;
  color: var(--text-muted);
  font-size: 12px;
  margin-bottom: 8px;
}

.members-stat strong {
  color: var(--text);
  font-size: clamp(24px, 2vw, 32px);
  line-height: 1;
  letter-spacing: -.05em;
}

.members-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 0 2px;
}

.members-toolbar__hint {
  min-width: 0;
}

.members-toolbar__label {
  display: block;
  font-size: 15px;
  font-weight: 700;
  color: var(--text);
}

.members-toolbar__sub {
  display: block;
  margin-top: 4px;
  color: var(--text-muted);
  font-size: 13px;
  line-height: 1.6;
}

.members-table-shell {
  min-height: 0;
  max-height: min(58vh, 620px);
  border: 1px solid var(--border-soft);
  border-radius: 22px;
  background: color-mix(in oklab, var(--bg-panel) 86%, var(--bg) 14%);
  overflow: hidden;
}

.member-grid {
  margin-bottom: 18px;
}

.contacts-table {
  height: 100%;
}

.member-dialog {
  display: grid;
  gap: 18px;
}

.member-dialog__intro {
  padding: 16px 18px;
  border-radius: 18px;
  border: 1px solid color-mix(in oklab, var(--primary) 14%, var(--border-soft));
  background: color-mix(in oklab, var(--primary) 8%, var(--bg-panel));
}

.member-dialog__intro h3 {
  margin: 0 0 6px;
  color: var(--text);
  font-size: 18px;
}

.member-dialog__intro p {
  margin: 0;
  color: var(--text-muted);
  line-height: 1.6;
}

@media (max-width: 1080px) {
  .settings-shell,
  .llm-shell {
    grid-template-columns: 1fr;
  }

  .members-hero {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 760px) {
  .form-grid,
  .section-header {
    grid-template-columns: 1fr;
    display: grid;
  }

  .identity-strip {
    align-items: stretch;
  }

  .switch-card {
    align-items: flex-start;
  }

  .members-hero__stats {
    grid-template-columns: 1fr;
  }

  .members-toolbar {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
