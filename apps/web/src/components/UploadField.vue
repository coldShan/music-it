<script setup lang="ts">
import { ref } from 'vue'

const filesModel = defineModel<File[]>('files', { default: () => [] })
const props = withDefaults(defineProps<{ disabled?: boolean }>(), { disabled: false })
const errorMessage = ref('')
const dragging = ref(false)
const input = ref<HTMLInputElement>()
const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' })
const extensions = new Set(['png', 'jpg', 'jpeg', 'pdf'])
const mimeTypes = new Set(['image/png', 'image/jpeg', 'application/pdf'])

function setFiles(files: File[]) {
  const invalid = files.filter((file) => {
    const extensionAllowed = extensions.has(file.name.split('.').pop()?.toLowerCase() ?? '')
    return !extensionAllowed || (!!file.type && !mimeTypes.has(file.type))
  })
  if (invalid.length) {
    errorMessage.value = `不支持 ${invalid.map((file) => file.name).join('、')}，请选择 PNG、JPG 或 PDF。`
    return
  }
  errorMessage.value = ''
  filesModel.value = [...files].sort((a, b) => collator.compare(a.name, b.name))
}

function onChange(event: Event) {
  const target = event.target as HTMLInputElement
  setFiles(Array.from(target.files ?? []))
  target.value = ''
}

function onDrop(event: DragEvent) {
  dragging.value = false
  if (!props.disabled) setFiles(Array.from(event.dataTransfer?.files ?? []))
}

function removeFile(index: number) {
  if (!props.disabled) filesModel.value = filesModel.value.filter((_, current) => current !== index)
}
</script>

<template>
  <div class="upload-field">
    <span class="upload-title">选择乐谱文件</span>
    <div
      :class="['drop-zone', { dragging, disabled }]"
      @dragenter.prevent="!disabled && (dragging = true)"
      @dragover.prevent
      @dragleave.prevent="dragging = false"
      @drop.prevent="onDrop"
    >
      <input ref="input" data-testid="recognize-file-input" aria-label="选择乐谱文件" tabindex="-1" type="file" accept=".png,.jpg,.jpeg,.pdf" multiple :disabled="disabled" @change="onChange" />
      <div class="drop-copy">
        <span class="upload-mark" aria-hidden="true">谱</span>
        <strong>拖放文件到这里</strong><span>或</span>
        <button type="button" class="choose-button" :disabled="disabled" @click="input?.click()">浏览文件</button>
      </div>
    </div>
    <p class="upload-hint">支持 PNG、JPG 和 PDF；多页图片会按文件名顺序合并，PDF 仅识别首页。</p>
    <p v-if="errorMessage" class="local-error" role="alert">{{ errorMessage }}</p>
    <ol v-if="filesModel.length" class="upload-files" aria-label="已选择文件">
      <li v-for="(file, index) in filesModel" :key="`${file.name}-${file.size}-${file.lastModified}`">
        <span class="file-order">{{ String(index + 1).padStart(2, '0') }}</span>
        <span class="file-name">{{ file.name }}</span>
        <button type="button" class="remove" :disabled="disabled" :aria-label="`移除 ${file.name}`" @click="removeFile(index)">移除</button>
      </li>
    </ol>
  </div>
</template>

<style scoped>
.upload-field { display: grid; gap: 10px; color: #252923; }
.upload-title { font-size: 14px; font-weight: 650; }
.drop-zone { position: relative; min-height: 156px; display: grid; place-items: center; border: 1px dashed #b9bcae; border-radius: 10px; background: #fffefa; transition: border-color .16s ease, background .16s ease; }
.drop-zone.dragging { border-color: #556348; background: #f1f3ec; }
.drop-zone.disabled { opacity: .6; cursor: not-allowed; }
.drop-zone input { position: absolute; width: 1px; height: 1px; opacity: 0; pointer-events: none; }
.drop-copy { display: flex; align-items: center; justify-content: center; flex-wrap: wrap; gap: 7px; padding: 24px; color: #76796f; font-size: 13px; }
.drop-copy strong { color: #252923; font-size: 14px; }
.upload-mark { width: 38px; height: 38px; margin-right: 3px; display: grid; place-items: center; border: 1px solid #dedfd5; border-radius: 50%; color: #556348; font-family: 'Noto Serif SC', serif; font-size: 17px; }
.choose-button, .remove { border: 0; background: transparent; color: #556348; font: inherit; font-weight: 650; cursor: pointer; }
.choose-button { padding: 4px 2px; text-decoration: underline; text-underline-offset: 3px; }
button:disabled { cursor: not-allowed; }
.upload-hint, .local-error { margin: 0; font-size: 12px; line-height: 1.55; }
.upload-hint { color: #76796f; }
.local-error { color: #9a3e32; }
.upload-files { margin: 2px 0 0; padding: 0; list-style: none; border: 1px solid #dedfd5; border-radius: 9px; background: #fffefa; }
.upload-files li { min-height: 42px; display: grid; grid-template-columns: 30px minmax(0, 1fr) auto; align-items: center; gap: 8px; padding: 7px 10px; border-bottom: 1px solid #e9e9e2; font-size: 13px; }
.upload-files li:last-child { border-bottom: 0; }
.file-order { color: #9a9d93; font-variant-numeric: tabular-nums; }
.file-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.remove { padding: 5px; font-size: 12px; }
</style>
