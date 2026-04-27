<template>
  <MainLayout>
    <div class="dashboard-page">
      <header class="page-header">
        <div class="page-header__copy">
          <div class="page-kicker">会议中心</div>
          <div class="page-mood">{{ workdayPulse }}</div>
          <h1>会议管理</h1>
          <p>上传录音后，系统会自动生成转写、摘要和行动项。</p>
        </div>

        <div class="page-header__actions">
          <el-button @click="store.fetchMeetings()">
            <el-icon><Refresh /></el-icon>
            刷新列表
          </el-button>
        </div>
      </header>

      <section class="dashboard-hero">
        <div class="upload-panel">
          <div class="section-head">
            <div>
              <div class="section-label">上传会议</div>
              <h2>导入录音，开始处理</h2>
            </div>
            <div class="section-hint">处理时间通常为 3 到 10 分钟</div>
          </div>

          <div
            class="upload-stage"
            :class="{ 'upload-stage--drag': isDragging, 'upload-stage--processing': isProcessing }"
            @dragenter.prevent="isDragging = true"
            @dragleave.prevent="isDragging = false"
            @dragover.prevent
            @drop.prevent="handleDrop"
          >
            <input ref="fileInput" type="file" accept=".mp3,.wav,.mp4,.m4a" hidden @change="handleFileSelect" />

            <template v-if="!isProcessing">
              <div class="upload-stage__intro">
                <div class="upload-stage__icon">
                  <el-icon size="32"><UploadFilled /></el-icon>
                </div>
                <div class="upload-stage__copy">
                  <h3>支持文件上传和录音链接</h3>
                  <p>可上传 MP3、WAV、MP4、M4A 文件，或粘贴可访问的录音地址。处理完成后，你可以直接确认纪要并分发任务。</p>
                </div>
              </div>

              <div class="upload-stage__meta">
                <span>支持格式：MP3 / WAV / MP4 / M4A</span>
                <span>建议单个文件不超过 200MB</span>
              </div>

              <div class="upload-stage__actions">
                <el-button type="primary" size="large" @click="fileInput?.click()">
                  <el-icon><FolderOpened /></el-icon>
                  选择文件
                </el-button>
                <el-button size="large" @click="showUrlDialog = true">
                  <el-icon><Link /></el-icon>
                  粘贴录音链接
                </el-button>
              </div>
            </template>

            <template v-else>
              <div class="progress-area">
                <div class="progress-spinner"></div>
                <div class="progress-copy">
                  <div class="progress-label">{{ progressLabel }}</div>
                  <p class="progress-note">{{ progressNote }}</p>
                  <el-progress :percentage="uploadPct" :show-text="false" class="progress-bar" />
                </div>
              </div>
            </template>
          </div>

          <div class="process-strip">
            <div class="process-step" :class="{ active: currentStage === 'uploading', done: stageDone('uploading') }">
              <strong>1</strong>
              <span>上传录音</span>
            </div>
            <div class="process-step" :class="{ active: currentStage === 'processing', done: stageDone('processing') }">
              <strong>2</strong>
              <span>自动转写与摘要整理</span>
            </div>
            <div class="process-step" :class="{ active: currentStage === 'review', done: stageDone('review') }">
              <strong>3</strong>
              <span>确认后分发行动项</span>
            </div>
          </div>
        </div>

        <aside class="overview-panel">
          <div class="overview-block">
            <div class="section-label">处理概览</div>
            <div class="overview-list">
              <div class="overview-row">
                <span>待确认</span>
                <strong>{{ pendingReview }}</strong>
              </div>
              <div class="overview-row">
                <span>处理中</span>
                <strong>{{ processingCount }}</strong>
              </div>
              <div class="overview-row">
                <span>已分发</span>
                <strong>{{ dispatched }}</strong>
              </div>
              <div class="overview-row">
                <span>会议总数</span>
                <strong>{{ store.totalMeetings }}</strong>
              </div>
            </div>
          </div>

          <div class="overview-block overview-block--focus">
            <div class="section-label">最近会议</div>
            <template v-if="latestMeeting">
              <h3>{{ latestMeeting.name }}</h3>
              <div class="focus-meta">
                <span>{{ latestMeeting.date }}</span>
                <span>{{ formatDuration(latestMeeting.duration_sec) }}</span>
              </div>
              <p class="focus-note">{{ meetingHint(latestMeeting.status) }}</p>
              <div class="focus-actions">
                <span class="card-tag" :class="`tag-${statusKey(latestMeeting.status)}`">
                  {{ statusLabel(latestMeeting.status) }}
                </span>
                <el-button type="primary" @click="router.push(`/meetings/${latestMeeting.id}`)">查看会议</el-button>
              </div>
            </template>
            <template v-else>
              <p class="overview-empty">还没有会议记录。先上传一段录音，系统会自动生成纪要和行动项。</p>
            </template>
          </div>
        </aside>
      </section>

      <section class="meeting-board">
        <div class="section-head section-head--board">
          <div>
            <div class="section-label">最近会议</div>
            <h2>最近会议</h2>
          </div>
          <div class="section-hint">点击任意会议即可继续确认纪要、分发任务或查看执行状态</div>
        </div>

        <div class="meeting-table">
          <div class="meeting-table__head">
            <span>会议</span>
            <span>日期</span>
            <span>时长</span>
            <span>行动项</span>
            <span>状态</span>
            <span>操作</span>
          </div>

          <div v-if="store.loading" class="meeting-table__loading">
            <div v-for="i in 5" :key="i" class="meeting-row meeting-row--skeleton"></div>
          </div>

          <div v-else-if="store.meetings.length" class="meeting-table__body">
            <article
              v-for="(meeting, index) in store.meetings"
              :key="meeting.id"
              class="meeting-row fade-slide-up"
              :style="{ animationDelay: index * 40 + 'ms' }"
              @click="router.push(`/meetings/${meeting.id}`)"
            >
              <div class="meeting-row__title">
                <div class="meeting-row__icon" :class="`icon-${statusColor(meeting.status)}`">
                  <el-icon><Headset /></el-icon>
                </div>
                <div>
                  <div class="meeting-row__name">{{ meeting.name }}</div>
                  <div class="meeting-row__hint">{{ meetingHint(meeting.status) }}</div>
                </div>
              </div>
              <div class="meeting-row__cell">{{ meeting.date }}</div>
              <div class="meeting-row__cell">{{ formatDuration(meeting.duration_sec) }}</div>
              <div class="meeting-row__cell">{{ meeting.task_count }} 项</div>
              <div class="meeting-row__cell">
                <span class="card-tag" :class="`tag-${statusKey(meeting.status)}`">
                  {{ statusLabel(meeting.status) }}
                </span>
              </div>
              <div class="meeting-row__actions">
                <el-button size="small" type="primary" @click.stop="router.push(`/meetings/${meeting.id}`)">进入</el-button>
                <el-button size="small" text type="danger" @click.stop="removeMeeting(meeting)">删除</el-button>
              </div>
            </article>
          </div>

          <div v-else class="table-empty">
            <h3>还没有会议记录</h3>
            <p>先上传一段录音，系统会自动生成转写、纪要和行动项。</p>
          </div>
        </div>
      </section>

      <el-dialog v-model="showUrlDialog" title="导入录音链接" width="440px" align-center>
        <el-input v-model="meetingUrl" placeholder="https://..." size="large" />
        <p class="url-hint">请粘贴一个可直接访问的音频或视频地址，系统会自动拉取并处理。</p>
        <template #footer>
          <el-button @click="showUrlDialog = false">取消</el-button>
          <el-button type="primary" @click="handleUrlUpload">开始处理</el-button>
        </template>
      </el-dialog>
    </div>
  </MainLayout>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, ElNotification } from 'element-plus'
