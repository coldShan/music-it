import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import UploadField from './UploadField.vue'

const drop = (files: File[]) => ({ dataTransfer: { files } })

describe('UploadField', () => {
  it('accepts a real drop and emits files in natural filename order', async () => {
    const wrapper = mount(UploadField)
    const page10 = new File(['10'], 'score-10.png', { type: 'image/png' })
    const page2 = new File(['2'], 'score-2.png', { type: 'image/png' })

    await wrapper.get('.drop-zone').trigger('drop', drop([page10, page2]))

    expect(wrapper.emitted('update:files')?.[0]).toEqual([[page2, page10]])
    expect(wrapper.findAll('.file-name').map((item) => item.text())).toEqual(['score-2.png', 'score-10.png'])
  })

  it('rejects an invalid type without replacing the current selection', async () => {
    const original = new File(['score'], 'kept.pdf', { type: 'application/pdf' })
    const wrapper = mount(UploadField, { props: { files: [original] } })
    const invalid = new File(['script'], 'fake.png', { type: 'text/javascript' })

    await wrapper.get('.drop-zone').trigger('drop', drop([invalid]))

    expect(wrapper.emitted('update:files')).toBeUndefined()
    expect(wrapper.get('[role="alert"]').text()).toContain('fake.png')
    expect(wrapper.get('.file-name').text()).toBe('kept.pdf')
  })

  it('removes a selected file and disables every file-changing control', async () => {
    const first = new File(['1'], 'one.png', { type: 'image/png' })
    const second = new File(['2'], 'two.pdf', { type: 'application/pdf' })
    const wrapper = mount(UploadField, { props: { files: [first, second] } })

    await wrapper.get('button[aria-label="移除 one.png"]').trigger('click')
    expect(wrapper.emitted('update:files')?.[0]).toEqual([[second]])

    await wrapper.setProps({ disabled: true })
    expect((wrapper.get('[data-testid="recognize-file-input"]').element as HTMLInputElement).disabled).toBe(true)
    expect(wrapper.findAll('button').every((item) => (item.element as HTMLButtonElement).disabled)).toBe(true)
    const updates = wrapper.emitted('update:files')?.length
    await wrapper.get('.drop-zone').trigger('drop', drop([first]))
    expect(wrapper.emitted('update:files')?.length).toBe(updates)
  })
})
