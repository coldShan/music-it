<script setup lang="ts">
const filesModel = defineModel<File[]>('files', {
  default: () => [],
})

const filenameCollator = new Intl.Collator(undefined, {
  numeric: true,
  sensitivity: 'base',
})

function onChange(event: Event) {
  const input = event.target as HTMLInputElement
  filesModel.value = Array.from(input.files ?? []).sort((left, right) =>
    filenameCollator.compare(left.name, right.name),
  )
}
</script>

<template>
  <label class="upload-field">
    <span class="upload-title">上传乐谱</span>
    <input
      data-testid="recognize-file-input"
      type="file"
      accept=".png,.jpg,.jpeg,.pdf"
      multiple
      @change="onChange"
    />
    <span class="upload-hint">支持多选 PNG / JPG / PDF（PDF 仅第一页），按文件名顺序识别</span>
    <ol v-if="filesModel.length" class="upload-files">
      <li v-for="file in filesModel" :key="`${file.name}-${file.size}-${file.lastModified}`">
        {{ file.name }}
      </li>
    </ol>
  </label>
</template>

<style scoped>
.upload-field {
  display: grid;
  gap: 8px;

  .upload-title {
    margin: 0;
    font: 600 16px/1.2 'Noto Sans SC', sans-serif;
    color: #1b1852;
  }

  input {
    border: 1px solid #8b87c8;
    border-radius: 12px;
    padding: 10px;
    background: #fff;
    color: #221f4d;

    &::file-selector-button {
      border: 1px solid #25216b;
      border-radius: 10px;
      padding: 8px 12px;
      margin-right: 12px;
      background: linear-gradient(130deg, #2d2984, #e03f9f);
      color: #f8f6ff;
      cursor: pointer;
    }
  }

  .upload-hint {
    color: #605b9a;
    font-size: 13px;
  }

  .upload-files {
    margin: 0;
    padding-left: 22px;
    color: #25216b;
    font-size: 13px;
    font-weight: 600;
    word-break: break-all;
  }
}
</style>
