import { SearchIcon } from "./Icons";

interface Props {
  hasDocuments: boolean;
  suggestions: string[];
  onPick: (question: string) => void;
}

export function EmptyState({ hasDocuments, suggestions, onPick }: Props) {
  return (
    <div className="mx-auto flex h-full max-w-2xl flex-col items-center justify-center px-6 py-10 text-center">
      <div
        className="mb-5 flex h-12 w-12 items-center justify-center rounded-xl bg-accent-500/15
          text-accent-600 dark:text-accent-300"
      >
        <SearchIcon className="h-6 w-6" />
      </div>

      <h2 className="text-lg font-semibold">
        {hasDocuments ? "Ask something" : "Add a document to begin"}
      </h2>
      <p className="mt-2 max-w-md text-sm leading-relaxed text-ink-500">
        {hasDocuments
          ? "Every answer is built from passages retrieved out of your own files, and each claim carries the passage it came from."
          : "Drop a PDF, Word file, Markdown or CSV into the panel on the left. It is chunked, embedded and indexed locally."}
      </p>

      {hasDocuments && suggestions.length > 0 && (
        <div className="mt-7 w-full">
          <p className="mb-2 text-xs font-medium uppercase tracking-wider text-ink-400">Try</p>
          <div className="grid gap-2 sm:grid-cols-2">
            {suggestions.map((question) => (
              <button
                key={question}
                onClick={() => onPick(question)}
                className="panel px-3.5 py-2.5 text-left text-sm text-ink-600 transition-colors
                  hover:border-accent-400 hover:text-ink-900 dark:text-ink-300 dark:hover:text-ink-50"
              >
                {question}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
