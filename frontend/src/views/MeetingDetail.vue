<template>
  <MainLayout>
    <div class="detail-page">
      <header class="topbar">
        <el-button text class="back-btn" @click="router.back()">
          <el-icon><ArrowLeft /></el-icon>
          返回
        </el-button>

        <div class="topbar-main">
          <div class="topbar-eyebrow">会议详情</div>
          <h1>{{ meeting?.name || '会议详情' }}</h1>
          <div v-if="meeting" class="topbar-meta">
            <span>{{ meeting.date || '--' }}</span>
            <span>{{ formatDuration(meeting.duration_sec) }}</span>
            <span class="meeting-status" :class="`tag-${statusKey(meeting.status)}`">
              {{ statusLabel(meeting.status) }}
            </span>
            <span v-if="isReadOnly" class="readonly-chip">待办查看模式</span>
          </div>
        </div>

        <div v-if="meeting && !isReadOnly" class="topbar-actions">
          <el-button :loading="saving" @click="saveMeeting">保存</el-button>
          <el-button type="primary" :loading="dispatching" @click="handleDispatch">
            {{ meeting.status === 'dispatched' ? '同步任务变更' : '分发任务' }}
          </el-button>
        </div>
      </header>

      <div v-if="store.loading" class="loading-state">
        <div class="progress-spinner large"></div>
        <p>正在加载会议数据...</p>
      </div>

      <div v-else-if="meeting" class="content-grid">
        <section class="left-pane">
          <div class="pane-card">
            <div class="pane-title"><el-icon><Headset /></el-icon>会议音频</div>
            <audio v-if="meeting.audio_url" :src="meeting.audio_url" controls class="audio-player" />
            <div v-else class="empty-box">当前会议暂无可播放音频。</div>
          </div>

          <div class="pane-card transcript-card">
            <div class="pane-title-row">
              <div class="pane-title"><el-icon><Document /></el-icon>逐字稿</div>
              <div v-if="!isReadOnly" class="inline-actions">
                <el-button plain @click="openSpeakerDialog">修改发言人姓名</el-button>
              </div>
            </div>
            <div class="transcript-list">
              <div
                v-for="seg in meeting.transcript || []"
                :key="seg.id || `${seg.start_ms}-${seg.end_ms}`"
                class="seg-item"
              >
                <div class="seg-meta">
                  <div class="seg-time">{{ msToTime(seg.start_ms) }}</div>
                  <div class="seg-speaker">{{ transcriptSpeaker(seg) }}</div>
                </div>
                <div class="seg-text">{{ transcriptText(seg) }}</div>
              </div>
            </div>
          </div>
        </section>

        <section class="right-pane">
          <div class="tabs-row">
            <button class="tab-btn" :class="{ active: activeTab === 'summary' }" @click="switchTab('summary')">
              <span>摘要决议</span>
              <span class="tab-count">{{ editedDecisions.length }}</span>
            </button>
            <button class="tab-btn" :class="{ active: activeTab === 'actions' }" @click="switchTab('actions')">
              <span>行动项</span>
              <span class="tab-count">{{ editedActions.length }}</span>
            </button>
            <button class="tab-btn" :class="{ active: activeTab === 'template' }" @click="switchTab('template')">
              <span>模板纪要</span>
            </button>
          </div>

          <div v-show="activeTab === 'summary'" class="pane-card detail-panel">
            <div class="pane-title-row">
              <div class="pane-title"><el-icon><ChatDotRound /></el-icon>会议摘要</div>
              <div v-if="!isReadOnly" class="inline-actions">
                <el-button plain :loading="regenLoading" @click="regenWithLLM(false)">AI 分析</el-button>
                <el-button type="primary" plain :loading="regenAndSaveLoading" @click="regenWithLLM(true)">AI 分析并保存</el-button>
              </div>
            </div>

            <el-input
              v-model="editedSummary"
              :disabled="isReadOnly"
              type="textarea"
              :rows="5"
              placeholder="请输入会议摘要"
            />

            <div class="section-block">
              <div class="section-label">核心决议</div>
              <div v-for="(item, index) in editedDecisions" :key="index" class="decision-row">
                <el-input v-model="editedDecisions[index]" :disabled="isReadOnly" placeholder="请输入决议内容" />
                <el-button v-if="!isReadOnly" text type="danger" @click="removeDecision(index)">删除</el-button>
              </div>
              <el-button v-if="!isReadOnly" text @click="addDecision">+ 添加决议</el-button>
            </div>
          </div>

          <div v-show="activeTab === 'actions'" class="pane-card detail-panel actions-panel">
            <div class="pane-title-row actions-header">
              <div class="actions-heading">
                <div class="pane-title"><el-icon><List /></el-icon>行动项工作台</div>
                <p class="actions-subtitle">逐项确认任务内容、负责人、截止日期和进度备注。</p>
              </div>
              <el-button v-if="!isReadOnly" text @click="addActionRow">+ 添加任务</el-button>
            </div>

            <div v-if="editedActions.length" class="action-stack-layout">
              <aside class="action-sidebar">
                <div class="action-overview-strip">
                  <div class="action-overview-card pending">
                    <span>待处理</span>
                    <strong>{{ actionCounts.pending }}</strong>
                  </div>
                  <div class="action-overview-card in_progress">
                    <span>进行中</span>
                    <strong>{{ actionCounts.in_progress }}</strong>
                  </div>
                  <div class="action-overview-card done">
                    <span>已完成</span>
                    <strong>{{ actionCounts.done }}</strong>
                  </div>
                  <div class="action-overview-progress">
                    <div class="action-overview-progress__head">
                      <span>完成进度</span>
                      <strong>{{ completionRatio }}%</strong>
                    </div>
                    <div class="action-overview-progress__track">
                      <span class="action-overview-progress__fill" :style="{ width: `${completionRatio}%` }"></span>
                    </div>
                  </div>
                </div>

                <div class="action-switcher">
                  <div class="action-switcher-meta">
                    <span class="action-switcher-title">当前行动项</span>
                    <span class="action-switcher-count">{{ activeActionIndex + 1 }} / {{ editedActions.length }}</span>
                  </div>
                  <div class="action-switcher-focus">
                    <strong>{{ currentActionOwner }}</strong>
                    <span :class="['action-switcher-focus__due', currentActionDueTone.tone]">{{ currentActionDueTone.text }}</span>
                  </div>
                  <div class="action-switcher-actions">
                    <el-button size="small" :disabled="activeActionIndex === 0" @click="goPrevAction">上一项</el-button>
                    <el-button size="small" :disabled="activeActionIndex === editedActions.length - 1" @click="goNextAction">下一项</el-button>
                  </div>
                </div>

                <div class="action-stack-tabs">
                  <button
                    v-for="(row, index) in editedActions"
                    :key="row.id || index"
                    class="action-stack-tab"
                    :class="[statusClass(row.status), { active: index === activeActionIndex, highlighted: String(row.id) === highlightedActionId }]"
                    @click="switchAction(index)"
                  >
                    <span class="tab-index">{{ index + 1 }}</span>
                    <span class="action-stack-tab__body">
                      <span class="tab-text">{{ row.content || '未填写任务内容' }}</span>
                      <span class="tab-meta">
                        {{ row.owner_name || '未指定负责人' }}
                        <span aria-hidden="true">·</span>
                        {{ row.due_date || '未设截止日期' }}
                      </span>
                    </span>
                  </button>
                </div>
              </aside>

              <div v-if="currentAction" class="action-stage">
                <Transition name="action-sheet" mode="out-in">
                  <div
                    :key="currentAction.id || activeActionIndex"
                    class="action-item current"
                    :class="[statusClass(currentAction.status), { highlighted: String(currentAction.id) === highlightedActionId }]"
                    :style="currentActionTransitionStyle"
                  >
                    <div class="action-main">
                      <div class="action-index">{{ activeActionIndex + 1 }}</div>
                      <div class="action-content-wrap">
                        <div class="action-topline">
                          <div class="action-panel-header">
                            <p class="action-panel-title">当前任务详情</p>
                            <p class="action-panel-sub">{{ currentActionDueTone.description }}</p>
                          </div>
                          <div class="action-top-actions">
                            <span class="action-status-badge" :class="statusClass(currentAction.status)">
                              {{ actionStatusText(currentAction.status) }}
                            </span>
                            <el-button v-if="!isReadOnly" text type="danger" @click="removeRow(activeActionIndex)">删除</el-button>
                          </div>
                        </div>

                        <div class="action-meta-list">
                          <span class="action-meta"><strong>负责人：</strong>{{ currentAction.owner_name || '未指定' }}</span>
                          <span class="action-meta" :class="currentActionDueTone.tone"><strong>截止：</strong>{{ currentAction.due_date || '未设置' }}</span>
                          <span v-if="currentAction.progress_note" class="action-meta"><strong>备注：</strong>已填写</span>
                        </div>

                        <div class="action-edit-list">
                          <div class="action-edit-row">
                            <div class="action-edit-label">具体任务</div>
                            <div class="action-edit-control">
                              <el-input
                                v-model="currentAction.content"
                                :disabled="isReadOnly"
                                type="textarea"
                                :rows="3"
                                placeholder="请输入具体任务内容，例如：整理需求清单并在周五前同步评审结论"
                                @change="markActionUpdated(currentAction)"
                              />
                            </div>
                          </div>

                          <div class="action-edit-row">
                            <div class="action-edit-label">负责人</div>
                            <div class="action-edit-control">
                              <el-select
                                v-model="currentAction.owner_id"
                                :disabled="isReadOnly"
                                placeholder="请选择负责人"
                                @change="value => updateOwner(currentAction, value)"
                              >
                                <el-option v-for="contact in store.contacts" :key="contact.id" :label="contact.name" :value="contact.id" />
                              </el-select>
                            </div>
                          </div>

                          <div class="action-edit-row">
                            <div class="action-edit-label">截止日期</div>
                            <div class="action-edit-control">
                              <el-date-picker
                                v-model="currentAction.due_date"
                                :disabled="isReadOnly"
                                type="date"
                                format="YYYY-MM-DD"
                                value-format="YYYY-MM-DD"
                                placeholder="截止日期"
                                @change="markActionUpdated(currentAction)"
                                style="width: 100%;"
                              />
                            </div>
                          </div>

                          <div class="action-edit-row">
                            <div class="action-edit-label">进度状态</div>
                            <div class="action-edit-control">
                              <el-select
                                v-model="currentAction.status"
                                :disabled="isReadOnly"
                                placeholder="请选择状态"
                                @change="markActionUpdated(currentAction)"
                              >
                                <el-option label="待处理" value="pending" />
                                <el-option label="进行中" value="in_progress" />
                                <el-option label="已完成" value="done" />
                              </el-select>
                            </div>
                          </div>

                          <div class="action-edit-row note-row">
                            <div class="action-edit-label">进度备注 / 回复说明</div>
                            <div class="action-edit-control">
                              <el-input
                                v-model="currentAction.progress_note"
                                :disabled="isReadOnly"
                                type="textarea"
                                :rows="5"
                                placeholder="填写当前处理进展、风险说明或回复内容"
                                @change="markActionUpdated(currentAction)"
                              />
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </Transition>
              </div>
            </div>

            <div v-else class="empty-box action-empty">当前没有行动项。</div>
          </div>

          <div v-show="activeTab === 'template'" class="pane-card detail-panel">
            <div class="pane-title-row">
              <div class="pane-title"><el-icon><DocumentAdd /></el-icon>模板纪要</div>
              <div class="inline-actions">
                <el-button plain :loading="loadingTemplates" @click="loadTemplates">刷新模板</el-button>
                <el-button v-if="!isReadOnly" type="primary" plain :loading="generatingTemplateMinutes" @click="generateTemplateMinutes">生成纪要</el-button>
                <el-button :disabled="!templateMinutes" @click="downloadTemplateMinutes">下载</el-button>
              </div>
            </div>

            <div class="template-toolbar">
              <el-select v-model="selectedTemplateId" :disabled="isReadOnly" placeholder="选择模板" style="width: 240px" @change="handleTemplateChange">
                <el-option v-for="item in templates" :key="item.id" :label="item.name" :value="item.id" />
              </el-select>
              <el-button v-if="!isReadOnly" @click="createTemplate">新建</el-button>
              <el-button v-if="!isReadOnly" @click="saveTemplate">保存</el-button>
              <el-button v-if="!isReadOnly" @click="saveAsTemplate">另存为</el-button>
              <el-button v-if="!isReadOnly" text type="danger" :disabled="!selectedTemplateId" @click="deleteCurrentTemplate">删除</el-button>
            </div>

            <div class="section-block">
              <div class="section-label">模板内容</div>
              <el-input v-model="templateContent" :disabled="isReadOnly" type="textarea" :rows="8" placeholder="请输入纪要模板内容" />
            </div>

            <div class="section-block">
              <div class="section-label">生成结果</div>
              <el-input v-model="templateMinutes" :disabled="isReadOnly" type="textarea" :rows="10" placeholder="生成后的会议纪要将显示在这里" />
            </div>
          </div>
        </section>
      </div>
    </div>

    <el-dialog
      v-model="speakerDialogVisible"
      title="修改发言人姓名"
      width="520px"
      destroy-on-close
    >
      <div class="speaker-dialog-list">
        <div
          v-for="item in speakerMappings"
          :key="item.original"
          class="speaker-dialog-row"
        >
          <div class="speaker-dialog-source">{{ item.original }}</div>
          <el-input
            v-model="item.target"
            maxlength="64"
            placeholder="请输入发言人名称"
            @keyup.enter="submitSpeakerChange"
          />
        </div>
      </div>
      <template #footer>
        <el-button @click="speakerDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="speakerSaving" @click="submitSpeakerChange">保存</el-button>
      </template>
    </el-dialog>
  </MainLayout>
