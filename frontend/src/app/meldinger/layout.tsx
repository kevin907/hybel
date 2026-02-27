"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import InboxLayout from "@/components/messaging/InboxLayout";
import ConversationListPanel from "@/components/messaging/ConversationList";
import { useAuth } from "@/lib/auth";
import { useWebSocket } from "@/hooks/useWebSocket";
import Spinner from "@/components/ui/Spinner";

export default function MeldingerLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace("/login");
    }
  }, [isLoading, isAuthenticated, router]);

  // Connect WebSocket and wire up React Query invalidation on events
  useWebSocket(isAuthenticated);

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  return (
    <InboxLayout list={<ConversationListPanel />}>
      {children}
    </InboxLayout>
  );
}
