import React from "react";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useMessagingStore } from "@/stores/messaging";
import type { Message, ConversationListItem } from "@/types/messaging";
import MessageBubble from "@/components/messaging/MessageBubble";
import ConversationItem from "@/components/messaging/ConversationItem";
import ConnectionStatus from "@/components/messaging/ConnectionStatus";

// ──────────────────────────────────────────────────
// Mocks
// ──────────────────────────────────────────────────

jest.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: {
      id: "u1",
      email: "t@t.com",
      first_name: "Test",
      last_name: "User",
    },
    isAuthenticated: true,
  }),
}));

jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: jest.fn() }),
  usePathname: () => "/meldinger",
}));

jest.mock("next/link", () => {
  // eslint-disable-next-line react/display-name
  return ({ children, ...props }: { children?: React.ReactNode; [key: string]: unknown }) => (
    <a {...props}>{children}</a>
  );
});

// ──────────────────────────────────────────────────
// Wrapper
// ──────────────────────────────────────────────────

const qc = new QueryClient({
  defaultOptions: { queries: { retry: false } },
});

const Wrapper = ({ children }: { children: React.ReactNode }) => (
  <QueryClientProvider client={qc}>{children}</QueryClientProvider>
);

// ──────────────────────────────────────────────────
// Helpers
// ──────────────────────────────────────────────────

function makeMessage(overrides: Partial<Message> = {}): Message {
  return {
    id: "msg-1",
    conversation: "conv-1",
    sender: {
      id: "u1",
      email: "t@t.com",
      first_name: "Test",
      last_name: "User",
    },
    content: "Hei, dette er en testmelding",
    message_type: "message",
    is_internal: false,
    attachments: [],
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    ...overrides,
  };
}

function makeConversation(
  overrides: Partial<ConversationListItem> = {}
): ConversationListItem {
  return {
    id: "conv-1",
    subject: "Vedlikeholdsforespørsel",
    conversation_type: "maintenance",
    status: "open",
    property: null,
    unread_count: 0,
    last_message: {
      id: "lm-1",
      content: "Siste melding",
      sender: {
        id: "u2",
        email: "sender@hybel.no",
        first_name: "Ola",
        last_name: "Nordmann",
      },
      created_at: new Date().toISOString(),
      is_internal: false,
    },
    participants: [
      {
        id: "p1",
        name: "Ola Nordmann",
        role: "landlord",
        side: "landlord_side",
      },
      {
        id: "p2",
        name: "Test User",
        role: "tenant",
        side: "tenant_side",
      },
    ],
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    ...overrides,
  };
}

const INITIAL_STATE = {
  activeConversationId: null,
  messages: [],
  unreadCounts: {},
  typingUsers: {},
  connectionStatus: "disconnected" as const,
  offlineQueue: [],
  searchQuery: "",
  isSearchActive: false,
};

// ──────────────────────────────────────────────────
// 1. MessageBubble
// ──────────────────────────────────────────────────

describe("MessageBubble", () => {
  beforeEach(() => {
    useMessagingStore.setState(INITIAL_STATE);
  });

  it("renders a regular message with content", () => {
    render(
      <Wrapper>
        <MessageBubble
          message={makeMessage({ content: "Hei fra leietaker" })}
          isOwn={false}
        />
      </Wrapper>
    );
    expect(screen.getByText("Hei fra leietaker")).toBeInTheDocument();
  });

  it("shows pending status text ('Sender...')", () => {
    render(
      <Wrapper>
        <MessageBubble
          message={makeMessage({ _status: "pending" })}
          isOwn={true}
        />
      </Wrapper>
    );
    expect(screen.getByText("Sender...")).toBeInTheDocument();
  });

  it("shows failed status text ('Sending feilet')", () => {
    render(
      <Wrapper>
        <MessageBubble
          message={makeMessage({ _status: "failed" })}
          isOwn={true}
        />
      </Wrapper>
    );
    expect(screen.getByText("Sending feilet")).toBeInTheDocument();
  });

  it("renders internal comment with 'Intern kommentar' label", () => {
    render(
      <Wrapper>
        <MessageBubble
          message={makeMessage({
            is_internal: true,
            message_type: "internal_comment",
            content: "Notat for utleier",
          })}
          isOwn={false}
        />
      </Wrapper>
    );
    expect(screen.getByText("Intern kommentar")).toBeInTheDocument();
    expect(screen.getByText("Notat for utleier")).toBeInTheDocument();
  });

  it("renders system event as italic centered text", () => {
    render(
      <Wrapper>
        <MessageBubble
          message={makeMessage({
            message_type: "system_event",
            content: "Kari ble lagt til i samtalen",
          })}
          isOwn={false}
        />
      </Wrapper>
    );
    const el = screen.getByText("Kari ble lagt til i samtalen");
    expect(el).toBeInTheDocument();
    expect(el.tagName).toBe("P");
    expect(el).toHaveClass("italic");
  });

  it("is exported as a memo component ($$typeof check)", () => {
    // React.memo wraps the component and sets $$typeof to Symbol.for("react.memo")
    expect(MessageBubble).toHaveProperty("$$typeof");
    expect(MessageBubble.$$typeof).toBe(Symbol.for("react.memo"));
  });
});

