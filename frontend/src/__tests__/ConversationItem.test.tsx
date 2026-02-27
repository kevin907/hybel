import { render, screen } from "@testing-library/react";
import ConversationItem from "@/components/messaging/ConversationItem";
import type { ConversationListItem } from "@/types/messaging";

// Mock next/link
jest.mock("next/link", () => {
  return function MockLink({
    children,
    ...props
  }: {
    children: React.ReactNode;
    href: string;
  }) {
    return <a {...props}>{children}</a>;
  };
});

// Mock the store
jest.mock("@/stores/messaging", () => ({
  useMessagingStore: (selector: (s: Record<string, unknown>) => unknown) =>
    selector({
      activeConversationId: null,
      setActiveConversation: jest.fn(),
      unreadCounts: {},
    }),
}));

function makeConversation(
  overrides: Partial<ConversationListItem> = {}
): ConversationListItem {
  return {
    id: "conv-1",
    subject: "Test samtale",
    conversation_type: "general",
    status: "open",
    property: null,
    unread_count: 0,
    last_message: null,
    participants: [
      { id: "p-1", name: "Ola Nordmann", role: "tenant", side: "tenant_side" },
      {
        id: "p-2",
        name: "Kari Hansen",
        role: "landlord",
        side: "landlord_side",
      },
    ],
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    ...overrides,
  };
}

describe("ConversationItem", () => {
  it("renders subject", () => {
    render(<ConversationItem conversation={makeConversation()} />);
    expect(screen.getByText("Test samtale")).toBeInTheDocument();
  });

  it("shows 'Ingen emne' when no subject", () => {
    render(
      <ConversationItem conversation={makeConversation({ subject: "" })} />
    );
    expect(screen.getByText("Ingen emne")).toBeInTheDocument();
  });

  it("shows last message preview", () => {
    render(
      <ConversationItem
        conversation={makeConversation({
          last_message: {
            id: "msg-1",
            content: "Hei, heisen er ødelagt",
            sender: {
              id: "u-1",
              email: "a@b.no",
              first_name: "A",
              last_name: "B",
            },
            created_at: new Date().toISOString(),
            is_internal: false,
          },
        })}
      />
    );
    expect(screen.getByText(/heisen er ødelagt/)).toBeInTheDocument();
  });

  it("shows unread badge when count > 0", () => {
    render(
      <ConversationItem
        conversation={makeConversation({ unread_count: 3 })}
      />
    );
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("shows participant avatars", () => {
    const { container } = render(
      <ConversationItem conversation={makeConversation()} />
    );
    // Should render 2 avatars (ON, KH)
    expect(screen.getByText("ON")).toBeInTheDocument();
    expect(screen.getByText("KH")).toBeInTheDocument();
  });

  it("shows empty state when no messages", () => {
    render(<ConversationItem conversation={makeConversation()} />);
    expect(screen.getByText("Ingen meldinger ennå")).toBeInTheDocument();
  });
});
