"use client";

import { useState } from "react";
import { Card, PageHeader } from "@/components/ui";
import { copilotAnswer } from "@/lib/mock-data";

export default function CopilotPage() {
  const [question, setQuestion] = useState("");
  const [submitted, setSubmitted] = useState(false);

  return (
    <div>
      <PageHeader
        title="Operations Copilot"
        subtitle="Ask in plain language. Answers are grounded in your indexed documents with citations."
      />

      <Card>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setSubmitted(true);
          }}
          className="flex gap-3"
        >
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="e.g. What is the recommended seal flush plan for Pump P-101?"
            className="flex-1 rounded-lg border border-[var(--color-border)] bg-[var(--color-base)] px-4 py-2.5 text-sm outline-none placeholder:text-[var(--color-muted)] focus:border-[var(--color-accent)]"
          />
          <button
            type="submit"
            className="rounded-lg bg-[var(--color-accent)] px-5 py-2.5 text-sm font-medium text-[var(--color-base)] hover:opacity-90"
          >
            Ask
          </button>
        </form>

        <div className="mt-3 flex flex-wrap gap-2">
          {[
            "Which assets have overdue calibration?",
            "Summarize the C-220 trip root cause",
            "LOTO steps before pump maintenance",
          ].map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setQuestion(s)}
              className="rounded-full border border-[var(--color-border)] bg-[var(--color-base)] px-3 py-1 text-xs text-[var(--color-muted)] hover:border-[var(--color-accent)] hover:text-white"
            >
              {s}
            </button>
          ))}
        </div>
      </Card>

      {(submitted || true) && (
        <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <p className="mb-2 text-xs uppercase tracking-wide text-[var(--color-muted)]">
              Question
            </p>
            <p className="mb-5 text-sm font-medium">
              {submitted && question ? question : copilotAnswer.question}
            </p>

            <p className="mb-2 text-xs uppercase tracking-wide text-[var(--color-muted)]">
              Answer
            </p>
            <p className="text-sm leading-relaxed">
              {copilotAnswer.answer}{" "}
              {copilotAnswer.citations.map((c) => (
                <sup key={c.id} className="ml-0.5 text-[var(--color-accent)]">
                  [{c.id}]
                </sup>
              ))}
            </p>
          </Card>

          <Card>
            <p className="mb-3 text-xs uppercase tracking-wide text-[var(--color-muted)]">
              Citations
            </p>
            <ul className="space-y-3">
              {copilotAnswer.citations.map((c) => (
                <li
                  key={c.id}
                  className="rounded-lg border border-[var(--color-border)] bg-[var(--color-base)] p-3"
                >
                  <div className="flex items-center gap-2">
                    <span className="flex h-5 w-5 items-center justify-center rounded bg-[var(--color-surface-2)] text-xs text-[var(--color-accent)]">
                      {c.id}
                    </span>
                    <span className="text-sm font-medium">{c.doc}</span>
                  </div>
                  <p className="mt-1 text-xs text-[var(--color-accent-2)]">{c.section}</p>
                  <p className="mt-1 text-xs text-[var(--color-muted)]">“{c.snippet}”</p>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      )}
    </div>
  );
}
