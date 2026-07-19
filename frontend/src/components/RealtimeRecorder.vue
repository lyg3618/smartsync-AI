<template>
  <div class="realtime-recorder" :class="{ 'is-active': status !== 'idle' }">
    <el-button
      v-if="status === 'idle'"
      size="large"
      :disabled="disabled"
      @click="startRecording"
    >
      <el-icon><Microphone /></el-icon>
      实时记录
    </el-button>

    <section v-else class="live-console" aria-live="polite">
      <header class="live-console__header">
        <div class="live-identity">
          <span class="live-dot" :class="{ active: status === 'recording' }"></span>
          <div>
            <strong>{{ statusTitle }}</strong>
            <span>{{ statusDescription }}</span>
          </div>
        </div>
        <time class="live-clock">{{ elapsedLabel }}</time>
      </header>

      <div class="live-transcript">
        <div v-if="!segments.length && !partialText" class="live-empty">
          <el-icon><ChatLineRound /></el-icon>
          <p>开始说话后，识别内容会实时出现在这里。</p>
        </div>

        <div v-else class="live-lines">
          <article v-for="segment in visibleSegments" :key="segment.index" class="live-line">
            <span class="speaker-mark">{{ speakerName(segment.speaker) }}</span>
            <p>{{ segment.text }}</p>
            <time>{{ formatTimestamp(segment.start_ms) }}</time>
          </article>
          <article v-if="partialText" class="live-line live-line--partial">
            <span class="speaker-mark">识别中</span>
            <p>{{ partialText }}</p>
            <span class="typing-mark" aria-hidden="true"></span>
          </article>
        </div>
      </div>

      <footer class="live-console__footer">
        <p v-if="status === 'recording'">麦克风音频以 16 kHz 单声道 PCM 安全转发至听悟。</p>
        <p v-else-if="status === 'done'">逐字稿已保存，可进入会议详情继续整理。</p>
        <p v-else>{{ errorMessage || '正在建立安全连接，请稍候。' }}</p>

        <div class="live-actions">
          <el-button
            v-if="status === 'starting'"
            text
            @click="cancelRecording"
          >取消</el-button>
          <el-button
            v-if="status === 'recording'"
            type="danger"
            @click="stopRecording"
          >
            <el-icon><VideoPause /></el-icon>
            结束记录
          </el-button>
          <el-button
            v-if="status === 'done' && meetingId"
            type="primary"
            @click="router.push(`/meetings/${meetingId}`)"
          >查看会议</el-button>
          <el-button v-if="status === 'done' || status === 'error'" @click="resetRecorder">
            {{ status === 'error' ? '重新开始' : '收起' }}
          </el-button>
        </div>
      </footer>
    </section>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../services/api.js'

defineProps({
  disabled: { type: Boolean, default: false },
})

const emit = defineEmits(['active-change', 'completed'])
const router = useRouter()

const status = ref('idle')
const errorMessage = ref('')
const segments = ref([])
const partialText = ref('')
const meetingId = ref('')
const elapsedSec = ref(0)

let socket = null
let mediaStream = null
let audioContext = null
let sourceNode = null
let processorNode = null
let silentGainNode = null
let timerId = null
let workletUrl = ''

const visibleSegments = computed(() => segments.value.slice(-6))
const elapsedLabel = computed(() => {
  const hours = Math.floor(elapsedSec.value / 3600)
  const minutes = Math.floor((elapsedSec.value % 3600) / 60)
  const seconds = elapsedSec.value % 60
  return [hours, minutes, seconds].map((value) => String(value).padStart(2, '0')).join(':')
})
const statusTitle = computed(() => ({
  starting: '正在连接听悟',
  recording: '实时记录中',
  stopping: '正在结束记录',
  done: '记录已完成',
  error: '实时记录中断',
}[status.value] || '实时记录'))
const statusDescription = computed(() => ({
  starting: '授权麦克风并创建实时转写任务',
  recording: '正在接收并保存实时识别结果',
  stopping: '正在等待最后一句识别结果',
  done: `${segments.value.length} 段内容已保存`,
  error: '请检查网络或服务配置后重试',
}[status.value] || ''))

