import type { SVGProps } from "react";

type IconName =
  | "search"
  | "message"
  | "document"
  | "shield"
  | "bank"
  | "account"
  | "logout"
  | "clock"
  | "lock"
  | "paperclip"
  | "users"
  | "chevron-down"
  | "menu"
  | "plus"
  | "filter"
  | "send"
  | "spinner";

interface Props extends SVGProps<SVGSVGElement> {
  name: IconName;
  size?: number;
}

const ICONS: Record<IconName, { paths: string; extras?: string }> = {
  search: {
    paths: "",
    extras: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>',
  },
  message: {
    paths: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
  },
  document: {
    paths:
      '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>',
  },
  shield: {
    paths: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
  },
  bank: {
    paths: '<rect x="3" y="10" width="18" height="11" rx="1"/><path d="M12 2 3 7h18z"/>',
  },
  account: {
    paths:
      '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="10" r="3"/><path d="M7 20.662V19a2 2 0 0 1 2-2h6a2 2 0 0 1 2 2v1.662"/>',
  },
  logout: {
    paths:
      '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>',
  },
  clock: {
    paths: '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
  },
  lock: {
    paths:
      '<rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
  },
  paperclip: {
    paths:
      '<path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/>',
  },
  users: {
    paths:
      '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
  },
  "chevron-down": {
    paths: '<polyline points="6 9 12 15 18 9"/>',
  },
  menu: {
    paths:
      '<line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/>',
  },
  plus: {
    paths: '<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>',
  },
  filter: {
    paths: '<polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>',
  },
  send: {
    paths: '<path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>',
  },
  spinner: {
    paths: "",
  },
};

export default function Icon({ name, size = 16, className, ...rest }: Props) {
  if (name === "spinner") {
    return (
      <svg
        className={className || "h-4 w-4 animate-spin"}
        viewBox="0 0 24 24"
        fill="none"
        {...rest}
      >
        <circle
          className="opacity-25"
          cx="12"
          cy="12"
          r="10"
          stroke="currentColor"
          strokeWidth="4"
        />
        <path
          className="opacity-75"
          fill="currentColor"
          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
        />
      </svg>
    );
  }

  if (name === "send") {
    return (
      <svg
        width={size}
        height={size}
        viewBox="0 0 24 24"
        fill="currentColor"
        className={className}
        {...rest}
        dangerouslySetInnerHTML={{ __html: ICONS[name].paths }}
      />
    );
  }

  const icon = ICONS[name];
  if (!icon) return null;

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      {...rest}
      dangerouslySetInnerHTML={{ __html: icon.extras || icon.paths }}
    />
  );
}

export type { IconName };
