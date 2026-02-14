import type { InstrumentId } from '@music-it/shared-types'

export const instrumentOptions: Array<{ value: InstrumentId; label: string }> = [
  { value: 'piano', label: '钢琴' },
  { value: 'guitar', label: '吉他' },
  { value: 'musicBox', label: '八音盒' },
  { value: 'violin', label: '小提琴' },
  { value: 'trumpet', label: '小号' },
  { value: 'saxophone', label: '萨克斯' },
  { value: 'flute', label: '笛子' },
]

export const instrumentLabelMap: Record<InstrumentId, string> = Object.fromEntries(
  instrumentOptions.map((item) => [item.value, item.label]),
) as Record<InstrumentId, string>
