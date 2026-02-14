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
    <span class="upload-title">上传五线谱</span>
    <input type="file" accept=".png,.jpg,.jpeg,.pdf" @change="onChange" />
    <span class="upload-hint">支持 PNG / JPG / PDF(第一页)</span>
  </label>
</template>

<style scoped>
.upload-field {
  display: grid;
  gap: 10px;

  .upload-title {
    font: 600 18px/1.2 'Cormorant Garamond', serif;
    letter-spacing: 0.06em;
  }

  input {
    border: 1px solid #7f7463;
    border-radius: 10px;
    padding: 10px;
    background: #f2efe8;

    &::file-selector-button {
      border: 0;
      border-radius: 8px;
      padding: 8px 12px;
      margin-right: 12px;
      background: #1d2a3f;
      color: #f5f2ea;
      cursor: pointer;
    }
  }

  .upload-hint {
    color: #524940;
    font-size: 13px;
  }
}
</style>