import api from '../services/api.js'
import MainLayout from '../components/MainLayout.vue'
import { useMeetingStore } from '../stores/meetingStore.js'

const router = useRouter()
const store = useMeetingStore()
const fileInput = ref(null)
const isDragging = ref(false)
const isProcessing = ref(false)
const uploadPct = ref(0)
const progressLabel = ref('正在上传录音...')
const progressNote = ref('上传完成后会自动开始转写，请稍等。')
const showUrlDialog = ref(false)
const meetingUrl = ref('')
const currentStage = ref('uploading')

const dispatched = computed(() => store.meetings.filter((meeting) => meeting.status === 'dispatched').length)
const pendingReview = computed(() => store.meetings.filter((meeting) => meeting.status === 'ready_for_review').length)
const processingCount = computed(() => store.meetings.filter((meeting) => meeting.status === 'processing' || meeting.status === 'uploading').length)
const latestMeeting = computed(() => store.meetings[0] || null)
const workdayPulse = computed(() => {
  const hour = new Date().getHours()
  if (hour < 11) return '早上好，先看今天的新会议'
  if (hour < 14) return '中午好，别忘了确认待分发内容'
  if (hour < 18) return '下午好，继续推进会议进度'
  return '晚上好，收一下今天的会议结果'
})

onMounted(() => store.fetchMeetings())

