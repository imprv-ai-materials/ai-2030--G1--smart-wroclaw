"use client";

/**
 * Inline follow-up widgets for the add flow. The orchestrator hands back a spec
 * of the missing fields (typed widgets); we render them so the resident completes
 * the report deterministically instead of another free-text round-trip. On submit
 * we return the raw values (sent back as structured `fields`) plus a readable
 * summary for the chat transcript.
 */

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import type { ChatFormField } from "@/lib/chat-api";

export function AddEventForm({
  fields,
  disabled,
  onSubmit,
}: {
  fields: ChatFormField[];
  disabled?: boolean;
  onSubmit: (values: Record<string, string>, summary: string) => void;
}) {
  const [values, setValues] = useState<Record<string, string>>({});
  const set = (name: string, value: string) =>
    setValues((state) => ({ ...state, [name]: value }));

  const complete = fields
    .filter((field) => field.required)
    .every((field) => (values[field.field] ?? "").trim() !== "");

  function submit() {
    if (!complete || disabled) return;
    const summary = fields
      .map((field) => {
        const raw = values[field.field] ?? "";
        const shown =
          field.widget === "select"
            ? field.options?.find((o) => o.value === raw)?.label ?? raw
            : raw;
        return `${field.label}: ${shown}`;
      })
      .join(" · ");
    onSubmit(values, summary);
  }

  return (
    <form
      className="w-full space-y-3 rounded-xl border bg-card p-3"
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      {fields.map((field) => {
        const id = `field-${field.field}`;
        const value = values[field.field] ?? "";
        return (
          <div key={field.field} className="space-y-1.5">
            <Label htmlFor={id}>{field.label}</Label>
            {field.widget === "select" ? (
              <Select
                id={id}
                value={value}
                disabled={disabled}
                onChange={(e) => set(field.field, e.target.value)}
              >
                <option value="" disabled>
                  Wybierz…
                </option>
                {(field.options ?? []).map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </Select>
            ) : field.widget === "textarea" ? (
              <Textarea
                id={id}
                rows={3}
                value={value}
                disabled={disabled}
                placeholder={field.placeholder}
                onChange={(e) => set(field.field, e.target.value)}
              />
            ) : field.widget === "datetime" ? (
              <Input
                id={id}
                type="datetime-local"
                value={value}
                disabled={disabled}
                onChange={(e) => set(field.field, e.target.value)}
              />
            ) : (
              <Input
                id={id}
                type="text"
                value={value}
                disabled={disabled}
                placeholder={field.placeholder}
                onChange={(e) => set(field.field, e.target.value)}
              />
            )}
          </div>
        );
      })}
      <Button
        type="submit"
        size="sm"
        className="w-full"
        disabled={!complete || disabled}
      >
        Dalej
      </Button>
    </form>
  );
}
