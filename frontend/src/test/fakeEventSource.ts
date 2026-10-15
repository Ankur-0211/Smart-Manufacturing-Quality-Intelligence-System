/** TEST-ONLY EventSource double: records URL, lets tests open/fail the stream and emit events. */
import type { SimulationEvent } from '@/features/process-control/model'
import type { EventSourceLike } from '@/features/process-control/useRunEvents'

export class FakeEventSource implements EventSourceLike {
  static instances: FakeEventSource[] = []
  onopen: EventSourceLike['onopen'] = null
  onerror: EventSourceLike['onerror'] = null
  closed = false
  private listeners = new Map<string, ((ev: MessageEvent<string>) => void)[]>()

  constructor(readonly url: string) {
    FakeEventSource.instances.push(this)
  }

  addEventListener(type: string, listener: (ev: MessageEvent<string>) => void): void {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener])
  }

  close(): void {
    this.closed = true
  }

  open(): void {
    this.onopen?.call(this, new Event('open'))
  }

  fail(): void {
    this.onerror?.call(this, new Event('error'))
  }

  emit(event: SimulationEvent): void {
    for (const l of this.listeners.get(event.type) ?? []) {
      l(new MessageEvent(event.type, { data: JSON.stringify(event) }))
    }
  }

  emitRaw(type: string, data: string): void {
    for (const l of this.listeners.get(type) ?? []) l(new MessageEvent(type, { data }))
  }
}
