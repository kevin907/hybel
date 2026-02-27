import { cn, getInitials } from "@/lib/utils";

const AVATAR_COLORS = [
  "bg-blue-500",
  "bg-emerald-500",
  "bg-amber-500",
  "bg-purple-500",
  "bg-rose-500",
  "bg-cyan-500",
];

const SIZES = {
  xs: "h-5 w-5 text-[8px]",
  sm: "h-6 w-6 text-[9px]",
  md: "h-7 w-7 text-[10px]",
  lg: "h-8 w-8 text-xs",
  xl: "h-10 w-10 text-xs",
} as const;

interface Props {
  firstName: string;
  lastName: string;
  size?: keyof typeof SIZES;
  colorIndex?: number;
  inactive?: boolean;
  className?: string;
}

export default function Avatar({
  firstName,
  lastName,
  size = "lg",
  colorIndex,
  inactive = false,
  className,
}: Props) {
  const initials = getInitials(firstName, lastName);
  const bg = inactive
    ? "bg-gray-400"
    : colorIndex !== undefined
      ? AVATAR_COLORS[colorIndex % AVATAR_COLORS.length]
      : "bg-blue-500";

  return (
    <div
      className={cn(
        "flex shrink-0 items-center justify-center rounded-full font-medium text-white",
        SIZES[size],
        bg,
        className
      )}
    >
      {initials}
    </div>
  );
}

export { AVATAR_COLORS };
