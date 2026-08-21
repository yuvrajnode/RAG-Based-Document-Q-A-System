import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { SendIcon, StopIcon } from "./Icons";

interface Props {
  busy: boolean;
  disabled: boolean;
  scopeLabel: string | null;
  onSubmit: (question: string) => void;
  onStop: () => void;
}

const MAX_HEIGHT = 180;

export function Composer({ busy, disabled, scopeLabel, onSubmit, onStop }: Props) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Grow with the content up to a ceiling, then scroll inside the box.
  useEffect(() => {
    const element = textareaRef.current;
    if (!element) return;
    element.style.height = "auto";
    element.style.height = `${Math.min(element.scrollHeight, MAX_HEIGHT)}px`;
  }, [value]);

  const submit = () => {
    const question = value.trim();
    if (!question || busy || disabled) return;
    onSubmit(question);
    setValue("");
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  };

  return (
    <div className="px-4 pb-4 pt-2">
      <div
        className="panel flex items-end gap-2 p-2 focus-within:border-accent-500/60
          focus-within:ring-1 focus-within:ring-accent-500/30"
      >
        <textarea
          ref={textareaRef}
          rows={1}
          value={value}
          disabled={disabled}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={onKeyDown}
          placeholder={
            disabled
              ? "Index a document first"
              : scopeLabel
                ? `Ask about ${scopeLabel}...`
                : "Ask a question about your documents..."
          }
          className="max-h-[180px] flex-1 resize-none bg-transparent px-2 py-1.5 text-[15px]
            outline-none placeholder:text-ink-400 disabled:cursor-not-allowed"
        />
        {busy ? (
          <button onClick={onStop} className="btn-ghost h-9 px-3" title="Stop generating">
            <StopIcon className="h-4 w-4" />
          </button>
        ) : (
          <button
            onClick={submit}
            disabled={!value.trim() || disabled}
            className="btn-primary h-9 w-9 !px-0"
            title="Send (Enter)"
          >
            <SendIcon className="h-4 w-4" />
          </button>
        )}
      </div>
      <p className="mt-1.5 px-1 text-[11px] text-ink-400">
        Enter to send, Shift+Enter for a new line. Answers are limited to what the indexed passages
        say.
      </p>
    </div>
  );
}
