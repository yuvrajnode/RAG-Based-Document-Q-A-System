import { useCallback, useRef, useState } from "react";
import { askStream } from "../lib/api";
import type { AskDone, Message, SourceChunk } from "../lib/types";

function id(): string {
  return Math.random().toString(36).slice(2, 10);
}

export function useConversation() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [busy, setBusy] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const patchLast = useCallback((patch: (message: Message) => Message) => {
    setMessages((current) => {
      if (!current.length) return current;
      const next = current.slice();
      next[next.length - 1] = patch(next[next.length - 1]);
      return next;
    });
  }, []);

  const ask = useCallback(
    async (question: string, documentIds: string[]) => {
      if (!question.trim() || busy) return;

      // Only completed turns are sent back as history; the placeholder we are
      // about to append would otherwise arrive as an empty assistant turn.
      const history = messages
        .filter((message) => !message.streaming && !message.error)
        .slice(-4)
        .map((message) => ({ role: message.role, content: message.content }));

      const controller = new AbortController();
      abortRef.current = controller;
      setBusy(true);
      setMessages((current) => [
        ...current,
        { id: id(), role: "user", content: question },
        { id: id(), role: "assistant", content: "", streaming: true },
      ]);

      try {
        await askStream(
          { question, documentIds, history, signal: controller.signal },
          {
            onSources: (sources: SourceChunk[]) =>
              patchLast((message) => ({ ...message, sources })),
            onDelta: (text: string) =>
              patchLast((message) => ({ ...message, content: message.content + text })),
            onDone: (payload) => {
              const done = payload as AskDone;
              patchLast((message) => ({
                ...message,
                streaming: false,
                citations: done.citations ?? [],
                meta: done,
              }));
            },
            onError: (detail: string) =>
              patchLast((message) => ({ ...message, streaming: false, error: detail })),
          },
        );
      } catch (cause) {
        const aborted = cause instanceof DOMException && cause.name === "AbortError";
        patchLast((message) => ({
          ...message,
          streaming: false,
          error: aborted ? undefined : cause instanceof Error ? cause.message : "request failed",
          content: aborted && !message.content ? "_Stopped._" : message.content,
        }));
      } finally {
        patchLast((message) => ({ ...message, streaming: false }));
        abortRef.current = null;
        setBusy(false);
      }
    },
    [busy, messages, patchLast],
  );

  const stop = useCallback(() => abortRef.current?.abort(), []);
  const reset = useCallback(() => {
    abortRef.current?.abort();
    setMessages([]);
  }, []);

  return { messages, busy, ask, stop, reset };
}