function realtimeSocketUrl(ticket) {
  const apiBase = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')
  let url
  if (/^https?:\/\//i.test(apiBase)) {
    url = new URL(`${apiBase}/realtime/ws`)
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  } else {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    url = new URL(`${protocol}//${window.location.host}${apiBase}/realtime/ws`)
  }
  url.searchParams.set('ticket', ticket)
  return url.toString()
}

function defaultMeetingName() {
  const now = new Date()
  const datePart = now.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
  const timePart = now.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false })
  return `实时会议 ${datePart} ${timePart}`
}

async function startRecording() {
  if (!navigator.mediaDevices?.getUserMedia) {
    ElMessage.error('当前浏览器不支持麦克风采集，请使用最新版 Chrome、Edge 或 Safari。')
    return
  }

  status.value = 'starting'
  errorMessage.value = ''
  segments.value = []
  partialText.value = ''
  meetingId.value = ''
  elapsedSec.value = 0
  emit('active-change', true)

  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
      video: false,
    })
    const response = await api.post('/realtime/ticket')
    await connectSocket(response.data.ticket)
  } catch (error) {
    const denied = error?.name === 'NotAllowedError'
    failRecording(denied ? '未获得麦克风权限，请在浏览器地址栏允许访问。' : apiError(error))
  }
}

function connectSocket(ticket) {
  return new Promise((resolve, reject) => {
    let settled = false
    socket = new WebSocket(realtimeSocketUrl(ticket))
    socket.binaryType = 'arraybuffer'

    const timeoutId = window.setTimeout(() => {
      if (!settled) {
        settled = true
        reject(new Error('连接实时转写服务超时'))
        socket?.close()
      }
    }, 20000)

    socket.onopen = () => {
      socket.send(JSON.stringify({
        type: 'start',
        name: defaultMeetingName(),
        source_language: 'cn',
        speaker_count: 0,
      }))
    }

    socket.onmessage = async (event) => {
      let message
      try {
        message = JSON.parse(event.data)
      } catch {
        return
      }

      if (message.type === 'ready') {
        meetingId.value = message.meeting_id
        try {
          await beginAudioPipeline()
        } catch (error) {
          if (!settled) {
            settled = true
            window.clearTimeout(timeoutId)
            reject(error)
          }
          return
        }
        status.value = 'recording'
        startTimer()
        if (!settled) {
          settled = true
          window.clearTimeout(timeoutId)
          resolve()
        }
        return
      }

      if (message.type === 'partial') {
        partialText.value = message.text || ''
        return
      }

      if (message.type === 'final' && message.text) {
        partialText.value = ''
        upsertSegment(message)
        return
      }

      if (message.type === 'error') {
        if (!settled) {
          settled = true
          window.clearTimeout(timeoutId)
          reject(new Error(message.message || message.status_text || '实时转写服务异常'))
        } else {
          failRecording(message.message || message.status_text || '实时转写服务异常')
        }
        return
      }

      if (message.type === 'session_completed') {
        meetingId.value = message.meeting_id || meetingId.value
        finishRecording()
      }
    }

    socket.onerror = () => {
      if (!settled) {
        settled = true
        window.clearTimeout(timeoutId)
        reject(new Error('无法连接实时转写服务'))
      }
    }

    socket.onclose = () => {
      if (status.value === 'starting' && !settled) {
        settled = true
        window.clearTimeout(timeoutId)
        reject(new Error('实时转写连接已关闭'))
      } else if (status.value === 'recording') {
        failRecording('实时转写连接意外中断，已保存收到的内容。')
      } else if (status.value === 'stopping') {
        meetingId.value ? finishRecording() : failRecording('实时转写连接在结束时中断。')
      }
    }
  })
}