</template>
<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ArrowLeft,
  ChatDotRound,
  Document,
  DocumentAdd,
  Headset,
  List,
} from '@element-plus/icons-vue'
import MainLayout from '../components/MainLayout.vue'
import { useMeetingStore } from '../stores/meetingStore.js'
import api from '../services/api.js'

const route = useRoute()
const router = useRouter()
const store = useMeetingStore()

const activeTab = ref('summary')
const activeActionIndex = ref(0)
const editedSummary = ref('')
const editedDecisions = ref([])
const editedActions = ref([])
const saving = ref(false)
const dispatching = ref(false)
const regenLoading = ref(false)
const regenAndSaveLoading = ref(false)
const generatingTemplateMinutes = ref(false)
const templates = ref([])
const selectedTemplateId = ref(null)
const templateContent = ref('')
const templateMinutes = ref('')
const loadingTemplates = ref(false)
const speakerDialogVisible = ref(false)
const speakerSaving = ref(false)
const speakerMappings = ref([])

const meeting = computed(() => store.currentMeeting)
const isReadOnly = computed(() => {
  if (route.query.readonly === '1' || route.query.from === 'todo') return true
  return meeting.value?.can_edit === false
})
const highlightedActionId = computed(() => String(route.query.actionId || ''))
const currentAction = computed(() => editedActions.value[activeActionIndex.value] || null)
const actionCounts = computed(() => {
  return editedActions.value.reduce((acc, item) => {
    const key = statusClass(item.status)
    acc[key] += 1
    return acc
  }, { pending: 0, in_progress: 0, done: 0 })
})
const completionRatio = computed(() => {
  if (!editedActions.value.length) return 0
  return Math.round((actionCounts.value.done / editedActions.value.length) * 100)
})
const currentActionOwner = computed(() => currentAction.value?.owner_name || '未指定负责人')
const currentActionDueTone = computed(() => describeActionDue(currentAction.value))
const currentActionTransitionStyle = computed(() => {
  if (!currentAction.value || String(currentAction.value.id) !== highlightedActionId.value) return {}
  return { viewTransitionName: actionTransitionName(currentAction.value.id) }
})

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
  }[status] || 'review'
}

