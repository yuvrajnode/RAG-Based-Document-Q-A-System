/** Inline icon set. A dozen 24px glyphs is smaller than any icon package. */
import type { SVGProps } from "react";

type Props = SVGProps<SVGSVGElement>;

const base = {
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.7,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

export const UploadIcon = (props: Props) => (
  <svg {...base} {...props}>
    <path d="M12 16V4m0 0L7.5 8.5M12 4l4.5 4.5" />
    <path d="M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3" />
  </svg>
);

export const SendIcon = (props: Props) => (
  <svg {...base} {...props}>
    <path d="M4.5 12h13m0 0-5.5-5.5M17.5 12 12 17.5" />
  </svg>
);

export const TrashIcon = (props: Props) => (
  <svg {...base} {...props}>
    <path d="M4.5 7h15M9.5 7V5.5A1.5 1.5 0 0 1 11 4h2a1.5 1.5 0 0 1 1.5 1.5V7" />
    <path d="M6.5 7l.8 11a2 2 0 0 0 2 1.9h5.4a2 2 0 0 0 2-1.9l.8-11" />
  </svg>
);

export const DocIcon = (props: Props) => (
  <svg {...base} {...props}>
    <path d="M14 3.5H7.5A1.5 1.5 0 0 0 6 5v14a1.5 1.5 0 0 0 1.5 1.5h9A1.5 1.5 0 0 0 18 19V7.5z" />
    <path d="M14 3.5V7a.5.5 0 0 0 .5.5H18M9 13h6M9 16.5h4" />
  </svg>
);

export const SparkIcon = (props: Props) => (
  <svg {...base} {...props}>
    <path d="M12 3.5 13.7 9l5.5 1.7-5.5 1.7L12 18l-1.7-5.6L4.8 10.7 10.3 9z" />
  </svg>
);

export const SunIcon = (props: Props) => (
  <svg {...base} {...props}>
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
  </svg>
);

export const MoonIcon = (props: Props) => (
  <svg {...base} {...props}>
    <path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z" />
  </svg>
);

export const StopIcon = (props: Props) => (
  <svg {...base} {...props}>
    <rect x="7" y="7" width="10" height="10" rx="2" />
  </svg>
);

export const LayersIcon = (props: Props) => (
  <svg {...base} {...props}>
    <path d="m12 3.5 8 4.5-8 4.5L4 8z" />
    <path d="m4 12 8 4.5L20 12M4 16l8 4.5L20 16" />
  </svg>
);

export const CloseIcon = (props: Props) => (
  <svg {...base} {...props}>
    <path d="M6 6l12 12M18 6 6 18" />
  </svg>
);

export const SearchIcon = (props: Props) => (
  <svg {...base} {...props}>
    <circle cx="11" cy="11" r="6.5" />
    <path d="m16 16 4 4" />
  </svg>
);