async function beginAudioPipeline() {
  audioContext = new AudioContext({ latencyHint: 'interactive' })
  await audioContext.resume()
  sourceNode = audioContext.createMediaStreamSource(mediaStream)
  silentGainNode = audioContext.createGain()
  silentGainNode.gain.value = 0
  silentGainNode.connect(audioContext.destination)

  if (audioContext.audioWorklet) {
    const workletCode = `
      class SmartSyncPcmProcessor extends AudioWorkletProcessor {
        process(inputs) {
          const input = inputs[0] && inputs[0][0]
          if (input && input.length) this.port.postMessage(input.slice(0))
          return true
        }
      }
      registerProcessor('smartsync-pcm-processor', SmartSyncPcmProcessor)
    `
    workletUrl = URL.createObjectURL(new Blob([workletCode], { type: 'text/javascript' }))
    await audioContext.audioWorklet.addModule(workletUrl)
    processorNode = new AudioWorkletNode(audioContext, 'smartsync-pcm-processor')
    processorNode.port.onmessage = (event) => sendPcmFrame(event.data, audioContext.sampleRate)
  } else {
    processorNode = audioContext.createScriptProcessor(4096, 1, 1)
    processorNode.onaudioprocess = (event) => {
      sendPcmFrame(event.inputBuffer.getChannelData(0), audioContext.sampleRate)
    }
  }

  sourceNode.connect(processorNode)
  processorNode.connect(silentGainNode)
}

function sendPcmFrame(floatSamples, inputRate) {
  if (status.value !== 'recording' || socket?.readyState !== WebSocket.OPEN) return
  if (socket.bufferedAmount > 512 * 1024) return
  const pcm = downsamplePcm16(floatSamples, inputRate, 16000)
  if (pcm.byteLength) socket.send(pcm.buffer)
}

function downsamplePcm16(input, inputRate, outputRate) {
  const ratio = inputRate / outputRate
  const outputLength = Math.max(0, Math.floor(input.length / ratio))
  const output = new Int16Array(outputLength)
  for (let outputIndex = 0; outputIndex < outputLength; outputIndex += 1) {
    const start = Math.floor(outputIndex * ratio)
    const end = Math.min(input.length, Math.floor((outputIndex + 1) * ratio))
    let total = 0
    let count = 0
    for (let inputIndex = start; inputIndex < end; inputIndex += 1) {
      total += input[inputIndex]
      count += 1
    }
    const sample = Math.max(-1, Math.min(1, count ? total / count : 0))
    output[outputIndex] = sample < 0 ? sample * 0x8000 : sample * 0x7fff
  }
  return output
}

function upsertSegment(segment) {
  const index = segments.value.findIndex((item) => item.index === segment.index)
  if (index >= 0) segments.value[index] = segment
  else segments.value.push(segment)
  segments.value.sort((a, b) => a.index - b.index)
}

async function stopRecording() {
  if (status.value !== 'recording') return
  status.value = 'stopping'
  stopTimer()
  await stopAudioPipeline()
  if (socket?.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ type: 'stop' }))
  } else {
    failRecording('连接已断开，已保存收到的内容。')
  }
}

function cancelRecording() {
  stopTimer()
  stopAudioPipeline()
  socket?.close()
  resetRecorder()
}

function finishRecording() {
  stopTimer()
  stopAudioPipeline()
  status.value = 'done'
  emit('active-change', false)
  emit('completed', meetingId.value)
}

function failRecording(message) {
  stopTimer()
  stopAudioPipeline()
  socket?.close()
  errorMessage.value = message
  status.value = 'error'
  emit('active-change', false)
}

async function stopAudioPipeline() {
  if (processorNode) {
    processorNode.disconnect()
    if ('onaudioprocess' in processorNode) processorNode.onaudioprocess = null
    processorNode.port && (processorNode.port.onmessage = null)
  }
  sourceNode?.disconnect()
  silentGainNode?.disconnect()
  mediaStream?.getTracks().forEach((track) => track.stop())
  if (audioContext && audioContext.state !== 'closed') await audioContext.close()
  if (workletUrl) URL.revokeObjectURL(workletUrl)
  processorNode = null
  sourceNode = null
  silentGainNode = null
  mediaStream = null
  audioContext = null
  workletUrl = ''
}

function resetRecorder() {
  socket?.close()
  socket = null
  status.value = 'idle'
  errorMessage.value = ''
  segments.value = []
  partialText.value = ''
  meetingId.value = ''
  elapsedSec.value = 0
  emit('active-change', false)
}

function startTimer() {
  stopTimer()
  timerId = window.setInterval(() => { elapsedSec.value += 1 }, 1000)
}