function statusLabel(status) {
  return {
    uploading: '上传中',
    processing: '处理中',
    ready_for_review: '待确认',
    dispatched: '已分发',
  }[status] || status
}

function statusKey(status) {
  return {
    uploading: 'uploading',
    processing: 'processing',
    ready_for_review: 'review',
    dispatched: 'dispatched',
  }[status] || 'info'
}

function statusColor(status) {
  return {
    uploading: 'blue',
    processing: 'yellow',
    ready_for_review: 'orange',
    dispatched: 'green',
  }[status] || 'blue'
}

function meetingHint(status) {
  return {
    uploading: '录音已上传，等待进入处理流程',
    processing: '系统正在整理摘要和行动项',
    ready_for_review: '请确认纪要内容后再分发任务',
    dispatched: '行动项已下发，可继续查看执行进度',
  }[status] || '查看会议详情'
}

function stageDone(stage) {
  const order = ['uploading', 'processing', 'review']
  return order.indexOf(currentStage.value) > order.indexOf(stage)
}

function formatDuration(sec) {
  if (!sec) return '--'
  const hour = Math.floor(sec / 3600)
  const minute = Math.floor((sec % 3600) / 60)
  return hour > 0 ? `${hour}小时 ${minute}分钟` : `${minute}分钟`
}

function handleDrop(event) {
  isDragging.value = false
  const file = event.dataTransfer.files[0]
  if (file) processFile(file)
}

function handleFileSelect(event) {
  const file = event.target.files[0]
  if (file) processFile(file)
}

async function processFile(file) {
  if (!(file.type.startsWith('audio') || file.type.startsWith('video'))) {
    ElMessage.error('仅支持 MP3、WAV、MP4、M4A 等音视频文件')
    return
  }

  if (file.size > 200 * 1024 * 1024) {
    ElMessage.error('文件大小不能超过 200MB')
    return
  }

  isProcessing.value = true
  uploadPct.value = 0
  progressLabel.value = '正在上传录音...'
  progressNote.value = '上传完成后会自动开始转写，请稍等。'
  currentStage.value = 'uploading'

  try {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('name', file.name.replace(/\.[^.]+$/, ''))

    const res = await api.post('/upload', formData)
    await pollTask(res.data.task_id)

    await store.fetchMeetings()
    ElNotification({
      title: '处理完成',
      message: `《${file.name}》已完成分析，现在可以确认纪要并分发任务。`,
      type: 'success',
      duration: 5000,
    })
  } catch (error) {
    ElMessage.error('上传失败：' + (error.response?.data?.detail || error.message))
  } finally {
    isProcessing.value = false
    if (fileInput.value) fileInput.value.value = ''
  }
}

