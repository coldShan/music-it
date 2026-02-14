<script setup lang="ts">
import { computed, ref } from 'vue'
import type { RecognizeResponse } from '@music-it/shared-types'

import ResultTable from './components/ResultTable.vue'
import UploadField from './components/UploadField.vue'
import { recognizeScore } from './services/api'
import { playScore, stopScore } from './services/player'

const selectedFile = ref<File | null>(null)
const loading = ref(false)
const errorMessage = ref('')
const result = ref<RecognizeResponse | null>(null)
const autoPlayMessage = ref('')

const canPlay = computed(() => !!result.value?.notes.length)

async function onRecognize() {
  if (!selectedFile.value) {
    errorMessage.value = '请先选择谱面文件。'
    return
  }

  loading.value = true
  errorMessage.value = ''
  autoPlayMessage.value = ''

  try {
    const response = await recognizeScore(selectedFile.value)
    result.value = response

    if (response.notes.length) {
      try {
        await playScore({ tempo: response.tempo, notes: response.notes })
      } catch {
        autoPlayMessage.value = '浏览器阻止了自动播放，请点击“播放”按钮。'
      }
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '识别失败'
    result.value = null
  } finally {
    loading.value = false
  }
}

async function onPlay() {
  if (!result.value) {
    return
  }
  await playScore({ tempo: result.value.tempo, notes: result.value.notes })
}

function onStop() {
  stopScore()
}
</script>

<template>
  <main class="screen">
    <section class="panel">
      <header>
        <p class="kicker">Music It MVP</p>
        <h1>五线谱识别自动弹奏</h1>
        <p class="description">上传清晰谱面图片或 PDF，识别后立即以钢琴音色播放。</p>
      </header>

      <form class="controls" @submit.prevent="onRecognize">
        <UploadField v-model:file="selectedFile" />
        <button type="submit" :disabled="loading">
          {{ loading ? '识别中...' : '识别并自动弹奏' }}
        </button>
      </form>

      <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
      <p v-if="autoPlayMessage" class="hint">{{ autoPlayMessage }}</p>

      <section v-if="result" class="result">
        <div class="meta">
          <p>Tempo: {{ result.tempo }} BPM</p>
          <p>拍号: {{ result.timeSignature }}</p>
          <p>音符数: {{ result.notes.length }}</p>
        </div>

        <div class="actions">
          <button type="button" @click="onPlay" :disabled="!canPlay">播放</button>
          <button type="button" class="secondary" @click="onStop">停止</button>
        </div>

        <ul v-if="result.meta.warnings.length" class="warnings">
          <li v-for="warning in result.meta.warnings" :key="warning">{{ warning }}</li>
        </ul>

        <ResultTable :notes="result.notes" />
      </section>
    </section>
  </main>
</template>

<style scoped>
:global(body) {
  margin: 0;
  font-family: 'IBM Plex Sans', sans-serif;
  color: #111;
}

.screen {
  min-height: 100vh;
  padding: 28px;
  background:
    radial-gradient(circle at 20% 20%, rgba(255, 226, 173, 0.28), transparent 45%),
    linear-gradient(145deg, #f6f1e6, #ddd3c2 60%, #d2c3ac);
  display: grid;
  place-items: center;

  .panel {
    width: min(900px, 100%);
    border-radius: 18px;
    padding: 26px;
    background: rgba(255, 252, 244, 0.9);
    border: 1px solid #9f9079;
    box-shadow: 0 12px 40px rgba(53, 33, 8, 0.16);
    animation: rise 420ms ease-out;

    header {
      margin-bottom: 20px;

      .kicker {
        margin: 0;
        font: 600 14px/1.2 'IBM Plex Sans', sans-serif;
        letter-spacing: 0.14em;
        color: #69583f;
      }

      h1 {
        margin: 8px 0;
        font: 600 44px/1.05 'Cormorant Garamond', serif;
      }

      .description {
        margin: 0;
        color: #4d453d;
      }
    }

    .controls {
      display: grid;
      gap: 14px;
      margin-bottom: 16px;
    }

    button {
      border: 0;
      border-radius: 12px;
      padding: 12px 16px;
      background: #142139;
      color: #f7f4ec;
      cursor: pointer;
      font-weight: 600;
      transition: transform 0.2s ease, opacity 0.2s ease;

      &:hover:not(:disabled) {
        transform: translateY(-1px);
      }

      &:disabled {
        opacity: 0.5;
        cursor: not-allowed;
      }

      &.secondary {
        background: #8a7f72;
      }
    }

    .error {
      color: #7f1f1f;
    }

    .hint {
      color: #5d503f;
    }

    .result {
      display: grid;
      gap: 14px;

      .meta {
        display: flex;
        flex-wrap: wrap;
        gap: 14px;
        color: #3b352d;
      }

      .actions {
        display: flex;
        gap: 12px;
      }

      .warnings {
        margin: 0;
        padding-left: 18px;
        color: #4e402f;
      }
    }
  }
}

@keyframes rise {
  from {
    opacity: 0;
    transform: translateY(14px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (max-width: 768px) {
  .screen {
    padding: 16px;

    .panel {
      padding: 18px;

      header h1 {
        font-size: 34px;
      }
    }
  }
}
</style>
