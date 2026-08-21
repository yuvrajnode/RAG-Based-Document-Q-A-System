import { useEffect, useRef } from "react";
import { formatDuration } from "../lib/format";
import type { Message } from "../lib/types";
import { AnswerText } from "./AnswerText";
import { SparkIcon } from "./Icons";

interface Props {
  messages: Message[];
  emptyState: React.ReactNode;
  activeCitation: number | null;
  onCitationHover: (marker: number | null) => void;
}

function Thinking() {
  return (
    <div className="flex items-center gap-1.5 py-1">
      <span className="thinking-dot" />
      <span className="thinking-dot [animation-delay:150ms]" />
      <span className="thinking-dot [animation-delay:300ms]" />
      <span className="ml-1 text-xs text-ink-500">searching the index</span>
    </div>
  );
}

export function Conversation({ messages, emptyState, activeCitation, onCitationHover }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const pinnedRef = useRef(true);

  // Follow the stream, but stop following the moment the reader scrolls up -
  // yanking someone back to the bottom while they are reading a source is the
  // fastest way to make a chat UI feel hostile.
  useEffect(() => {
    const element = containerRef.current;
    if (!element) return;
    const onScroll = () => {
      const distance = element.scrollHeight - element.scrollTop - element.clientHeight;
      pinnedRef.current = distance < 120;
    };
    element.addEventListener("scroll", onScroll, { passive: true });
    return () => element.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    if (pinnedRef.current) bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (!messages.length) {
    return <div className="flex-1 overflow-y-auto">{emptyState}</div>;
  }

  return (
    <div ref={containerRef} className="flex-1 overflow-y-auto px-4 py-6">
      <div className="mx-auto flex max-w-3xl flex-col gap-6">
        {messages.map((message) =>
          message.role === "user" ? (
            <div key={message.id} className="flex justify-end">
              <div
                className="max-w-[85%] animate-fade-up whitespace-pre-wrap rounded-2xl rounded-br-md
                  bg-accent-600 px-4 py-2.5 text-[15px] text-white shadow-sm"
              >
                {message.content}
              </div>
            </div>
          ) : (
            <div key={message.id} className="flex animate-fade-up gap-3">
              <div
                className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg
                  bg-accent-500/15 text-accent-600 dark:text-accent-300"
              >
                <SparkIcon className="h-4 w-4" />
              </div>

              <div className="min-w-0 flex-1">
                {message.streaming && !message.content ? (
                  <Thinking />
                ) : (
                  <AnswerText
                    text={message.content}
                    activeCitation={activeCitation}
                    onCitationClick={(marker) =>
                      onCitationHover(activeCitation === marker ? null : marker)
                    }
                  />
                )}

                {message.error && (
                  <p className="mt-2 rounded-lg bg-rose-500/10 px-3 py-2 text-xs text-rose-600 dark:text-rose-300">
                    {message.error}
                  </p>
                )}

                {message.meta && !message.streaming && (
                  <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-ink-400">
                    <span>{formatDuration(message.meta.latency_ms)}</span>
                    {message.meta.retrieval_ms !== undefined && (
                      <span>retrieval {formatDuration(message.meta.retrieval_ms)}</span>
                    )}
                    <span>{message.sources?.length ?? 0} passages retrieved</span>
                    <span
                      className={
                        message.meta.grounded
                          ? "text-emerald-600 dark:text-emerald-400"
                          : "text-amber-600 dark:text-amber-400"
                      }
                    >
                      {message.meta.grounded
                        ? `${message.citations?.length ?? 0} cited`
                        : "no citations"}
                    </span>
                  </div>
                )}
              </div>
            </div>
          ),
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
