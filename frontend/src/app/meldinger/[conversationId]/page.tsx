"use client";

import { use } from "react";
import dynamic from "next/dynamic";
import Spinner from "@/components/ui/Spinner";

const ConversationDetail = dynamic(
  () => import("@/components/messaging/ConversationDetail"),
  {
    loading: () => (
      <div className="flex flex-1 items-center justify-center">
        <Spinner />
      </div>
    ),
  }
);

export default function ConversationPage({
  params,
}: {
  params: Promise<{ conversationId: string }>;
}) {
  const { conversationId } = use(params);

  return <ConversationDetail conversationId={conversationId} />;
}
