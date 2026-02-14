import type { RecognizeResponse } from '@music-it/shared-types'

const BASE_URL = import.meta.env.VITE_OMR_API_URL ?? 'http://localhost:8000'

export async function recognizeScore(file: File): Promise<RecognizeResponse> {
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch(`${BASE_URL}/api/v1/recognize`, {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: 'Request failed' }))
    const detail = typeof body?.detail === 'string' ? body.detail : 'Request failed'
    throw new Error(detail)
  }

  return (await response.json()) as RecognizeResponse
}
