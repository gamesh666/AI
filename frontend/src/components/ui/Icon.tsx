/** 18px line icons (fill none, stroke currentColor 1.7, round caps), like REACH AI BOX's SVG sprite. */
const PATHS = {
  dashboard: "M4 4h6v7H4zM14 4h6v4h-6zM14 12h6v8h-6zM4 15h6v5H4z",
  monitor: "M3 6.5A1.5 1.5 0 0 1 4.5 5h11A1.5 1.5 0 0 1 17 6.5v11a1.5 1.5 0 0 1-1.5 1.5h-11A1.5 1.5 0 0 1 3 17.5zM17 10l4-2.5v9L17 14",
  logs: "M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01",
  owners: "M4 20V9a1 1 0 0 1 1-1h14a1 1 0 0 1 1 1v11M9 8V5.5A1.5 1.5 0 0 1 10.5 4h3A1.5 1.5 0 0 1 15 5.5V8M4 13h16M10.5 13v2h3v-2",
  sites: "M4 20V8l8-4 8 4v12M9 20v-6h6v6M3 20h18",
  devices: "M6 4h12a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2zM9 9h6v6H9zM9 1.5V4M15 1.5V4M9 20v2.5M15 20v2.5M1.5 9H4M1.5 15H4M20 9h2.5M20 15h2.5",
  cameras: "M3 8.5A1.5 1.5 0 0 1 4.5 7h2.2l1.4-2h7.8l1.4 2h2.2A1.5 1.5 0 0 1 21 8.5v9a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 17.5zM12 16.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7z",
  models: "M12 3l1.8 4.6L18.5 9l-4.7 1.6L12 15l-1.8-4.4L5.5 9l4.7-1.4zM18.5 15l.9 2.1 2.1.9-2.1.9-.9 2.1-.9-2.1-2.1-.9 2.1-.9zM5.5 15l.7 1.6 1.6.7-1.6.7-.7 1.5-.7-1.5-1.6-.7 1.6-.7z",
  users: "M9 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7zM2.5 20a6.5 6.5 0 0 1 13 0M16 4.5a3.5 3.5 0 0 1 0 6.5M18 14.5a6.5 6.5 0 0 1 3.5 5.5",
  logout: "M10 4H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h4M15 8l4 4-4 4M19 12H9",
  menu: "M4 7h16M4 12h16M4 17h16",
  online: "M5 12.5a10 10 0 0 1 14 0M8 15.5a5.5 5.5 0 0 1 8 0M12 19h.01M2 9.5a14.5 14.5 0 0 1 20 0",
  offline: "M3 3l18 18M8.5 16a5 5 0 0 1 4.7-1.4M5 12.5a10 10 0 0 1 4.3-2.4M12 19h.01M2 9.5a14.4 14.4 0 0 1 4.1-2.6M16.2 10.6A10 10 0 0 1 19 12.5M10.7 5.1A14.5 14.5 0 0 1 22 9.5",
  disconnect: "M9 15l-2 2a3 3 0 0 1-4.2-4.2l2-2M15 9l2-2a3 3 0 0 1 4.2 4.2l-2 2M8 4v2M4 8h2M16 20v-2M20 16h-2",
  pulse: "M3 12h4l2.5-6 4 12 2.5-6H21",
  clock: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 7v5l3 2",
  server: "M4 5h16v5H4zM4 14h16v5H4zM7.5 7.5h.01M7.5 16.5h.01",
  link: "M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1",
  shield: "M12 3l7 3v5.5c0 4.3-3 8-7 9.5-4-1.5-7-5.2-7-9.5V6z",
  cpu: "M7 7h10v10H7zM10 10h4v4h-4zM10 3v4M14 3v4M10 17v4M14 17v4M3 10h4M3 14h4M17 10h4M17 14h4",
} as const;

export type IconName = keyof typeof PATHS;

export function Icon({ name, size = 18, className }: { name: IconName; size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
    >
      <path d={PATHS[name]} />
    </svg>
  );
}
