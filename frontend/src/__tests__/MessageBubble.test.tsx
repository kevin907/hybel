import { render, screen } from "@testing-library/react";
import MessageBubble from "@/components/messaging/MessageBubble";
import type { Message } from "@/types/messaging";

const baseSender = {
  id: "user-1",
  email: "test@hybel.no",
  first_name: "Ola",
  last_name: "Nordmann",
};

const baseMessage: Message = {
  id: "msg-1",
  conversation: "conv-1",
  sender: baseSender,
  content: "Hei, heisen er ødelagt.",
  message_type: "message",
  is_internal: false,
  attachments: [],
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
};

describe("MessageBubble", () => {
  it("renders regular message content", () => {
    render(<MessageBubble message={baseMessage} isOwn={false} />);
    expect(screen.getByText("Hei, heisen er ødelagt.")).toBeInTheDocument();
  });

  it("renders sender name for other messages", () => {
    render(<MessageBubble message={baseMessage} isOwn={false} />);
    expect(screen.getByText("Ola Nordmann")).toBeInTheDocument();
  });

  it("renders internal comment with label", () => {
    const internal: Message = {
      ...baseMessage,
      message_type: "internal_comment",
      is_internal: true,
      content: "Koster 5000kr.",
    };
    render(<MessageBubble message={internal} isOwn={false} />);
    expect(screen.getByText("Intern kommentar")).toBeInTheDocument();
    expect(screen.getByText("Koster 5000kr.")).toBeInTheDocument();
  });

  it("renders system event as centered text", () => {
    const event: Message = {
      ...baseMessage,
      message_type: "system_event",
      content: "Ola la til Per som deltaker.",
    };
    render(<MessageBubble message={event} isOwn={false} />);
    expect(
      screen.getByText("Ola la til Per som deltaker.")
    ).toBeInTheDocument();
  });

  it("renders attachments with download link", () => {
    const withAttachment: Message = {
      ...baseMessage,
      attachments: [
        {
          id: "att-1",
          filename: "kvittering.pdf",
          file_type: "application/pdf",
          file_size: 2048,
          uploaded_at: new Date().toISOString(),
        },
      ],
    };
    render(<MessageBubble message={withAttachment} isOwn={false} />);
    expect(screen.getByText("kvittering.pdf")).toBeInTheDocument();
    expect(screen.getByText("2.0 KB")).toBeInTheDocument();
  });
});