async function pollTask(taskId) {
  return new Promise((resolve, reject) => {
    const timer = setInterval(async () => {
      try {
        const res = await api.get(`/tasks/${taskId}/status`)
        const data = res.data
        uploadPct.value = data.progress || 0

        if (data.status === 'uploading') {
          progressLabel.value = '正在上传录音...'
          progressNote.value = '上传完成后会自动开始转写，请稍等。'
          currentStage.value = 'uploading'
        } else if (data.status === 'processing') {
          currentStage.value = 'processing'
          if ((data.progress || 0) < 35) {
            progressLabel.value = '正在识别发言内容...'
            progressNote.value = '系统正在整理说话人和时间段。'
          } else if ((data.progress || 0) < 75) {
            progressLabel.value = '正在整理摘要和结论...'
            progressNote.value = '转写已完成，正在提炼关键信息。'
          } else {
            progressLabel.value = '正在提取行动项...'
            progressNote.value = '快完成了，马上就能进入确认环节。'
          }
        } else {
          progressLabel.value = '正在整理结果...'
          progressNote.value = '正在做最后整理。'
        }

        if (data.status === 'ready_for_review' || data.status === 'dispatched') {
          clearInterval(timer)
          uploadPct.value = 100
          progressLabel.value = '处理完成'
          progressNote.value = '结果已经准备好，可以去确认纪要了。'
          currentStage.value = 'review'
          setTimeout(resolve, 500)
        }
      } catch (error) {
        clearInterval(timer)
        reject(error)
      }
    }, 1500)
  })
}

async function handleUrlUpload() {
  if (!meetingUrl.value.trim()) {
    ElMessage.warning('请输入录音链接')
    return
  }

  showUrlDialog.value = false
  isProcessing.value = true
  progressLabel.value = '正在提交录音链接...'
  progressNote.value = '提交后会自动开始拉取和处理录音。'
  uploadPct.value = 0
  currentStage.value = 'uploading'

  try {
    const formData = new FormData()
    formData.append('url', meetingUrl.value)
    const res = await api.post('/upload', formData)
    await pollTask(res.data.task_id)

    await store.fetchMeetings()
    ElMessage.success('链接处理完成，现在可以继续确认纪要')
  } catch (error) {
    ElMessage.error('处理失败：' + (error.response?.data?.detail || error.message))
  } finally {
    isProcessing.value = false
    meetingUrl.value = ''
  }
}

async function removeMeeting(meeting) {
  try {
    await ElMessageBox.confirm(`确认删除《${meeting.name}》？删除后将无法恢复。`, '删除会议', {
      confirmButtonText: '删除会议',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }

  try {
    await api.delete(`/meetings/${meeting.id}`)
    ElMessage.success('会议已删除')
    await store.fetchMeetings()
  } catch (error) {
    ElMessage.error('删除失败：' + (error.response?.data?.detail || error.message))
  }
}
</script>

<style scoped>
.dashboard-page {
  max-width: 1400px;
  margin: 0 auto;
  padding: clamp(28px, 4vw, 44px);
}

.page-header,
.dashboard-hero {
  display: grid;
  gap: 24px;
}

.page-header {
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: end;
  margin-bottom: 28px;
}

.page-header__copy {
  max-width: 62rem;
}

.page-mood {
  display: inline-flex;
  align-items: center;
  min-height: 30px;
  margin-bottom: 14px;
  padding: 0 12px;
  border-radius: 999px;
  background: color-mix(in oklab, var(--primary) 8%, var(--bg-panel));
  border: 1px solid color-mix(in oklab, var(--primary) 14%, var(--border));
  color: color-mix(in oklab, var(--primary) 72%, var(--text) 28%);
  font-size: 13px;
  font-weight: 600;
}

.page-kicker,
.section-label {
  margin-bottom: 10px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-soft);
}

.page-header h1,
.section-head h2 {
  font-size: clamp(2rem, 4.4vw, 3.5rem);
  line-height: 0.98;
  letter-spacing: -0.05em;
  color: var(--text);
}

.page-header p,
.upload-stage__copy p,
.focus-note,
.table-empty p {
  margin-top: 14px;
  max-width: 56ch;
  color: var(--text-muted);
  line-height: 1.72;
}

.dashboard-hero {
  grid-template-columns: minmax(0, 1.55fr) minmax(320px, 0.9fr);
  align-items: start;
  margin-bottom: 28px;
}

.upload-panel,
.overview-panel,
.meeting-board {
  border: 1px solid var(--border-soft);
  background: color-mix(in oklab, var(--bg-elevated) 94%, var(--bg) 6%);
  box-shadow: var(--shadow-sm);
}

.upload-panel {
  border-radius: 28px;
  padding: clamp(22px, 4vw, 32px);
}

.section-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: end;
}

