<script setup lang="ts">
import { Menu, MenuButton, MenuItem, MenuItems } from '@headlessui/vue'
import type { CatalogEntrySummary } from '@music-it/shared-types'

const props = defineProps<{
  entries: CatalogEntrySummary[]
  loading: boolean
  activeId: string | null
  editingId: string | null
  editingTitle: string
}>()

const emit = defineEmits<{
  select: [entryId: string]
  play: [entryId: string]
  delete: [entryId: string]
  startRename: [entryId: string, currentTitle: string]
  updateEditingTitle: [value: string]
  commitRename: [entryId: string, title: string]
  cancelRename: []
}>()

const vFocus = { mounted: (el: HTMLInputElement) => { el.focus(); el.select() } }
const onInput = (value: string) => emit('updateEditingTitle', value)
const saveRename = (entryId: string) => emit('commitRename', entryId, props.editingTitle)
</script>

<template>
  <section class="catalog" aria-label="已收藏乐谱">


    <div v-if="loading" class="state" role="status">
      <span class="loading-mark" aria-hidden="true"></span>
      <div><strong>正在整理曲库</strong><p>稍候，乐谱很快就绪。</p></div>
    </div>
    <div v-else-if="!entries.length" class="state">
      <span class="empty-mark" aria-hidden="true">𝄞</span>
      <div><strong>曲库还是空的</strong><p>完成一次乐谱识别后，曲目会收藏在这里。</p></div>
    </div>

    <div v-else class="table-shell">
      <div class="table-head" aria-hidden="true"><span>序</span><span>曲目</span><span>节拍</span><span>操作</span></div>
      <ul class="items">
        <li v-for="(entry, index) in entries" :key="entry.id" :class="{ active: entry.id === activeId, editing: editingId === entry.id }">
          <span class="index">{{ String(index + 1).padStart(2, '0') }}</span>
          <div class="identity">
            <template v-if="editingId === entry.id">
              <label class="sr-only" :for="`catalog-title-${entry.id}`">曲目名称</label>
              <input
                :id="`catalog-title-${entry.id}`"
                v-focus
                :data-testid="`catalog-rename-input-${entry.id}`"
                class="rename-input"
                :value="editingTitle"
                @input="onInput(($event.target as HTMLInputElement).value)"
                @keydown.enter.prevent="saveRename(entry.id)"
                @keydown.esc.prevent="emit('cancelRename')"
              />
            </template>
            <button v-else type="button" :data-testid="`catalog-select-${entry.id}`" class="title" @click="emit('select', entry.id)">{{ entry.title }}</button>
            <p class="mobile-meta">{{ entry.timeSignature }} · {{ entry.tempo }} BPM</p>
          </div>
          <p class="meter"><span>{{ entry.timeSignature }}</span><small>{{ entry.tempo }} BPM</small></p>

          <div v-if="editingId === entry.id" class="rename-actions">
            <button type="button" class="save" @click="saveRename(entry.id)">保存</button>
            <button type="button" class="cancel" @click="emit('cancelRename')">取消</button>
          </div>
          <div v-else class="actions">

            <button type="button" class="play" :data-testid="`catalog-play-${entry.id}`" :aria-label="`试听 ${entry.title}`" @click="emit('play', entry.id)"><span aria-hidden="true">▶</span>试听</button>
            <Menu as="div" class="menu-wrap">
              <MenuButton :data-testid="`catalog-menu-${entry.id}`" class="menu-button" :aria-label="`${entry.title} 更多操作`"><span aria-hidden="true">•••</span></MenuButton>
              <MenuItems class="menu-items">
                <MenuItem v-slot="{ active: menuActive }"><button type="button" :data-testid="`catalog-rename-${entry.id}`" :class="{ active: menuActive }" @click="emit('startRename', entry.id, entry.title)">重命名</button></MenuItem>
                <MenuItem v-slot="{ active: menuActive }"><button type="button" :data-testid="`catalog-delete-${entry.id}`" :class="['danger', { active: menuActive }]" @click="emit('delete', entry.id)">删除曲目</button></MenuItem>
              </MenuItems>
            </Menu>
          </div>
        </li>
      </ul>
    </div>
  </section>
</template>