function stopTimer() {
  if (timerId) window.clearInterval(timerId)
  timerId = null
}

function speakerName(speaker) {
  const match = String(speaker || '').match(/(\d+)$/)
  return match ? `发言人 ${Number(match[1]) + 1}` : '发言人'
}

function formatTimestamp(milliseconds) {
  const totalSeconds = Math.max(0, Math.floor(Number(milliseconds || 0) / 1000))
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
}

function apiError(error) {
  return error?.response?.data?.detail || error?.message || '无法启动实时转写'
}

onBeforeUnmount(() => {
  stopTimer()
  stopAudioPipeline()
  socket?.close()
})
</script>

<style scoped>
.realtime-recorder.is-active {
  flex: 1 0 100%;
  width: 100%;
}

.live-console {
  margin-top: 8px;
  overflow: hidden;
  border: 1px solid color-mix(in oklab, var(--primary) 24%, var(--border));
  border-radius: 18px;
  background: color-mix(in oklab, var(--bg-elevated) 95%, var(--primary) 5%);
}

.live-console__header,
.live-console__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 18px 20px;
}

.live-console__header {
  border-bottom: 1px solid var(--border-soft);
}

.live-identity {
  display: flex;
  align-items: center;
  gap: 12px;
}

.live-identity strong,
.live-identity span {
  display: block;
}

.live-identity strong {
  color: var(--text);
  font-size: 15px;
}

.live-identity div > span {
  margin-top: 3px;
  color: var(--text-soft);
  font-size: 12px;
}

.live-dot {
  width: 11px;
  height: 11px;
  flex: 0 0 auto;
  border-radius: 50%;
  background: var(--warning);
}

.live-dot.active {
  background: var(--danger);
  box-shadow: 0 0 0 0 color-mix(in oklab, var(--danger) 35%, transparent);
  animation: recordingPulse 1.8s ease-out infinite;
}

.live-clock {
  color: var(--text);
  font-size: 1.25rem;
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.04em;
}

.live-transcript {
  min-height: 190px;
  max-height: 330px;
  overflow-y: auto;
  padding: 8px 20px;
}

.live-empty {
  min-height: 174px;
  display: grid;
  place-items: center;
  align-content: center;
  gap: 10px;
  color: var(--text-soft);
  text-align: center;
}

.live-empty .el-icon {
  font-size: 26px;
}

.live-lines {
  display: grid;
}

.live-line {
  display: grid;
  grid-template-columns: 76px minmax(0, 1fr) 44px;
  align-items: start;
  gap: 12px;
  padding: 14px 0;
  border-bottom: 1px solid var(--border-soft);
}

.live-line:last-child {
  border-bottom: 0;
}

.speaker-mark {
  color: color-mix(in oklab, var(--primary) 78%, var(--text) 22%);
  font-size: 12px;
  font-weight: 700;
}

.live-line p {
  color: var(--text);
  line-height: 1.7;
}

.live-line time {
  color: var(--text-soft);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  text-align: right;
}

.live-line--partial {
  opacity: 0.68;
}

.typing-mark {
  width: 6px;
  height: 18px;
  background: var(--primary);
  animation: typingBlink 1s steps(1) infinite;
}

.live-console__footer {
  border-top: 1px solid var(--border-soft);
  background: color-mix(in oklab, var(--bg-panel) 48%, transparent);
}

.live-console__footer > p {
  color: var(--text-muted);
  font-size: 12px;
  line-height: 1.55;
}

.live-actions {
  display: flex;
  flex: 0 0 auto;
  gap: 8px;
}

@keyframes recordingPulse {
  70% { box-shadow: 0 0 0 9px transparent; }
  100% { box-shadow: 0 0 0 0 transparent; }
}

@keyframes typingBlink {
  50% { opacity: 0; }
}

@media (max-width: 680px) {
  .live-console__header,
  .live-console__footer {
    align-items: flex-start;
    flex-direction: column;
  }

  .live-line {
    grid-template-columns: 72px minmax(0, 1fr);
  }

  .live-line time,
  .typing-mark {
    grid-column: 2;
    text-align: left;
  }
}
</style>