function actionStatusText(status) {
  return {
    pending: '待处理',
    in_progress: '进行中',
    done: '已完成',
  }[status] || '待处理'
}

function statusClass(status) {
  return {
    pending: 'pending',
    in_progress: 'in_progress',
    done: 'done',
  }[status] || 'pending'
}

function formatDuration(sec) {
  if (!sec) return '--'
  const hour = Math.floor(sec / 3600)
  const minute = Math.floor((sec % 3600) / 60)
  return hour > 0 ? `${hour}小时 ${minute}分钟` : `${minute}分钟`
}

function msToTime(ms) {
  const totalSec = Math.floor((ms || 0) / 1000)
  const min = Math.floor(totalSec / 60)
  const sec = totalSec % 60
  return `${String(min).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
}

function transcriptSpeaker(seg) {
  if (seg?.speaker) return seg.speaker
  const text = String(seg?.text || '')
  const matched = text.match(/^\[(SPEAKER_[^\]]+)\]\s*/i)
  return matched?.[1] || 'SPEAKER_00'
}

function transcriptText(seg) {
  const text = String(seg?.text || '')
  return text.replace(/^\[(SPEAKER_[^\]]+)\]\s*/i, '')
}

function openSpeakerDialog() {
  const seen = new Set()
  speakerMappings.value = (meeting.value?.transcript || [])
    .map((seg) => transcriptSpeaker(seg))
    .filter((speaker) => {
      if (seen.has(speaker)) return false
      seen.add(speaker)
      return true
    })
    .map((speaker) => ({
      original: speaker,
      target: speaker,
    }))
  speakerDialogVisible.value = true
}

async function submitSpeakerChange() {
  const mappings = Object.fromEntries(
    speakerMappings.value
      .map((item) => [String(item.original || "").trim(), String(item.target || "").trim()])
      .filter(([source, target]) => source && target && source !== target)
  )
  if (!Object.keys(mappings).length) {
    speakerDialogVisible.value = false
    return
  }

  speakerSaving.value = true
  try {
    await api.put(`/meetings/${route.params.id}/transcripts/speakers`, { mappings })
    for (const seg of meeting.value?.transcript || []) {
      const currentSpeaker = transcriptSpeaker(seg)
      if (mappings[currentSpeaker]) seg.speaker = mappings[currentSpeaker]
    }
    speakerDialogVisible.value = false
    ElMessage.success('发言人已批量更新')
  } catch (error) {
    ElMessage.error('更新失败：' + (error.response?.data?.detail || error.message))
  } finally {
    speakerSaving.value = false
  }
}

function syncEditableState() {
  editedSummary.value = meeting.value?.summary || ''
  editedDecisions.value = Array.isArray(meeting.value?.decisions) ? [...meeting.value.decisions] : []
  editedActions.value = Array.isArray(meeting.value?.action_items)
    ? meeting.value.action_items.map((item) => ({ ...item, progress_note: item.progress_note || '' }))
    : []
  syncActiveActionIndex()
}

function syncActiveActionIndex() {
  if (!editedActions.value.length) {
    activeActionIndex.value = 0
    return
  }
  const highlightedIndex = editedActions.value.findIndex((item) => String(item.id) === highlightedActionId.value)
  if (highlightedIndex >= 0) {
    activeActionIndex.value = highlightedIndex
    return
  }
  if (activeActionIndex.value > editedActions.value.length - 1) {
    activeActionIndex.value = editedActions.value.length - 1
  }
}

function withViewTransition(update) {
  if (typeof document !== 'undefined' && 'startViewTransition' in document) {
    document.startViewTransition(() => {
      update()
    })
    return
  }
  update()
}

function switchTab(tab) {
  if (activeTab.value === tab) return
  withViewTransition(() => {
    activeTab.value = tab
  })
}

function switchAction(index) {
  if (index < 0 || index > editedActions.value.length - 1) return
  if (activeActionIndex.value === index) return
  withViewTransition(() => {
    activeActionIndex.value = index
  })
}

function goPrevAction() {
  if (activeActionIndex.value > 0) switchAction(activeActionIndex.value - 1)
}

function goNextAction() {
  if (activeActionIndex.value < editedActions.value.length - 1) switchAction(activeActionIndex.value + 1)
}

function addDecision() {
  editedDecisions.value.push('')
}

function removeDecision(index) {
  editedDecisions.value.splice(index, 1)
}

function addActionRow() {
  editedActions.value.push({
    id: Date.now(),
    owner_id: '',
    owner_name: '',
    content: '',
    due_date: '',
    status: 'pending',
    progress_note: '',
    updated_after_dispatch: meeting.value?.status === 'dispatched',
    last_dispatched_at: null,
  })
  switchAction(editedActions.value.length - 1)
}

function removeRow(index) {
  editedActions.value.splice(index, 1)
  syncActiveActionIndex()
}

function updateOwner(row, value) {
  const contact = store.contacts.find((item) => item.id === value)
  row.owner_name = contact?.name || ''
  markActionUpdated(row)
}

function markActionUpdated(row) {
  if (meeting.value?.status === 'dispatched') {
    row.updated_after_dispatch = true
  }
}

function actionTransitionName(id) {
  return `todo-action-${id}`
}

function describeActionDue(action) {
  if (!action?.due_date) {
    return {
      tone: 'neutral',
      text: '未设置截止日期',
      description: '建议补充截止日期，方便按优先级推进处理。',
    }
  }

  const dueDate = new Date(`${action.due_date}T00:00:00`)
  if (Number.isNaN(dueDate.getTime())) {
    return {
      tone: 'neutral',
      text: action.due_date,
      description: '请确认截止日期格式，避免后续跟进出现歧义。',
    }
  }

  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const diffDays = Math.ceil((dueDate.getTime() - today.getTime()) / 86400000)

  if (action.status === 'done') {
    return {
      tone: 'done',
      text: '已完成',
      description: '这项任务已完成，仍可补充说明或复核负责人信息。',
    }
  }

  if (diffDays < 0) {
    return {
      tone: 'overdue',
      text: `已逾期 ${Math.abs(diffDays)} 天`,
      description: '这项任务已逾期，建议先补充最新进展或更新截止日期。',
    }
  }

  if (diffDays === 0) {
    return {
      tone: 'urgent',
      text: '今天截止',
      description: '这项任务今天截止，建议尽快确认最新进度。',
    }
  }

  if (diffDays <= 2) {
    return {
      tone: 'urgent',
      text: `${diffDays} 天后截止`,
      description: '这项任务接近截止时间，建议优先确认负责人和回复说明。',
    }
  }

  return {
    tone: 'normal',
    text: `${diffDays} 天后截止`,
    description: '当前节奏正常，可以继续完善处理说明和责任人信息。',
  }
}

async function saveMeeting() {
  if (isReadOnly.value) return
  saving.value = true
  try {
    await store.confirmMeeting(route.params.id, {
      summary: editedSummary.value,
      decisions: editedDecisions.value.filter(Boolean),
      action_items: editedActions.value,
    })
    await store.fetchMeeting(route.params.id)
    syncEditableState()
    ElMessage.success('会议已保存')
  } catch (error) {
    ElMessage.error('保存失败：' + (error.response?.data?.detail || error.message))
  } finally {
    saving.value = false
  }
}

async function regenWithLLM(autoSave = false) {
  if (isReadOnly.value) return
  if (!meeting.value?.transcript?.length) {
    ElMessage.warning('当前没有逐字稿数据')
    return
  }
  if (autoSave) regenAndSaveLoading.value = true
  else regenLoading.value = true

  try {
    const res = await api.post('/ai/analyze-meeting', { meeting_id: route.params.id })
    const data = res.data
    if (data.summary) editedSummary.value = data.summary
    if (Array.isArray(data.decisions)) editedDecisions.value = data.decisions
    if (Array.isArray(data.action_items)) {
      editedActions.value = data.action_items.map((item, index) => {
        const contact = store.contacts.find((c) => c.name === item.owner_name)
        return {
          id: Date.now() + index,
          owner_id: contact?.id || '',
          owner_name: item.owner_name || '',
          content: item.content || '',
          due_date: item.due_date || '',
          status: item.status || 'pending',
          progress_note: item.progress_note || '',
          updated_after_dispatch: meeting.value?.status === 'dispatched',
          last_dispatched_at: null,
        }
      })
    }
    if (autoSave) await saveMeeting()
    else ElMessage.success('AI 分析完成')
  } catch (error) {
    ElMessage.error('AI 分析失败：' + (error.response?.data?.detail || error.message))
  } finally {
    regenLoading.value = false
    regenAndSaveLoading.value = false
  }
}

async function handleDispatch() {
  if (isReadOnly.value) return
  try {
    await saveMeeting()
    dispatching.value = true
    if (meeting.value?.status === 'dispatched') {
      const res = await api.post(`/meetings/${route.params.id}/resync`)
      ElMessage.success(`已同步 ${res.data.changed_count || 0} 条变更任务`)
    } else {
      await store.dispatchMeeting(route.params.id)
      ElMessage.success('任务已分发')
    }
    await store.fetchMeeting(route.params.id)
    syncEditableState()
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      dispatching.value = false
      return
    }
    ElMessage.error('分发失败：' + (error.response?.data?.detail || error.message))
  } finally {
    dispatching.value = false
  }
}

async function loadTemplates() {
  loadingTemplates.value = true
  try {
    const res = await api.get('/templates')
    templates.value = res.data || []
    const defaultTemplate = templates.value.find((item) => item.is_default) || templates.value[0]
    if (defaultTemplate && !selectedTemplateId.value) {
      selectedTemplateId.value = defaultTemplate.id
      handleTemplateChange(defaultTemplate.id)
    }
  } catch (error) {
    ElMessage.error('模板加载失败：' + (error.response?.data?.detail || error.message))
  } finally {
    loadingTemplates.value = false
  }
}

function handleTemplateChange(id) {
  const template = templates.value.find((item) => item.id === id)
  templateContent.value = template?.content || ''
}

async function createTemplate() {
  if (isReadOnly.value) return
  try {
    const { value } = await ElMessageBox.prompt('请输入模板名称', '新建模板', {
      inputValue: '新模板',
      inputValidator: (inputValue) => !!inputValue?.trim() || '请输入模板名称',
    })
    const res = await api.post('/templates', {
      name: value.trim(),
      content: templateContent.value || '模板内容',
      is_default: false,
    })
    selectedTemplateId.value = res.data.id
    await loadTemplates()
    ElMessage.success('模板已创建')
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error('创建失败：' + (error.response?.data?.detail || error.message))
  }
}

async function saveTemplate() {
  if (isReadOnly.value) return
  if (!selectedTemplateId.value) {
    await createTemplate()
    return
  }
  try {
    await api.put(`/templates/${selectedTemplateId.value}`, { content: templateContent.value })
    await loadTemplates()
    ElMessage.success('模板已保存')
  } catch (error) {
    ElMessage.error('保存失败：' + (error.response?.data?.detail || error.message))
  }
}

async function saveAsTemplate() {
  if (isReadOnly.value) return
  try {
    const { value } = await ElMessageBox.prompt('请输入新的模板名称', '另存为', {
      inputValue: '',
      inputValidator: (inputValue) => !!inputValue?.trim() || '请输入模板名称',
    })
    const res = await api.post('/templates', {
      name: value.trim(),
      content: templateContent.value || '模板内容',
      is_default: false,
    })
    selectedTemplateId.value = res.data.id
    await loadTemplates()
    ElMessage.success('模板已创建')
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error('另存失败：' + (error.response?.data?.detail || error.message))
  }
}

async function deleteCurrentTemplate() {
  if (isReadOnly.value || !selectedTemplateId.value) return
  try {
    await ElMessageBox.confirm('确认删除当前模板吗？', '删除确认', { type: 'warning' })
    await api.delete(`/templates/${selectedTemplateId.value}`)
    selectedTemplateId.value = null
    templateContent.value = ''
    await loadTemplates()
    ElMessage.success('模板已删除')
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error('删除失败：' + (error.response?.data?.detail || error.message))
  }
}

async function generateTemplateMinutes() {
  if (isReadOnly.value) return
  if (!templateContent.value.trim()) {
    ElMessage.warning('请先输入模板内容')
    return
  }
  generatingTemplateMinutes.value = true
  try {
    const res = await api.post('/ai/template-minutes', {
      meeting_id: route.params.id,
      template_content: templateContent.value,
    })
    templateMinutes.value = res.data.content || ''
    ElMessage.success('纪要生成成功')
  } catch (error) {
    ElMessage.error('生成失败：' + (error.response?.data?.detail || error.message))
  } finally {
    generatingTemplateMinutes.value = false
  }
}

function downloadTemplateMinutes() {
  if (!templateMinutes.value) return
  const safeTitle = (meeting.value?.name || 'meeting-minutes').replace(/[\\/:*?"<>|]/g, '-')
  const blob = new Blob([templateMinutes.value], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${safeTitle}.txt`
  link.click()
  URL.revokeObjectURL(url)
}

