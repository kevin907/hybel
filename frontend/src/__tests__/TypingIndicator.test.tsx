import { render, screen } from "@testing-library/react";
import TypingIndicator from "@/components/messaging/TypingIndicator";
import { useMessagingStore } from "@/stores/messaging";

describe("TypingIndicator", () => {
  beforeEach(() => {
    useMessagingStore.setState({ typingUsers: {} });
  });

  it("renders nothing when no one is typing", () => {
    const { container } = render(
      <TypingIndicator conversationId="conv-1" />
    );
    expect(container.firstChild).toBeNull();
  });

  it("shows user name when one user is typing", () => {
    useMessagingStore.setState({
      typingUsers: { "conv-1": [{ userId: "user-1", userName: "Ola Nordmann" }] },
    });
    render(<TypingIndicator conversationId="conv-1" />);
    expect(screen.getByText(/Ola Nordmann skriver/)).toBeInTheDocument();
  });

  it("shows both names when two users are typing", () => {
    useMessagingStore.setState({
      typingUsers: {
        "conv-1": [
          { userId: "user-1", userName: "Ola Nordmann" },
          { userId: "user-2", userName: "Kari Hansen" },
        ],
      },
    });
    render(<TypingIndicator conversationId="conv-1" />);
    expect(screen.getByText(/Ola Nordmann og Kari Hansen skriver/)).toBeInTheDocument();
  });

  it("shows first name and count when more than two users are typing", () => {
    useMessagingStore.setState({
      typingUsers: {
        "conv-1": [
          { userId: "user-1", userName: "Ola Nordmann" },
          { userId: "user-2", userName: "Kari Hansen" },
          { userId: "user-3", userName: "Per Olsen" },
        ],
      },
    });
    render(<TypingIndicator conversationId="conv-1" />);
    expect(screen.getByText(/Ola Nordmann og 2 andre skriver/)).toBeInTheDocument();
  });

  it("renders nothing for a different conversation", () => {
    useMessagingStore.setState({
      typingUsers: { "conv-1": [{ userId: "user-1", userName: "Ola Nordmann" }] },
    });
    const { container } = render(
      <TypingIndicator conversationId="conv-2" />
    );
    expect(container.firstChild).toBeNull();
  });
});
