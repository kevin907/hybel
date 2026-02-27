import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import ConversationItem from "@/components/messaging/ConversationItem";
import { useMessagingStore } from "@/stores/messaging";
import type { ConversationListItem } from "@/types/messaging";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false } },
});

function Wrapper({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

const mockConversation: ConversationListItem = {
  id: "abc-123",
  subject: "Vannlekkasje på badet",
  conversation_type: "maintenance",
  status: "open",
  property: null,
  unread_count: 3,
  last_message: {
    id: "msg-1",
    content: "Vi sender en rørlegger i morgen.",
    sender: {
      id: "user-1",
      email: "landlord@hybel.no",
      first_name: "Ola",
      last_name: "Nordmann",
    },
    created_at: new Date().toISOString(),
    is_internal: false,
  },
  participants: [
    { id: "user-1", name: "Ola Nordmann", role: "landlord", side: "landlord_side" },
    { id: "user-2", name: "Kari Hansen", role: "tenant", side: "tenant_side" },
  ],
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
};

describe("ConversationItem", () => {
  it("renders subject and last message preview", () => {
    render(
      <Wrapper>
        <ConversationItem conversation={mockConversation} />
      </Wrapper>
    );

    expect(screen.getByText("Vannlekkasje på badet")).toBeInTheDocument();
    expect(
      screen.getByText(/Vi sender en rørlegger/)
    ).toBeInTheDocument();
  });

  it("shows unread badge when unread_count > 0", () => {
    render(
      <Wrapper>
        <ConversationItem conversation={mockConversation} />
      </Wrapper>
    );

    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("does not show unread badge when unread_count is 0", () => {
    const read = { ...mockConversation, unread_count: 0 };
    render(
      <Wrapper>
        <ConversationItem conversation={read} />
      </Wrapper>
    );

    expect(screen.queryByText("0")).not.toBeInTheDocument();
  });

  it("shows participant initials", () => {
    render(
      <Wrapper>
        <ConversationItem conversation={mockConversation} />
      </Wrapper>
    );

    expect(screen.getByText("ON")).toBeInTheDocument();
    expect(screen.getByText("KH")).toBeInTheDocument();
  });

  it("shows +N when more than 2 participants", () => {
    const manyParticipants = {
      ...mockConversation,
      participants: [
        ...mockConversation.participants,
        { id: "user-3", name: "Per Berg", role: "contractor" as const, side: "landlord_side" as const },
      ],
    };
    render(
      <Wrapper>
        <ConversationItem conversation={manyParticipants} />
      </Wrapper>
    );

    expect(screen.getByText("+1")).toBeInTheDocument();
  });

  it("shows empty state text when no last message", () => {
    const noMsg = { ...mockConversation, last_message: null };
    render(
      <Wrapper>
        <ConversationItem conversation={noMsg} />
      </Wrapper>
    );

    expect(screen.getByText("Ingen meldinger ennå")).toBeInTheDocument();
  });
});

describe("ConversationItem — store-based unread", () => {
  beforeEach(() => {
    useMessagingStore.setState({
      activeConversationId: null,
      conversations: [],
      messages: [],
      unreadCounts: {},
      typingUsers: {},
      connectionStatus: "disconnected",
      offlineQueue: [],
      searchQuery: "",
      isSearchActive: false,
    });
  });

  it("uses store unread count over prop unread_count", () => {
    useMessagingStore.setState({ unreadCounts: { "abc-123": 7 } });
    render(
      <Wrapper>
        <ConversationItem conversation={mockConversation} />
      </Wrapper>
    );

    // Store has 7, prop has 3 — badge should show 7
    expect(screen.getByText("7")).toBeInTheDocument();
    expect(screen.queryByText("3")).not.toBeInTheDocument();
  });

  it("falls back to prop when store has no entry for conversation", () => {
    useMessagingStore.setState({ unreadCounts: {} });
    render(
      <Wrapper>
        <ConversationItem conversation={mockConversation} />
      </Wrapper>
    );

    // Store has no entry for abc-123 — falls back to prop unread_count: 3
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("renders without crash when store unreadCounts is empty object", () => {
    useMessagingStore.setState({ unreadCounts: {} });
    const zeroUnread = { ...mockConversation, unread_count: 0 };
    render(
      <Wrapper>
        <ConversationItem conversation={zeroUnread} />
      </Wrapper>
    );

    expect(screen.getByText("Vannlekkasje på badet")).toBeInTheDocument();
    // No badge should appear
    expect(screen.queryByRole("badge")).not.toBeInTheDocument();
  });

  it("renders without crash when unreadCounts is undefined", () => {
    // Simulate the exact bug scenario: store hydration not yet complete
    useMessagingStore.setState({ unreadCounts: undefined as any });
    render(
      <Wrapper>
        <ConversationItem conversation={mockConversation} />
      </Wrapper>
    );

    // Should not crash, and should fall back to prop unread_count: 3
    expect(screen.getByText("Vannlekkasje på badet")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
  });
});