// ──────────────────────────────────────────────────
// 2. ConversationItem
// ──────────────────────────────────────────────────

describe("ConversationItem", () => {
  beforeEach(() => {
    useMessagingStore.setState(INITIAL_STATE);
  });

  it("shows store unread count over prop value", () => {
    // Prop says 2 unread, store says 5 — store wins
    useMessagingStore.setState({
      ...INITIAL_STATE,
      unreadCounts: { "conv-1": 5 },
    });

    render(
      <Wrapper>
        <ConversationItem
          conversation={makeConversation({ unread_count: 2 })}
        />
      </Wrapper>
    );

    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.queryByText("2")).not.toBeInTheDocument();
  });

  it("falls back to prop unread_count when store has no entry", () => {
    // Store has no entry for conv-1, so prop value should be used
    useMessagingStore.setState({
      ...INITIAL_STATE,
      unreadCounts: {},
    });

    render(
      <Wrapper>
        <ConversationItem
          conversation={makeConversation({ unread_count: 3 })}
        />
      </Wrapper>
    );

    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("highlights the active conversation with bg-blue-50", () => {
    useMessagingStore.setState({
      ...INITIAL_STATE,
      activeConversationId: "conv-1",
    });

    render(
      <Wrapper>
        <ConversationItem conversation={makeConversation()} />
      </Wrapper>
    );

    // The root <a> element should have the active class
    const link = screen.getByRole("link");
    expect(link).toHaveClass("bg-blue-50");
  });

  it("does not highlight non-active conversations", () => {
    useMessagingStore.setState({
      ...INITIAL_STATE,
      activeConversationId: "conv-other",
    });

    render(
      <Wrapper>
        <ConversationItem conversation={makeConversation()} />
      </Wrapper>
    );

    const link = screen.getByRole("link");
    expect(link).not.toHaveClass("bg-blue-50");
  });

  it("is exported as a memo component ($$typeof check)", () => {
    expect(ConversationItem).toHaveProperty("$$typeof");
    expect(ConversationItem.$$typeof).toBe(Symbol.for("react.memo"));
  });
});

// ──────────────────────────────────────────────────
// 3. ConnectionStatus
// ──────────────────────────────────────────────────

describe("ConnectionStatus", () => {
  beforeEach(() => {
    useMessagingStore.setState(INITIAL_STATE);
  });

  it("renders nothing when connected", () => {
    useMessagingStore.setState({
      ...INITIAL_STATE,
      connectionStatus: "connected",
    });

    const { container } = render(
      <Wrapper>
        <ConnectionStatus />
      </Wrapper>
    );

    expect(container.querySelector("[role='alert']")).toBeNull();
  });

  it("shows reconnecting message ('Kobler til')", () => {
    useMessagingStore.setState({
      ...INITIAL_STATE,
      connectionStatus: "reconnecting",
    });

    render(
      <Wrapper>
        <ConnectionStatus />
      </Wrapper>
    );

    const alert = screen.getByRole("alert");
    expect(alert).toBeInTheDocument();
    expect(alert.textContent).toContain("Kobler til");
  });

  it("shows disconnected message ('Frakoblet')", () => {
    useMessagingStore.setState({
      ...INITIAL_STATE,
      connectionStatus: "disconnected",
    });

    render(
      <Wrapper>
        <ConnectionStatus />
      </Wrapper>
    );

    const alert = screen.getByRole("alert");
    expect(alert).toBeInTheDocument();
    expect(alert.textContent).toContain("Frakoblet");
  });
});
