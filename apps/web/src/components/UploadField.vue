<script setup lang="ts">
const fileModel = defineModel<File | null>('file', {
  default: null,
})

function onChange(event: Event) {
  const input = event.target as HTMLInputElement
  fileModel.value = input.files?.[0] ?? null
}
</script>

<template>
  <label class="upload-field">
    <span class="upload-title">上传乐谱</span>
    <input
      data-testid="recognize-file-input"
      type="file"
      accept=".png,.jpg,.jpeg,.pdf"
      @change="onChange"
    />
    <span class="upload-hint">支持 PNG / JPG / PDF（第一页）</span>
    <span v-if="fileModel" class="upload-file">已选择：{{ fileModel.name }}</span>
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

  .upload-file {
    color: #25216b;
    font-size: 13px;
    font-weight: 600;
    word-break: break-all;
  }
}
</style>