.section-head h2 {
  font-size: clamp(1.7rem, 3vw, 2.4rem);
}

.section-hint {
  max-width: 20rem;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-soft);
}

.upload-stage {
  margin-top: 22px;
  border-radius: 24px;
  border: 1px dashed color-mix(in oklab, var(--primary) 28%, var(--border));
  background: color-mix(in oklab, var(--bg-panel) 86%, var(--primary) 4%);
  padding: clamp(24px, 4vw, 34px);
  transition: transform 0.2s ease, border-color 0.2s ease, background 0.2s ease;
}

.upload-stage:hover,
.upload-stage--drag {
  border-color: color-mix(in oklab, var(--primary) 48%, var(--border));
  background: color-mix(in oklab, var(--bg-panel) 80%, var(--primary) 7%);
}

.upload-stage__intro {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr);
  gap: 18px;
  align-items: start;
}

.upload-stage__icon {
  width: 72px;
  height: 72px;
  border-radius: 20px;
  display: grid;
  place-items: center;
  color: var(--primary);
  background: color-mix(in oklab, var(--primary) 12%, transparent);
  border: 1px solid color-mix(in oklab, var(--primary) 16%, var(--border));
}

.upload-stage__copy h3 {
  font-size: clamp(1.4rem, 2.4vw, 2.1rem);
  line-height: 1.08;
  letter-spacing: -0.04em;
  color: var(--text);
}

.upload-stage__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 16px;
  margin-top: 22px;
  font-size: 13px;
  color: var(--text-soft);
}

.upload-stage__actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 28px;
}

.progress-area {
  min-height: 210px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 20px;
}

.progress-spinner {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  border: 3px solid color-mix(in oklab, var(--primary) 16%, transparent);
  border-top-color: var(--primary);
  animation: spin 1s linear infinite;
}

.progress-copy {
  width: min(360px, 100%);
}

.progress-label {
  font-size: 16px;
  font-weight: 700;
  color: var(--text);
}

.progress-note {
  margin: 10px 0 16px;
  color: var(--text-muted);
  font-size: 14px;
  line-height: 1.65;
}

.process-strip {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-top: 18px;
}

.process-step {
  min-height: 88px;
  padding: 16px;
  border-top: 1px solid var(--border-soft);
  background: color-mix(in oklab, var(--bg-panel) 68%, transparent);
  transition: transform 0.18s ease, background 0.18s ease;
  position: relative;
  overflow: hidden;
}

.process-step:hover {
  transform: translateY(-1px);
  background: color-mix(in oklab, var(--bg-panel) 80%, var(--primary) 4%);
}

.process-step::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(110deg, transparent 0%, color-mix(in oklab, var(--primary) 10%, transparent) 45%, transparent 100%);
  transform: translateX(-120%);
  opacity: 0;
}

.process-step.active {
  background: color-mix(in oklab, var(--primary) 8%, var(--bg-panel));
}

.process-step.active::after {
  opacity: 1;
  animation: stageSweep 1.8s ease-in-out infinite;
}

.process-step.done {
  background: color-mix(in oklab, var(--success) 8%, var(--bg-panel));
}

.process-step.done strong {
  color: var(--success);
}

.process-step strong {
  display: block;
  margin-bottom: 10px;
  font-size: 14px;
  font-weight: 700;
  color: var(--primary);
}

.process-step span {
  display: block;
  color: var(--text);
  line-height: 1.6;
}

@keyframes stageSweep {
  0% {
    transform: translateX(-120%);
  }

  100% {
    transform: translateX(130%);
  }
}

.overview-panel {
  border-radius: 24px;
  padding: 22px;
  display: grid;
  gap: 16px;
}

