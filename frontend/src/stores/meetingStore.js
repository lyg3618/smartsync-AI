import { defineStore } from 'pinia'
import api from '../services/api.js'

export const useMeetingStore = defineStore('meeting', {
  state: () => ({
    meetings: [],
    currentMeeting: null,
    contacts: [],
    uploadProgress: null,
    pollingTimer: null,
    loading: false,
    totalMeetings: 0,
  }),

  actions: {
    async fetchMeetings(page = 1, size = 10) {
      this.loading = true
      try {
        const res = await api.get('/meetings', { params: { page, size } })
        this.meetings = res.data.items
        this.totalMeetings = res.data.total
      } catch (e) {
        console.error(e)
        // Use mock data in dev
        this.meetings = mockMeetings()
        this.totalMeetings = mockMeetings().length
      } finally {
        this.loading = false
      }
    },

    async fetchMeeting(id) {
      this.loading = true
      try {
        const res = await api.get(`/meetings/${id}`)
        this.currentMeeting = res.data
      } catch (e) {
        this.currentMeeting = mockMeetingDetail(id)
      } finally {
        this.loading = false
      }
    },

    async fetchContacts() {
      try {
        const res = await api.get('/contacts')
        this.contacts = res.data
      } catch {
        this.contacts = mockContacts()
      }
    },

    async uploadFile(formData, onProgress) {
      const res = await api.post('/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (e) => {
          if (onProgress) onProgress(Math.round(e.loaded * 100 / e.total))
        },
      })
      return res.data
    },

    async pollStatus(taskId, statusCallback) {
      clearInterval(this.pollingTimer)
      this.pollingTimer = setInterval(async () => {
        try {
          const res = await api.get(`/tasks/${taskId}/status`)
          statusCallback(res.data)
          if (res.data.status === 'ready_for_review' || res.data.status === 'error') {
            clearInterval(this.pollingTimer)
          }
        } catch {
          clearInterval(this.pollingTimer)
        }
      }, 3000)
    },

    async confirmMeeting(id, payload) {
      const res = await api.post(`/meetings/${id}/confirm`, payload)
      return res.data
    },

    async dispatchMeeting(id) {
      const res = await api.post(`/meetings/${id}/dispatch`)
      return res.data
    },

    stopPolling() {
      clearInterval(this.pollingTimer)
    }
  }
})

// ── Mock data for frontend-only preview ──────────────────────────────
function mockMeetings() {
  return [
    { id: '1', name: '2026年Q1产品规划会议', date: '2026-03-01', duration_sec: 3600, task_count: 5, status: 'ready_for_review' },
    { id: '2', name: '技术架构评审会', date: '2026-02-28', duration_sec: 5400, task_count: 8, status: 'dispatched' },
    { id: '3', name: '客户需求对接会', date: '2026-02-27', duration_sec: 2700, task_count: 3, status: 'processing' },
    { id: '4', name: '全员晨会 - 状态同步', date: '2026-02-26', duration_sec: 1200, task_count: 2, status: 'dispatched' },
    { id: '5', name: '风险评估与合规讨论', date: '2026-02-25', duration_sec: 4200, task_count: 6, status: 'ready_for_review' },
  ]
}

function mockContacts() {
  return [
    { id: '1', name: '张伟', email: 'zhang.wei@company.com' },
    { id: '2', name: '李娜', email: 'li.na@company.com' },
    { id: '3', name: '王芳', email: 'wang.fang@company.com' },
    { id: '4', name: '刘洋', email: 'liu.yang@company.com' },
    { id: '5', name: '陈静', email: 'chen.jing@company.com' },
  ]
}

function mockMeetingDetail(id) {
  return {
    id,
    name: 'Q1产品规划会议',
    date: '2026-03-01',
    duration_sec: 3600,
    status: 'ready_for_review',
    audio_url: null,
    transcript: [
      { id: 1, start_ms: 0, end_ms: 12000, text: '大家好，我们今天的主要议题是讨论Q1的产品路线图，重点关注用户增长和功能迭代两条线。' },
      { id: 2, start_ms: 12000, end_ms: 28000, text: '张伟：根据上个季度的数据，我们的DAU已经达到了50万，但是用户留存率在第7天出现了明显下滑，大概是在35%左右。' },
      { id: 3, start_ms: 28000, end_ms: 45000, text: '李娜：我这里的分析表明，主要原因是新用户引导流程太复杂。我建议我们简化注册后的前三步操作，把步骤从7步减少到3步。' },
      { id: 4, start_ms: 45000, end_ms: 62000, text: '王芳：同意，另外用户反馈系统通知太多，导致通知疲劳。我来负责梳理通知策略，争取本月底完成方案。' },
      { id: 5, start_ms: 62000, end_ms: 85000, text: '刘洋：技术层面，我们需要对搜索模块进行重构，现在的响应时间平均是2.3秒，目标要优化到800ms以内。这个工作量大概需要两周。' },
      { id: 6, start_ms: 85000, end_ms: 100000, text: '总结：本次会议确定了三个核心行动项，各负责人需在规定时间内完成并汇报进展。下次会议定在两周后。' },
    ],
    summary: '本次Q1产品规划会议围绕用户增长与功能迭代展开。数据显示DAU达50万，但第7天留存率仅35%，主要原因为引导流程复杂及通知过度。会议确定了三项关键改进措施：简化新用户引导流程、优化通知策略、重构搜索模块以提升响应速度。',
    decisions: ['简化新用户引导流程，从7步减少到3步，目标提升第7天留存至50%', '梳理并优化App内通知策略，减少通知疲劳', '搜索模块响应时间优化至800ms以内'],
    action_items: [
      { id: 1, owner_id: '3', owner_name: '王芳', content: '梳理并重新设计App内通知推送策略，减少日均通知数量至3条以内', due_date: '2026-03-31', status: 'pending' },
      { id: 2, owner_id: '4', owner_name: '刘洋', content: '完成搜索模块架构重构，将P50响应时间优化至800ms以内', due_date: '2026-03-20', status: 'pending' },
      { id: 3, owner_id: '2', owner_name: '李娜', content: '重新设计新用户注册引导流程，步骤从7步简化为3步，并完成A/B测试方案', due_date: '2026-03-15', status: 'pending' },
      { id: 4, owner_id: '1', owner_name: '张伟', content: '输出第7天留存率优化专项报告，含数据基线与改进目标', due_date: '2026-03-10', status: 'pending' },
    ],
  }
}
