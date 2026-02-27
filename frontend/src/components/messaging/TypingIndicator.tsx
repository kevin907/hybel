"use client";

import { useMessagingStore } from "@/stores/messaging";

const EMPTY: { userId: string; userName: string }[] = [];

interface Props {
  conversationId: string;
}

export default function TypingIndicator({ conversationId }: Props) {
  const typingUsers = useMessagingStore(
    (s) => s.typingUsers[conversationId] ?? EMPTY
  );

  if (typingUsers.length === 0) return null;

  let text: string;
  if (typingUsers.length === 1) {
    text = `${typingUsers[0].userName} skriver`;
  } else if (typingUsers.length === 2) {
    text = `${typingUsers[0].userName} og ${typingUsers[1].userName} skriver`;
  } else {
    text = `${typingUsers[0].userName} og ${typingUsers.length - 1} andre skriver`;
  }

  return (
    <div className="flex items-center gap-2 px-4 py-2">
      <div className="flex gap-0.5">
        <span className="h-1.5 w-1.5 rounded-full bg-gray-400 animate-bounce [animation-delay:0ms]" />
        <span className="h-1.5 w-1.5 rounded-full bg-gray-400 animate-bounce [animation-delay:150ms]" />
        <span className="h-1.5 w-1.5 rounded-full bg-gray-400 animate-bounce [animation-delay:300ms]" />
      </div>
      <span className="text-xs text-gray-400">{text}...</span>
    </div>
  );
}
