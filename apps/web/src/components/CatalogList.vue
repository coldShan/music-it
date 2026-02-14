<script setup lang="ts">
import type { CatalogEntrySummary, InstrumentId } from '@music-it/shared-types'

defineProps<{
  entries: CatalogEntrySummary[]
  loading: boolean
  activeId: string | null
  instrumentLabelMap: Record<InstrumentId, string>
}>()

const emit = defineEmits<{
  play: [entryId: string]
  delete: [entryId: string]
}>()

function onPlay(entryId: string) {
  emit('play', entryId)
}

function onDelete(entryId: string) {
  emit('delete', entryId)
}
</script>

<template>
  <section class="catalog">
    <header class="catalog-header">
      <h2>已识别曲目目录</h2>
      <p>保存于项目目录，可直接播放无需重复识别。</p>
    </header>

    <p v-if="loading" class="empty">目录加载中...</p>
    <p v-else-if="!entries.length" class="empty">暂无已识别曲目。</p>

    <ul v-else class="items">
      <li
        v-for="entry in entries"
        :key="entry.id"
        :class="{ active: entry.id === activeId }"
      >
        <div class="info">
          <p class="title">{{ entry.title }}</p>
          <p class="meta">
            {{ entry.imagePath }} · {{ entry.timeSignature }} · {{ entry.tempo }} BPM · {{ entry.noteCount }} 音符
          </p>
          <p class="meta">
            旋律: {{ instrumentLabelMap[entry.melodyInstrument] }} · 左手: {{ instrumentLabelMap[entry.leftHandInstrument] }}
          </p>
        </div>

        <div class="actions">
          <button
            type="button"
            class="play"
            :data-testid="`catalog-play-${entry.id}`"
            @click="onPlay(entry.id)"
          >
            播放
          </button>
          <button
            type="button"
            class="danger"
            :data-testid="`catalog-delete-${entry.id}`"
            @click="onDelete(entry.id)"
          >
            删除
          </button>
        </div>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.catalog {
  display: grid;
  gap: 12px;

  .catalog-header {
    h2 {
      margin: 0;
      font: 600 28px/1.1 'Cormorant Garamond', serif;
    }

    p {
      margin: 6px 0 0;
      color: #4d453d;
      font-size: 14px;
    }
  }

  .empty {
    margin: 0;
    color: #61594f;
    font-size: 14px;
  }

  .items {
    margin: 0;
    padding: 0;
    list-style: none;
    display: grid;
    gap: 10px;

    li {
      border: 1px solid #d8cfbf;
      border-radius: 12px;
      padding: 12px;
      background: #fffdf7;
      display: flex;
      justify-content: space-between;
      gap: 14px;

      &.active {
        border-color: #2e4368;
        box-shadow: inset 0 0 0 1px rgba(20, 33, 57, 0.16);
      }

      .info {
        min-width: 0;

        .title {
          margin: 0;
          font-weight: 600;
          color: #1f1b15;
        }

        .meta {
          margin: 6px 0 0;
          color: #5f574b;
          font-size: 13px;
          word-break: break-all;
        }
      }

      .actions {
        display: flex;
        align-items: center;
        gap: 8px;

        button {
          border: 0;
          border-radius: 9px;
          padding: 8px 12px;
          cursor: pointer;
          color: #f7f4ec;
          background: #142139;

          &.danger {
            background: #7f2b2b;
          }
        }
      }
    }
  }
}

@media (max-width: 768px) {
  .catalog {
    .items li {
      flex-direction: column;
      align-items: flex-start;

      .actions {
        width: 100%;
      }
    }
  }
}
</style>