.overview-block {
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border-soft);
}

.overview-block:last-child {
  padding-bottom: 0;
  border-bottom: none;
}

.overview-list {
  display: grid;
  gap: 14px;
}

.overview-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  color: var(--text-muted);
}

.overview-row strong {
  font-size: 1.75rem;
  line-height: 1;
  letter-spacing: -0.04em;
  color: var(--text);
}

.overview-block--focus h3,
.table-empty h3 {
  font-size: 1.25rem;
  line-height: 1.25;
  letter-spacing: -0.03em;
  color: var(--text);
}

.focus-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 12px;
  color: var(--text-soft);
  font-size: 13px;
}

.focus-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  margin-top: 18px;
}

.overview-empty {
  color: var(--text-muted);
  line-height: 1.7;
}

.meeting-board {
  border-radius: 28px;
  padding: 24px;
}

.section-head--board {
  padding-bottom: 18px;
  border-bottom: 1px solid var(--border-soft);
}

.meeting-table__head,
.meeting-row {
  display: grid;
  grid-template-columns: minmax(320px, 2fr) 116px 100px 100px 120px 114px;
  gap: 12px;
  align-items: center;
}

.meeting-table__head {
  min-height: 52px;
  padding: 0 8px;
  color: var(--text-soft);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.meeting-table__body {
  display: grid;
}

.meeting-row {
  min-height: 84px;
  padding: 0 8px;
  border-top: 1px solid var(--border-soft);
  cursor: pointer;
  transition: background 0.18s ease;
}

.meeting-row:hover {
  background: color-mix(in oklab, var(--primary) 4%, transparent);
}

.meeting-row--skeleton {
  border-radius: 16px;
  background: color-mix(in oklab, var(--bg-panel) 82%, var(--bg) 18%);
  animation: pulse 1.4s ease-in-out infinite;
  margin-top: 10px;
}

.meeting-row__title {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
}

.meeting-row__icon {
  width: 42px;
  height: 42px;
  border-radius: 14px;
  display: grid;
  place-items: center;
  flex-shrink: 0;
}

.icon-orange {
  background: color-mix(in oklab, var(--primary) 12%, transparent);
  color: var(--primary);
}

.icon-green {
  background: color-mix(in oklab, var(--success) 12%, transparent);
  color: var(--success);
}

.icon-yellow {
  background: color-mix(in oklab, var(--warning) 12%, transparent);
  color: var(--warning);
}

.icon-blue {
  background: color-mix(in oklab, var(--accent) 12%, transparent);
  color: var(--accent);
}

.meeting-row__name {
  font-size: 15px;
  font-weight: 700;
  color: var(--text);
  line-height: 1.45;
}

.meeting-row__hint,
.meeting-row__cell {
  color: var(--text-muted);
  font-size: 13px;
  line-height: 1.5;
}

.meeting-row__hint {
  margin-top: 4px;
}

.meeting-row__actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.meeting-table__loading {
  padding-top: 8px;
}

.table-empty {
  padding: 48px 0 24px;
  text-align: center;
}

.table-empty p {
  margin-inline: auto;
}

.url-hint {
  margin-top: 10px;
  font-size: 13px;
  color: var(--text-muted);
  line-height: 1.6;
}

@media (max-width: 1180px) {
  .dashboard-hero {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 940px) {
  .page-header,
  .section-head {
    grid-template-columns: 1fr;
    display: grid;
  }

  .process-strip {
    grid-template-columns: 1fr;
  }

  .meeting-table__head,
  .meeting-row {
    grid-template-columns: minmax(240px, 2fr) 88px 88px 84px 100px 98px;
  }
}

@media (max-width: 760px) {
  .upload-stage__intro,
  .progress-area {
    grid-template-columns: 1fr;
    display: grid;
  }

  .meeting-table__head {
    display: none;
  }

  .meeting-row {
    grid-template-columns: 1fr;
    gap: 8px;
    padding: 18px 0;
  }

  .meeting-row__actions {
    justify-content: flex-start;
  }
}
</style>
