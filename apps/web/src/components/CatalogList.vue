<script setup lang="ts">
import { Menu, MenuButton, MenuItem, MenuItems } from '@headlessui/vue'
import type { CatalogEntrySummary, InstrumentId } from '@music-it/shared-types'

const props = defineProps<{
  entries: CatalogEntrySummary[]
  loading: boolean
  activeId: string | null
  instrumentLabelMap: Record<InstrumentId, string>
  editingId: string | null
  editingTitle: string
}>()

const emit = defineEmits<{
  play: [entryId: string]
  delete: [entryId: string]
  startRename: [entryId: string, currentTitle: string]
  updateEditingTitle: [value: string]
  commitRename: [entryId: string, title: string]
  cancelRename: []
}>()

function onPlay(entryId: string) {
  emit('play', entryId)
}

function onDelete(entryId: string) {
  emit('delete', entryId)
}

function onStartRename(entryId: string, currentTitle: string) {
  emit('startRename', entryId, currentTitle)
}

function onInput(value: string) {
  emit('updateEditingTitle', value)
}

function onRenameConfirm(entryId: string) {
  emit('commitRename', entryId, props.editingTitle)
}

function onRenameCancel() {
  emit('cancelRename')
}
</script>

<template>
  <section class="catalog">
    <header class="catalog-header">
      <h2>曲目目录</h2>
      <p>从历史识别结果快速回放。</p>
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
          <input
            v-if="editingId === entry.id"
            :data-testid="`catalog-rename-input-${entry.id}`"
            class="rename-input"
            :value="editingTitle"
            @input="onInput(($event.target as HTMLInputElement).value)"
            @keydown.enter.prevent="onRenameConfirm(entry.id)"
            @keydown.esc.prevent="onRenameCancel"
            @blur="onRenameCancel"
          />
          <p v-else class="title">{{ entry.title }}</p>

          <p class="meta">{{ entry.timeSignature }} · {{ entry.tempo }} BPM · {{ entry.noteCount }} 音符</p>
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

          <Menu as="div" class="menu-wrap">
            <MenuButton :data-testid="`catalog-menu-${entry.id}`" class="menu-button">操作</MenuButton>
            <MenuItems class="menu-items">
              <MenuItem v-slot="{ active }">
                <button
                  type="button"
                  :data-testid="`catalog-rename-${entry.id}`"
                  :class="{ active }"
                  @click="onStartRename(entry.id, entry.title)"
                >
                  重命名
                </button>
              </MenuItem>
              <MenuItem v-slot="{ active }">
                <button
                  type="button"
                  :data-testid="`catalog-delete-${entry.id}`"
                  :class="['danger', { active }]"
                  @click="onDelete(entry.id)"
                >
                  删除
                </button>
              </MenuItem>
            </MenuItems>
          </Menu>
        </div>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.catalog {
  display: grid;
  gap: 10px;

  .catalog-header {
    h2 {
      margin: 0;
      font: 700 24px/1.2 'Noto Serif SC', serif;
      color: #26215d;
    }

    p {
      margin: 5px 0 0;
      color: #5f5796;
      font-size: 13px;
    }
  }

  .empty {
    margin: 0;
    color: #6a629e;
    font-size: 14px;
  }

  .items {
    margin: 0;
    padding: 0;
    list-style: none;
    display: grid;
    gap: 10px;
  }
}

li {
  border: 1px solid #8c86cf;
  border-radius: 14px;
  background: #fff;
  display: grid;
  gap: 10px;
  padding: 12px;
  transition: transform 0.2s ease, box-shadow 0.2s ease;

  &:hover {
    transform: translateY(-1px);
    box-shadow: 0 12px 24px rgba(53, 40, 134, 0.14);
  }

  &.active {
    border-color: #2c2685;
    box-shadow: 0 0 0 2px rgba(70, 56, 192, 0.2);
  }
}

.info {
  min-width: 0;
  display: grid;
  gap: 6px;

  .title {
    margin: 0;
    color: #211c59;
    font-weight: 700;
    word-break: break-word;
  }

  .rename-input {
    border: 1px solid #7f77c9;
    border-radius: 10px;
    padding: 8px 10px;
    font-weight: 600;
    color: #1e1a56;
    background: #f8f6ff;
    outline: none;
  }

  .meta {
    margin: 0;
    color: #5c5492;
    font-size: 13px;
    word-break: break-all;
  }
}

.actions {
  display: flex;
  gap: 8px;

  .play {
    flex: 1;
    border: 0;
    border-radius: 10px;
    padding: 8px 10px;
    background: linear-gradient(130deg, #29237f, #e0439f);
    color: #fff;
    cursor: pointer;
    font-weight: 600;
  }

  .menu-wrap {
    position: relative;
  }

  .menu-button {
    border: 1px solid #7f77c9;
    border-radius: 10px;
    background: #f7f4ff;
    color: #2a246a;
    padding: 8px 12px;
    cursor: pointer;
    font-weight: 600;
  }

  .menu-items {
    position: absolute;
    right: 0;
    margin-top: 6px;
    z-index: 10;
    border-radius: 12px;
    border: 1px solid #8f89d1;
    background: #fff;
    box-shadow: 0 14px 24px rgba(44, 31, 118, 0.2);
    padding: 6px;
    min-width: 120px;
    display: grid;
    gap: 4px;

    button {
      border: 0;
      border-radius: 8px;
      padding: 8px;
      width: 100%;
      text-align: left;
      cursor: pointer;
      background: transparent;
      color: #2e286f;

      &.active {
        background: #efebff;
      }

      &.danger {
        color: #9a1f5f;
      }
    }
  }
}
</style>
