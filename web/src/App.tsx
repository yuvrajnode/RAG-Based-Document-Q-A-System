import { useCallback, useMemo, useState } from "react";
import { Composer } from "./components/Composer";
import { Conversation } from "./components/Conversation";
import { DocumentLibrary } from "./components/DocumentLibrary";
import { EmptyState } from "./components/EmptyState";
import { Header } from "./components/Header";
import { SourcePanel } from "./components/SourcePanel";
import { useConversation } from "./hooks/useConversation";
import { useDocuments } from "./hooks/useDocuments";
import { useTheme } from "./hooks/useTheme";

type Pane = "library" | "chat" | "sources";

const PANES: { id: Pane; label: string }[] = [
  { id: "library", label: "Library" },
  { id: "chat", label: "Chat" },
  { id: "sources", label: "Sources" },
];

const STARTER_QUESTIONS = [
  "Summarise the main points in three sentences.",
  "What deadlines or dates are mentioned?",
  "What does this say about costs or limits?",
  "Which parts are unclear or left unspecified?",
];

export default function App() {
  const { theme, toggle } = useTheme();
  const { documents, stats, uploading, error, upload, remove } = useDocuments();
  const { messages, busy, ask, stop, reset } = useConversation();

  const [selected, setSelected] = useState<string[]>([]);
  const [activeCitation, setActiveCitation] = useState<number | null>(null);
  // Below the lg breakpoint there is no room for three columns, so the panes
  // become tabs rather than disappearing.
  const [pane, setPane] = useState<Pane>("chat");

  const toggleSelected = useCallback((id: string) => {
    setSelected((current) =>
      current.includes(id) ? current.filter((value) => value !== id) : [...current, id],
    );
  }, []);

  const submit = useCallback(
    (question: string) => {
      setActiveCitation(null);
      setPane("chat");
      void ask(question, selected);
    },
    [ask, selected],
  );

  // The panel always reflects the most recent assistant turn.
  const latest = useMemo(
    () => [...messages].reverse().find((message) => message.role === "assistant"),
    [messages],
  );

  const scopeLabel = useMemo(() => {
    if (!selected.length) return null;
    if (selected.length === 1) {
      return documents.find((document) => document.id === selected[0])?.title ?? "1 document";
    }
    return `${selected.length} documents`;
  }, [documents, selected]);

  return (
    <div className="flex h-full flex-col overflow-hidden bg-ink-50 dark:bg-ink-950">
      <Header
        stats={stats}
        theme={theme}
        onToggleTheme={toggle}
        onReset={reset}
        canReset={messages.length > 0}
      />

      {error && (
        <div className="bg-rose-500/10 px-4 py-2 text-center text-xs text-rose-600 dark:text-rose-300">
          {error} - is the API running on :8000?
        </div>
      )}

      <nav className="flex gap-1 border-b border-ink-200/70 px-3 py-1.5 dark:border-ink-800 lg:hidden">
        {PANES.map((entry) => (
          <button
            key={entry.id}
            onClick={() => setPane(entry.id)}
            className={`flex-1 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
              pane === entry.id
                ? "bg-accent-500/15 text-accent-700 dark:text-accent-300"
                : "text-ink-500 hover:bg-ink-200/60 dark:hover:bg-ink-800"
            }`}
          >
            {entry.label}
          </button>
        ))}
      </nav>

      <div className="grid min-h-0 flex-1 overflow-hidden lg:grid-cols-[290px_minmax(0,1fr)_330px]">
        <aside
          className={`${pane === "library" ? "block" : "hidden"} min-h-0 border-r
            border-ink-200/70 p-3 dark:border-ink-800 lg:block`}
        >
          <DocumentLibrary
            documents={documents}
            selected={selected}
            uploading={uploading}
            onSelect={toggleSelected}
            onClearSelection={() => setSelected([])}
            onUpload={upload}
            onRemove={remove}
          />
        </aside>

        <main className={`${pane === "chat" ? "flex" : "hidden"} min-h-0 flex-col lg:flex`}>
          {scopeLabel && (
            <div
              className="flex items-center justify-center gap-2 border-b border-ink-200/70 bg-accent-500/5
                px-4 py-1.5 text-[11px] text-ink-500 dark:border-ink-800"
            >
              Answering from <span className="font-medium text-accent-600 dark:text-accent-300">{scopeLabel}</span>
              <button onClick={() => setSelected([])} className="underline underline-offset-2">
                use everything
              </button>
            </div>
          )}

          <Conversation
            messages={messages}
            activeCitation={activeCitation}
            onCitationHover={setActiveCitation}
            emptyState={
              <EmptyState
                hasDocuments={documents.length > 0}
                suggestions={STARTER_QUESTIONS}
                onPick={submit}
              />
            }
          />

          <Composer
            busy={busy}
            disabled={documents.length === 0}
            scopeLabel={scopeLabel}
            onSubmit={submit}
            onStop={stop}
          />
        </main>

        <aside
          className={`${pane === "sources" ? "block" : "hidden"} min-h-0 border-l
            border-ink-200/70 dark:border-ink-800 lg:block`}
        >
          <SourcePanel
            sources={latest?.sources ?? []}
            citations={(latest?.citations ?? []).map((citation) => citation.marker)}
            meta={latest?.meta}
            active={activeCitation}
            onActivate={setActiveCitation}
          />
        </aside>
      </div>
    </div>
  );
}
