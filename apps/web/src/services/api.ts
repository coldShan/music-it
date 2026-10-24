import type {
  CatalogEntryDetail,
  CatalogEntrySummary,
  InstrumentId,
  RecognizeApiResponse,
} from '@music-it/shared-types'

const BASE_URL = import.meta.env.VITE_OMR_API_URL ?? 'http://localhost:8000'

async function parseJsonOrThrow(response: Response) {
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: 'Request failed' }))
    const detail = typeof body?.detail === 'string' ? body.detail : 'Request failed'
    throw new Error(detail)
  }
  return response.json()
}

export async function recognizeScore(files: File[], force = false, onUploadProgress?: (percent: number | null) => void): Promise<RecognizeApiResponse> {
  const formData = new FormData()
  for (const file of files) {
    formData.append('file', file)
  }

  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest()
    request.open('POST', `${BASE_URL}/api/v1/recognize${force ? '?force=true' : ''}`)
    request.upload.onprogress = (event) => {
      onUploadProgress?.(event.lengthComputable && event.total > 0
        ? Math.min(99, Math.floor(event.loaded / event.total * 100)) : null)
    }
    request.upload.onload = () => onUploadProgress?.(100)
    request.onerror = () => reject(new Error('网络连接失败，请重试。'))
    request.onabort = () => reject(new Error('导入已取消。'))
    request.onload = () => {
      try {
        const body = JSON.parse(request.responseText)
        if (request.status < 200 || request.status >= 300) {
          reject(new Error(typeof body?.detail === 'string' ? body.detail : 'Request failed'))
          return
        }
        resolve(body as RecognizeApiResponse)
      } catch {
        reject(new Error('服务器返回了无效响应，请重试。'))
      }
    }
    request.send(formData)
  })
}

export async function listCatalogEntries(): Promise<CatalogEntrySummary[]> {
  const response = await fetch(`${BASE_URL}/api/v1/catalog`)
  return (await parseJsonOrThrow(response)) as CatalogEntrySummary[]
}

export async function getCatalogEntry(entryId: string): Promise<CatalogEntryDetail> {
  const response = await fetch(`${BASE_URL}/api/v1/catalog/${entryId}`)
  return (await parseJsonOrThrow(response)) as CatalogEntryDetail
}

type UpdateCatalogEntryPayload = {
  title?: string
  melodyInstrument?: InstrumentId
  leftHandInstrument?: InstrumentId
}

export async function updateCatalogEntry(
  entryId: string,
  payload: UpdateCatalogEntryPayload,
): Promise<CatalogEntrySummary> {
  const response = await fetch(`${BASE_URL}/api/v1/catalog/${entryId}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })
  return (await parseJsonOrThrow(response)) as CatalogEntrySummary
}

export async function deleteCatalogEntry(entryId: string): Promise<void> {
  const response = await fetch(`${BASE_URL}/api/v1/catalog/${entryId}`, {
    method: 'DELETE',
  })
  await parseJsonOrThrow(response)
}

export async function resetCatalog(confirm = 'WIPE_CATALOG'): Promise<{ reset: boolean; removedEntries: number }> {
  const response = await fetch(
    `${BASE_URL}/api/v1/catalog/reset?confirm=${encodeURIComponent(confirm)}`,
    {
      method: 'POST',
    },
  )
  return (await parseJsonOrThrow(response)) as { reset: boolean; removedEntries: number }
}
