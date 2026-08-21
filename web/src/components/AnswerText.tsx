import { Fragment, type ReactNode } from "react";

/**
 * A deliberately small markdown renderer.
 *
 * The model is prompted for prose with occasional bullets and bold, so the
 * grammar we need is: paragraphs, list items, `code`, **bold**, *italic*, and
 * [n] citation markers. Pulling in a full markdown parser plus a sanitiser to
 * cover the rest would be several times the size of this file, and every extra
 * construct is another thing to style.
 */

interface Props {
  text: string;
  onCitationClick?: (marker: number) => void;
  activeCitation?: number | null;
}

const INLINE = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\[\d{1,2}\])/g;

function CitationChip({
  marker,
  active,
  onClick,
}: {
  marker: number;
  active: boolean;
  onClick?: (marker: number) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onClick?.(marker)}
      title={`Jump to source ${marker}`}
      className={`mx-0.5 inline-flex h-[18px] min-w-[18px] translate-y-[-1px] items-center
        justify-center rounded px-1 align-middle text-[11px] font-semibold tabular-nums
        transition-colors ${
          active
            ? "bg-accent-600 text-white"
            : "bg-accent-500/15 text-accent-700 hover:bg-accent-500/30 dark:text-accent-300"
        }`}
    >
      {marker}
    </button>
  );
}

function renderInline(text: string, props: Props, keyPrefix: string): ReactNode[] {
  return text.split(INLINE).map((piece, index) => {
    const key = `${keyPrefix}-${index}`;
    if (!piece) return <Fragment key={key} />;

    if (piece.startsWith("**") && piece.endsWith("**")) {
      return (
        <strong key={key} className="font-semibold text-ink-900 dark:text-ink-50">
          {piece.slice(2, -2)}
        </strong>
      );
    }
    if (piece.startsWith("`") && piece.endsWith("`")) {
      return (
        <code
          key={key}
          className="rounded bg-ink-200/70 px-1 py-0.5 font-mono text-[0.85em] dark:bg-ink-800"
        >
          {piece.slice(1, -1)}
        </code>
      );
    }
    if (piece.startsWith("*") && piece.endsWith("*") && piece.length > 2) {
      return (
        <em key={key} className="italic">
          {piece.slice(1, -1)}
        </em>
      );
    }
    const citation = /^\[(\d{1,2})\]$/.exec(piece);
    if (citation) {
      const marker = Number(citation[1]);
      return (
        <CitationChip
          key={key}
          marker={marker}
          active={props.activeCitation === marker}
          onClick={props.onCitationClick}
        />
      );
    }
    return <Fragment key={key}>{piece}</Fragment>;
  });
}

export function AnswerText(props: Props) {
  const blocks = props.text.split(/\n{2,}/);

  return (
    <div className="space-y-3 text-[15px] leading-relaxed">
      {blocks.map((block, blockIndex) => {
        const lines = block.split("\n").filter((line) => line.trim());
        const isList = lines.length > 0 && lines.every((line) => /^\s*([-*]|\d+\.)\s+/.test(line));

        if (isList) {
          return (
            <ul key={blockIndex} className="ml-1 space-y-1.5">
              {lines.map((line, lineIndex) => (
                <li key={lineIndex} className="flex gap-2.5">
                  <span
                    aria-hidden
                    className="mt-[9px] h-1 w-1 shrink-0 rounded-full bg-ink-400 dark:bg-ink-500"
                  />
                  <span>
                    {renderInline(
                      line.replace(/^\s*([-*]|\d+\.)\s+/, ""),
                      props,
                      `${blockIndex}-${lineIndex}`,
                    )}
                  </span>
                </li>
              ))}
            </ul>
          );
        }

        const heading = /^#{1,4}\s+(.*)$/.exec(block.trim());
        if (heading) {
          return (
            <h3 key={blockIndex} className="text-sm font-semibold text-ink-900 dark:text-ink-100">
              {renderInline(heading[1], props, `${blockIndex}-h`)}
            </h3>
          );
        }

        return <p key={blockIndex}>{renderInline(block, props, String(blockIndex))}</p>;
      })}
    </div>
  );
}
