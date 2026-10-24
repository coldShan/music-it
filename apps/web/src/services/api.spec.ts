import { afterEach, describe, expect, it, vi } from 'vitest'
import { recognizeScore } from './api'

class MockRequest {
  static latest: MockRequest
  upload = { onprogress: null as ((event: ProgressEvent) => void) | null, onload: null as (() => void) | null }
  onload: (() => void) | null = null
  onerror: (() => void) | null = null
  onabort: (() => void) | null = null
  status = 200
  responseText = '{}'
  open = vi.fn()
  send = vi.fn()
  constructor() { MockRequest.latest = this }
}

afterEach(() => vi.unstubAllGlobals())

describe('recognizeScore', () => {
  it('reports actual upload progress and waits for the recognition response', async () => {
    vi.stubGlobal('XMLHttpRequest', MockRequest)
    const report = vi.fn()
    const files = [new File(['a'], 'page-1.png'), new File(['b'], 'page-2.png')]
    const result = recognizeScore(files, true, report)
    const request = MockRequest.latest
    expect(request.open).toHaveBeenCalledWith('POST', expect.stringContaining('/api/v1/recognize?force=true'))
    expect((request.send.mock.calls[0][0] as FormData).getAll('file')).toEqual(files)
    request.upload.onprogress!(new ProgressEvent('progress', { lengthComputable: true, loaded: 42, total: 100 }))
    expect(report).toHaveBeenLastCalledWith(42)
    request.upload.onprogress!(new ProgressEvent('progress'))
    expect(report).toHaveBeenLastCalledWith(null)
    request.upload.onload!()
    expect(report).toHaveBeenLastCalledWith(100)
    request.responseText = '{"catalogEntryId":"new"}'
    request.onload!()
    await expect(result).resolves.toEqual({ catalogEntryId: 'new' })
  })

  it.each(['server', 'network', 'invalid'])('rejects %s errors', async (kind) => {
    vi.stubGlobal('XMLHttpRequest', MockRequest)
    const result = recognizeScore([])
    const request = MockRequest.latest
    if (kind === 'network') request.onerror!()
    else {
      request.status = kind === 'server' ? 422 : 200
      request.responseText = kind === 'server' ? '{"detail":"谱面无法识别"}' : '<html>Error</html>'
      request.onload!()
    }
    await expect(result).rejects.toThrow(kind === 'server' ? '谱面无法识别' : kind === 'network' ? '网络连接失败' : '无效响应')
  })
})
