import { useState, type FormEvent, type ReactNode } from 'react'

import type { Constraints } from '@/api/constraints'
import { useCreateMaterial, type MaterialLotCreate } from '@/api/reference'
import { cn } from '@/lib/utils'

import { rangeText, serverErrors } from './recipeValidation'

const NUMERIC_FIELDS = [
  { name: 'mfi', label: 'MFI (g/10 min)' },
  { name: 'moisture_pct', label: 'Moisture (%)' },
  { name: 'regrind_pct', label: 'Regrind (%)' },
  { name: 'colourant_pct', label: 'Colourant (%)' },
] as const

type NumericField = (typeof NUMERIC_FIELDS)[number]['name']

/** Label, control, optional hint and error; the error is linked, never part of the label. */
function Field({
  id,
  label,
  error,
  hint,
  children,
}: {
  id: string
  label: string
  error?: string
  hint?: string
  children: ReactNode
}) {
  return (
    <div className="flex flex-col gap-1 text-xs text-text-muted">
      <label htmlFor={id}>{label}</label>
      {children}
      {hint && <span id={`${id}-hint`}>{hint}</span>}
      {error && (
        <span id={`${id}-error`} className="text-risk-critical">
          {error}
        </span>
      )}
    </div>
  )
}

/**
 * "Create lot" (roadmap R2-P6 task 3, F1). The API validates the lot against the registry; this form
 * shows a window only where the registry defines one (rule B6) and maps the server's answer back
 * onto the fields.
 */
export function CreateLotDialog({
  constraints,
  onCreated,
  onClose,
}: {
  constraints: Constraints
  onCreated: (lotId: string) => void
  onClose: () => void
}) {
  const grades = Object.keys(constraints.resin_grades)
  const [code, setCode] = useState('')
  const [grade, setGrade] = useState(grades[0] ?? '')
  const [values, setValues] = useState<Record<NumericField, string>>({
    mfi: '',
    moisture_pct: '',
    regrind_pct: '',
    colourant_pct: '',
  })
  const [notes, setNotes] = useState('')
  const create = useCreateMaterial()
  const errors = serverErrors(create.isError ? create.error : null)
  const missing = !code.trim() || !grade || NUMERIC_FIELDS.some((f) => values[f.name].trim() === '')

  const submit = (e: FormEvent) => {
    e.preventDefault()
    const body = {
      material_lot_id: code.trim(),
      resin_grade: grade,
      mfi: Number(values.mfi),
      moisture_pct: Number(values.moisture_pct),
      regrind_pct: Number(values.regrind_pct),
      colourant_pct: Number(values.colourant_pct),
      notes: notes.trim() || null,
    } as MaterialLotCreate
    create.mutate(body, { onSuccess: (lot) => onCreated(lot.material_lot_id) })
  }

  const describedBy = (name: string, hint = false) =>
    [hint ? `lot-${name}-hint` : null, errors.fields[name] ? `lot-${name}-error` : null]
      .filter(Boolean)
      .join(' ') || undefined
  const inputClass = (name: string) =>
    cn(
      'rounded border bg-panel px-2 py-1 text-sm text-text',
      errors.fields[name] ? 'border-risk-critical' : 'border-border',
    )

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/60 p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="create-lot-title"
        className="w-full max-w-md rounded border border-border bg-panel p-4 shadow-xl"
        onKeyDown={(e) => {
          if (e.key === 'Escape') onClose()
        }}
      >
        <h3 id="create-lot-title" className="text-sm font-semibold text-text">
          Create material lot
        </h3>
        <p className="mt-1 text-xs text-text-muted">
          The server checks the lot against the constraint registry before it is saved.
        </p>
        <form onSubmit={submit} className="mt-3 flex flex-col gap-2" aria-label="Create lot">
          <Field id="lot-material_lot_id" label="Lot code" error={errors.fields.material_lot_id}>
            <input
              id="lot-material_lot_id"
              autoFocus
              value={code}
              onChange={(e) => setCode(e.target.value)}
              aria-invalid={Boolean(errors.fields.material_lot_id)}
              aria-describedby={describedBy('material_lot_id')}
              className={inputClass('material_lot_id')}
            />
          </Field>
          <Field id="lot-resin_grade" label="Resin grade" error={errors.fields.resin_grade}>
            <select
              id="lot-resin_grade"
              value={grade}
              onChange={(e) => setGrade(e.target.value)}
              aria-invalid={Boolean(errors.fields.resin_grade)}
              aria-describedby={describedBy('resin_grade')}
              className={inputClass('resin_grade')}
            >
              {grades.map((g) => (
                <option key={g} value={g}>
                  {g}
                </option>
              ))}
            </select>
          </Field>
          <div className="grid grid-cols-2 gap-2">
            {NUMERIC_FIELDS.map((f) => {
              const spec = constraints.parameters.find((p) => p.name === f.name)
              return (
                <Field
                  key={f.name}
                  id={`lot-${f.name}`}
                  label={f.label}
                  error={errors.fields[f.name]}
                  hint={spec ? rangeText(spec) : undefined}
                >
                  <input
                    id={`lot-${f.name}`}
                    type="number"
                    step="any"
                    min={spec?.min ?? undefined}
                    max={spec?.max ?? undefined}
                    value={values[f.name]}
                    onChange={(e) => setValues((v) => ({ ...v, [f.name]: e.target.value }))}
                    aria-invalid={Boolean(errors.fields[f.name])}
                    aria-describedby={describedBy(f.name, Boolean(spec))}
                    className={inputClass(f.name)}
                  />
                </Field>
              )
            })}
          </div>
          <Field id="lot-notes" label="Notes (optional)">
            <input
              id="lot-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className={inputClass('notes')}
            />
          </Field>
          {errors.general.length > 0 && (
            <ul role="alert" className="text-xs text-risk-critical">
              {errors.general.map((m) => (
                <li key={m}>{m}</li>
              ))}
            </ul>
          )}
          <div className="mt-2 flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded border border-border px-3 py-1 text-xs text-text hover:bg-panel-raised"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={missing || create.isPending}
              className="rounded border border-state-active px-3 py-1 text-xs font-semibold text-state-active uppercase disabled:opacity-40"
            >
              {create.isPending ? 'Saving…' : 'Create lot'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
