import { render, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import ComposeBox from "@/components/messaging/ComposeBox";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false } },
});

function Wrapper({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe("ComposeBox", () => {
  it("renders textarea with placeholder", () => {
    render(
      <Wrapper>
        <ComposeBox conversationId="conv-1" />
      </Wrapper>
    );

    expect(
      screen.getByPlaceholderText("Skriv en melding...")
    ).toBeInTheDocument();
  });

  it("shows internal comment placeholder for landlord side", () => {
    render(
      <Wrapper>
        <ComposeBox conversationId="conv-1" userSide="landlord_side" />
      </Wrapper>
    );

    // Toggle to internal mode
    fireEvent.click(screen.getByText("Melding"));

    expect(
      screen.getByPlaceholderText("Skriv intern kommentar...")
    ).toBeInTheDocument();
  });

  it("does not show internal toggle for tenant side", () => {
    render(
      <Wrapper>
        <ComposeBox conversationId="conv-1" userSide="tenant_side" />
      </Wrapper>
    );

    expect(screen.queryByText("Melding")).not.toBeInTheDocument();
  });

  it("shows internal toggle for landlord side", () => {
    render(
      <Wrapper>
        <ComposeBox conversationId="conv-1" userSide="landlord_side" />
      </Wrapper>
    );

    expect(screen.getByText("Melding")).toBeInTheDocument();
  });

  it("toggles internal comment mode", () => {
    render(
      <Wrapper>
        <ComposeBox conversationId="conv-1" userSide="landlord_side" />
      </Wrapper>
    );

    fireEvent.click(screen.getByText("Melding"));

    expect(screen.getByText("Intern kommentar")).toBeInTheDocument();
    expect(
      screen.getByText("Kun synlig for utleiersiden")
    ).toBeInTheDocument();
  });

  it("has a disabled send button when textarea is empty", () => {
    render(
      <Wrapper>
        <ComposeBox conversationId="conv-1" />
      </Wrapper>
    );

    const buttons = screen.getAllByRole("button");
    const sendButton = buttons[buttons.length - 1];
    expect(sendButton).toBeDisabled();
  });

  it("enables send button when content is entered", () => {
    render(
      <Wrapper>
        <ComposeBox conversationId="conv-1" />
      </Wrapper>
    );

    const textarea = screen.getByPlaceholderText("Skriv en melding...");
    fireEvent.change(textarea, { target: { value: "Hei!" } });

    const buttons = screen.getAllByRole("button");
    const sendButton = buttons[buttons.length - 1];
    expect(sendButton).not.toBeDisabled();
  });
});
