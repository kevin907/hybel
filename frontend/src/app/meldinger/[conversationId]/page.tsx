"use client";

import { use } from "react";
import ConversationDetail from "@/components/messaging/ConversationDetail";

export default function ConversationPage({
  params,
}: {
  params: Promise<{ conversationId: string }>;
}) {
  const { conversationId } = use(params);

  return <ConversationDetail conversationId={conversationId} />;
}