<style scoped>
.catalog { --paper:#f7f6f2; --ink:#252923; --olive:#556348; --line:rgba(37,41,35,.15); color:var(--ink); font-family:'Noto Sans SC','PingFang SC',sans-serif }
.catalog-header { display:flex; align-items:end; justify-content:space-between; gap:24px; padding:4px 2px 22px; border-bottom:1px solid var(--ink) }
.eyebrow { margin:0 0 7px; color:var(--olive); font:700 10px/1.2 Georgia,serif; letter-spacing:.24em }
h2 { margin:0; font:500 clamp(25px,3vw,36px)/1.05 'Songti SC','Noto Serif SC',serif; letter-spacing:-.04em }
.count { margin:0; color:#707469; font-size:12px }
.table-head,li { display:grid; grid-template-columns:56px minmax(0,1fr) 140px 160px; align-items:center }
.table-head { min-height:45px; padding:0 14px; border-bottom:1px solid var(--line); color:#777b71; font-size:10px; letter-spacing:.14em }
.items { margin:0; padding:0; list-style:none }
li { min-height:74px; padding:0 14px; border-bottom:1px solid var(--line); transition:background 160ms ease }
li:hover,li:focus-within { background:rgba(85,99,72,.055) }
li.active { box-shadow:inset 3px 0 var(--olive); background:rgba(85,99,72,.08) }
.index { color:#91958b; font:italic 14px/1 Georgia,serif }
.identity { min-width:0 }
.title { max-width:100%; overflow:hidden; padding:8px 0; border:0; background:none; color:var(--ink); font:500 17px/1.35 'Songti SC','Noto Serif SC',serif; text-align:left; text-overflow:ellipsis; white-space:nowrap; cursor:pointer }
.title:hover { color:var(--olive); text-decoration:underline; text-decoration-thickness:1px; text-underline-offset:5px }
.mobile-meta { display:none }
.meter { display:flex; align-items:baseline; gap:9px; margin:0; color:var(--ink); font:500 15px/1 Georgia,serif }
.meter small { color:#777b71; font:400 11px/1.2 'Noto Sans SC',sans-serif }
.actions,.rename-actions { display:flex; justify-content:flex-end; align-items:center; gap:7px }
button { font-family:inherit; font-size:12px }
.open,.play,.save,.cancel,.menu-button { min-height:36px; border-radius:3px; cursor:pointer }
.open,.cancel { border:0; background:transparent; color:#555b50; padding:7px 9px }
.open span { margin-left:3px }
.play,.save { border:1px solid var(--olive); background:var(--olive); color:var(--paper); padding:7px 13px; font-weight:600 }
.play span { margin-right:5px; font-size:9px }
.menu-wrap { position:relative }
.menu-button { width:38px; border:1px solid transparent; background:transparent; color:#666b61; letter-spacing:2px }
.menu-button:hover,.menu-button[aria-expanded='true'] { border-color:var(--line); background:#fff }
.menu-items { position:absolute; right:0; z-index:10; display:grid; width:136px; margin-top:6px; padding:5px; border:1px solid var(--line); border-radius:4px; background:#fffefa; box-shadow:0 14px 32px rgba(37,41,35,.14) }
.menu-items button { width:100%; padding:9px 10px; border:0; border-radius:2px; background:transparent; color:var(--ink); text-align:left; cursor:pointer }
.menu-items button.active { background:rgba(85,99,72,.1) }
.menu-items button.danger { color:#8a4037 }
.rename-input { width:min(100%,420px); box-sizing:border-box; padding:8px 10px; border:1px solid var(--olive); border-radius:3px; outline:3px solid rgba(85,99,72,.12); background:#fffefa; color:var(--ink); font:500 16px/1.3 'Songti SC','Noto Serif SC',serif }
.state { display:flex; align-items:center; justify-content:center; gap:18px; min-height:220px; border-bottom:1px solid var(--line); color:var(--ink) }
.state strong { font:500 18px/1.3 'Songti SC','Noto Serif SC',serif }
.state p { margin:5px 0 0; color:#777b71; font-size:12px }
.empty-mark { color:var(--olive); font:42px/1 Georgia,serif }
.loading-mark { width:28px; height:28px; border:1px solid rgba(85,99,72,.25); border-top-color:var(--olive); border-radius:50%; animation:turn 900ms linear infinite }
.sr-only { position:absolute; width:1px; height:1px; padding:0; overflow:hidden; clip:rect(0,0,0,0); white-space:nowrap; border:0 }
@keyframes turn { to { transform:rotate(360deg) } }
@media (max-width:720px) {
  .catalog-header { padding-bottom:17px }
  .table-head { display:none }
  li { grid-template-columns:34px minmax(0,1fr) auto; min-height:88px; padding:0 4px }
  .meter { display:none }
  .mobile-meta { display:block; margin:-2px 0 0; color:#777b71; font-size:11px }
  .actions { gap:1px }
  .open { display:none }
  .play { padding-inline:10px }
  li.editing { grid-template-columns:34px minmax(0,1fr); gap:8px 0; padding-block:12px }
  .editing .rename-actions { grid-column:2; justify-content:flex-start }
}
@media (prefers-reduced-motion:reduce) { li { transition:none } .loading-mark { animation-duration:1.8s } }
</style>