watch(meeting, () => {
  syncEditableState()
}, { immediate: true })

watch(activeTab, (value) => {
  localStorage.setItem(`smartsync_meeting_tab_${route.params.id}`, value)
})

watch(
  () => route.params.id,
  async (id, previousId) => {
    if (!id || id === previousId) return
    activeTab.value = route.query.tab || localStorage.getItem(`smartsync_meeting_tab_${id}`) || 'summary'
    await store.fetchMeeting(id)
    syncEditableState()
  }
)

watch(
  () => route.query.tab,
  (tab) => {
    if (typeof tab === 'string' && tab) {
      activeTab.value = tab
    }
  }
)

onMounted(async () => {
  activeTab.value = route.query.tab || localStorage.getItem(`smartsync_meeting_tab_${route.params.id}`) || 'summary'
  await store.fetchContacts()
  await store.fetchMeeting(route.params.id)
  syncEditableState()
  await loadTemplates()
})
</script>

<style scoped>
.detail-page { max-width: 1480px; margin: 0 auto; padding: clamp(20px, 3vw, 32px); min-height: 100vh; height: 100vh; box-sizing: border-box; display: flex; flex-direction: column; overflow: hidden; }
.topbar { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: 18px; align-items: center; margin-bottom: 16px; flex-shrink: 0; }
.topbar-main h1 { font-size: clamp(30px, 4vw, 48px); line-height: 1; letter-spacing: -.05em; color: var(--text); }
.topbar-eyebrow { font-size: 12px; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; color: var(--text-muted); margin-bottom: 8px; }
.topbar-meta { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 10px; color: var(--text-muted); }
.topbar-actions { display: flex; gap: 10px; flex-wrap: wrap; }
.meeting-status, .readonly-chip { display: inline-flex; align-items: center; min-height: 28px; padding: 0 12px; border-radius: 999px; border: 1px solid var(--border); }
.readonly-chip { color: var(--warning); background: color-mix(in oklab, var(--warning) 10%, transparent); }
.meeting-status.tag-uploading { color: var(--primary); background: color-mix(in oklab, var(--primary) 10%, transparent); }
.meeting-status.tag-processing { color: var(--accent); background: color-mix(in oklab, var(--accent) 10%, transparent); }
.meeting-status.tag-review { color: var(--warning); background: color-mix(in oklab, var(--warning) 10%, transparent); }
.meeting-status.tag-dispatched { color: var(--success); background: color-mix(in oklab, var(--success) 10%, transparent); }
.content-grid { display: grid; grid-template-columns: minmax(300px, 400px) minmax(0, 1fr); gap: 18px; min-height: 0; flex: 1; overflow: hidden; align-items: stretch; }
.left-pane, .right-pane { display: flex; flex-direction: column; gap: 14px; min-height: 0; overflow: hidden; }
.pane-card { border: 1px solid var(--border); background: color-mix(in oklab, var(--bg-card) 88%, var(--bg) 12%); border-radius: 24px; box-shadow: var(--shadow); padding: 18px; min-height: 0; }
.detail-panel { min-height: 0; flex: 1; display: flex; flex-direction: column; overflow: auto; }
.actions-panel { overflow: hidden; }
.pane-title, .pane-title-row { display: flex; align-items: center; gap: 10px; color: var(--text); font-weight: 700; }
.pane-title-row { justify-content: space-between; margin-bottom: 16px; }
.inline-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.audio-player { width: 100%; }
.empty-box { min-height: 120px; display: grid; place-items: center; color: var(--text-muted); border: 1px dashed var(--border); border-radius: 18px; text-align: center; padding: 18px; }
.transcript-card { min-height: 0; flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.transcript-list { display: flex; flex-direction: column; gap: 6px; flex: 1; min-height: 0; overflow: auto; padding-right: 4px; }
.seg-item { position: relative; display: grid; grid-template-columns: 112px minmax(0, 1fr); gap: 10px; align-items: start; border: 1px solid color-mix(in oklab, var(--border) 88%, transparent); border-radius: 14px; padding: 8px 10px; background: color-mix(in oklab, var(--bg) 84%, var(--bg-card) 16%); }
.seg-item::before { content: ''; position: absolute; left: 0; top: 8px; bottom: 8px; width: 3px; border-radius: 999px; background: color-mix(in oklab, var(--primary) 42%, transparent); opacity: .7; }
.seg-meta { display: flex; flex-direction: column; gap: 6px; }
.seg-time { display: inline-flex; align-items: center; justify-content: center; min-height: 24px; padding: 0 8px; border-radius: 999px; background: color-mix(in oklab, var(--bg-card) 92%, var(--bg) 8%); color: var(--text-muted); margin-bottom: 0; line-height: 1; font-size: 11px; font-weight: 700; letter-spacing: .02em; }
.seg-speaker { display: inline-flex; align-items: center; justify-content: center; min-height: 24px; padding: 0 10px; border-radius: 999px; background: color-mix(in oklab, var(--primary) 14%, var(--bg-card)); color: color-mix(in oklab, var(--primary) 72%, var(--text)); font-size: 11px; font-weight: 700; letter-spacing: .02em; }
.seg-text { color: var(--text); line-height: 1.5; font-size: 13px; white-space: pre-wrap; word-break: break-word; }
.speaker-dialog-list { display: flex; flex-direction: column; gap: 12px; }
.speaker-dialog-row { display: grid; grid-template-columns: 140px minmax(0, 1fr); gap: 12px; align-items: center; }
.speaker-dialog-source { display: inline-flex; align-items: center; min-height: 38px; padding: 0 12px; border-radius: 12px; background: color-mix(in oklab, var(--primary) 10%, var(--bg-card)); color: color-mix(in oklab, var(--primary) 68%, var(--text)); font-size: 12px; font-weight: 700; }
.tabs-row { display: flex; gap: 10px; margin-bottom: 14px; flex-wrap: wrap; flex-shrink: 0; }
.tab-btn { min-height: 42px; padding: 0 16px; border-radius: 999px; border: 1px solid var(--border); background: transparent; color: var(--text-muted); cursor: pointer; display: inline-flex; align-items: center; gap: 10px; transition: border-color .18s ease, background .18s ease, color .18s ease, transform .18s ease; }
.tab-btn:hover { transform: translateY(-1px); border-color: color-mix(in oklab, var(--primary) 18%, var(--border)); }
.tab-btn.active { color: var(--text); border-color: var(--border-strong); background: color-mix(in oklab, var(--primary) 10%, var(--bg-card)); }
.tab-count { min-width: 22px; height: 22px; padding: 0 7px; border-radius: 999px; display: inline-flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 700; background: color-mix(in oklab, var(--primary) 12%, transparent); color: var(--text); }
.section-block { margin-top: 18px; }
.section-label { margin-bottom: 10px; color: var(--text-muted); font-size: 12px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; }
.decision-row { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 10px; margin-bottom: 10px; }
.actions-header { align-items: center; }
.actions-heading { min-width: 0; }
.actions-subtitle { margin: 6px 0 0; color: var(--text-muted); font-size: 13px; line-height: 1.6; }
.action-stack-layout { display: grid; grid-template-columns: 300px minmax(0, 1fr); gap: 16px; align-items: start; min-height: 0; height: 100%; }
.action-sidebar { display: flex; flex-direction: column; gap: 12px; min-height: 0; max-height: 100%; }
.action-overview-strip { display: grid; gap: 8px; }
.action-overview-card,
.action-overview-progress { border: 1px solid var(--border); border-radius: 16px; background: color-mix(in oklab, var(--bg) 84%, var(--bg-card) 16%); padding: 12px 14px; }
.action-overview-card { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
.action-overview-card span { font-size: 12px; color: var(--text-muted); }
.action-overview-card strong { font-size: 1.05rem; color: var(--text); letter-spacing: -.03em; }
.action-overview-card.pending { border-left: 3px solid var(--warning); }
.action-overview-card.in_progress { border-left: 3px solid var(--accent); }
.action-overview-card.done { border-left: 3px solid var(--success); }
.action-overview-progress__head { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; margin-bottom: 10px; }
.action-overview-progress__head span { font-size: 12px; color: var(--text-muted); }
.action-overview-progress__head strong { color: var(--text); font-size: 1rem; }
.action-overview-progress__track { height: 8px; border-radius: 999px; background: color-mix(in oklab, var(--primary) 8%, var(--bg)); overflow: hidden; }
.action-overview-progress__fill { display: block; height: 100%; border-radius: inherit; background: linear-gradient(90deg, color-mix(in oklab, var(--primary) 70%, var(--accent) 30%), color-mix(in oklab, var(--success) 72%, var(--primary) 28%)); transition: width .28s ease; }
.action-switcher { display: flex; flex-direction: column; gap: 12px; padding: 12px 14px; border: 1px solid var(--border); border-radius: 16px; background: color-mix(in oklab, var(--bg) 84%, var(--bg-card) 16%); }
.action-switcher-meta { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
.action-switcher-title { font-size: 13px; font-weight: 700; color: var(--text); }
.action-switcher-count { font-size: 12px; color: var(--text-muted); }
.action-switcher-focus { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.action-switcher-focus strong { color: var(--text); font-size: 13px; }
.action-switcher-focus__due { font-size: 12px; color: var(--text-muted); }
.action-switcher-focus__due.urgent,
.action-meta.urgent { color: var(--warning); }
.action-switcher-focus__due.overdue,
.action-meta.overdue { color: var(--danger); }
.action-switcher-focus__due.done,
.action-meta.done { color: var(--success); }
.action-switcher-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.action-stack-tabs { display: flex; flex-direction: column; gap: 8px; overflow-y: auto; padding-right: 4px; }
.action-stack-tab { width: 100%; min-width: 0; display: flex; align-items: center; gap: 10px; padding: 10px 12px; border-radius: 14px; border: 1px solid var(--border); background: color-mix(in oklab, var(--bg) 88%, var(--bg-card) 12%); color: var(--text-muted); cursor: pointer; text-align: left; transition: all .2s ease; }
.action-stack-tab.active { color: var(--text); border-color: color-mix(in oklab, var(--primary) 30%, var(--border)); background: color-mix(in oklab, var(--primary) 8%, var(--bg-card)); }
.action-stack-tab.highlighted { box-shadow: inset 0 0 0 1px color-mix(in oklab, var(--primary) 24%, transparent); }
.action-stack-tab.pending { border-left: 3px solid var(--warning); }
.action-stack-tab.in_progress { border-left: 3px solid var(--accent); }
.action-stack-tab.done { border-left: 3px solid var(--success); }
.tab-index { width: 24px; height: 24px; display: grid; place-items: center; border-radius: 8px; background: color-mix(in oklab, var(--primary) 10%, transparent); color: var(--text); font-size: 12px; font-weight: 800; flex-shrink: 0; }
.action-stack-tab__body { min-width: 0; display: flex; flex-direction: column; gap: 4px; }
.tab-text {
  font-size: 12px;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.tab-meta { font-size: 11px; color: var(--text-soft); display: inline-flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.action-stage { position: relative; padding-bottom: 28px; min-height: 0; overflow: auto; }
.action-item { border: 1px solid var(--border); border-radius: 18px; background: color-mix(in oklab, var(--bg) 84%, var(--bg-card) 16%); padding: 16px 18px; transition: all .2s ease; }
.action-item.current { position: relative; z-index: 2; }
.action-item.highlighted { border-color: color-mix(in oklab, var(--primary) 38%, var(--border)); box-shadow: 0 12px 22px color-mix(in oklab, var(--primary) 10%, transparent); }
.action-item.pending { border-left: 4px solid var(--warning); }
.action-item.in_progress { border-left: 4px solid var(--accent); }
.action-item.done { border-left: 4px solid var(--success); }
.action-main { display: grid; grid-template-columns: 36px minmax(0, 1fr); gap: 14px; align-items: start; }
.action-index { width: 36px; height: 36px; display: grid; place-items: center; border-radius: 12px; background: color-mix(in oklab, var(--primary) 8%, var(--bg-card)); color: var(--text); font-weight: 800; }
.action-content-wrap { min-width: 0; }
.action-topline { display: flex; justify-content: space-between; gap: 14px; align-items: start; }
.action-panel-header { min-width: 0; }
.action-panel-title { margin: 0; font-size: 15px; line-height: 1.5; color: var(--text); font-weight: 700; }
.action-panel-sub { margin: 4px 0 0; font-size: 12px; line-height: 1.6; color: var(--text-muted); }
.action-top-actions { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; flex-shrink: 0; }
.action-meta-list { display: flex; gap: 16px; flex-wrap: wrap; margin-top: 8px; color: var(--text-muted); font-size: 12px; }
.action-meta strong { color: var(--text); font-weight: 700; }
.action-status-badge { display: inline-flex; align-items: center; min-height: 30px; padding: 0 12px; border-radius: 999px; border: 1px solid var(--border); font-size: 12px; font-weight: 700; }
.action-status-badge.pending { color: var(--warning); background: color-mix(in oklab, var(--warning) 12%, transparent); }
.action-status-badge.in_progress { color: var(--accent); background: color-mix(in oklab, var(--accent) 12%, transparent); }
.action-status-badge.done { color: var(--success); background: color-mix(in oklab, var(--success) 12%, transparent); }
.action-edit-list { display: flex; flex-direction: column; gap: 12px; margin-top: 14px; padding-top: 14px; border-top: 1px dashed var(--border); }
.action-edit-row { display: grid; grid-template-columns: 132px minmax(0, 1fr); gap: 14px; align-items: center; }
.action-edit-label { font-size: 13px; font-weight: 700; color: var(--text); }
.action-edit-control { min-width: 0; }
.note-row { align-items: start; }
.action-empty { min-height: 180px; }
.template-toolbar { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 16px; }
.loading-state { min-height: 320px; display: grid; place-items: center; color: var(--text-muted); }
.action-sheet-enter-active,
.action-sheet-leave-active { transition: opacity .24s ease, transform .24s ease; }
.action-sheet-enter-from,
.action-sheet-leave-to { opacity: 0; transform: translateY(8px) scale(.995); }
@media (prefers-reduced-motion: reduce) {
  .tab-btn,
  .action-overview-progress__fill,
  .action-sheet-enter-active,
  .action-sheet-leave-active { transition: none; }
}
@media (max-width: 1120px) {
  .detail-page { min-height: auto; height: auto; display: block; overflow: visible; }
  .content-grid { grid-template-columns: 1fr; flex: none; overflow: visible; }
  .left-pane, .right-pane { min-height: auto; }
  .detail-panel, .actions-panel, .action-stage, .transcript-list { overflow: visible; }
}
@media (max-width: 860px) {
  .topbar { grid-template-columns: 1fr; }
  .content-grid { grid-template-columns: 1fr; }
  .seg-item { grid-template-columns: 1fr; gap: 6px; padding-left: 12px; }
  .seg-item::before { top: 10px; bottom: 10px; }
  .seg-time { justify-self: start; }
  .action-stack-layout { grid-template-columns: 1fr; }
  .action-sidebar { max-height: none; }
  .action-switcher { align-items: stretch; }
  .action-main { grid-template-columns: 1fr; }
  .action-index { display: none; }
  .action-topline { flex-direction: column; }
  .action-edit-row { grid-template-columns: 1fr; gap: 8px; }
  .decision-row { grid-template-columns: 1fr; }
  .speaker-dialog-row { grid-template-columns: 1fr; gap: 8px; }
}
</style>
