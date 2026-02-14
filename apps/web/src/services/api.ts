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

export async function recognizeScore(file: File): Promise<RecognizeApiResponse> {
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch(`${BASE_URL}/api/v1/recognize`, {
    method: 'POST',
    body: formData,
  })

  return (await parseJsonOrThrow(response)) as RecognizeApiResponse
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
