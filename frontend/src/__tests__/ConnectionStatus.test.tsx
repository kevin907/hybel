import { render, screen } from "@testing-library/react";
import ConnectionStatus from "@/components/messaging/ConnectionStatus";
import { useMessagingStore } from "@/stores/messaging";

describe("ConnectionStatus", () => {
  beforeEach(() => {
    useMessagingStore.setState({ connectionStatus: "connected" });
  });

  it("renders nothing when connected", () => {
    const { container } = render(<ConnectionStatus />);
    expect(container.firstChild).toBeNull();
  });

  it("shows reconnecting message", () => {
    useMessagingStore.setState({ connectionStatus: "reconnecting" });
    render(<ConnectionStatus />);
    expect(screen.getByText(/Kobler til på nytt/)).toBeInTheDocument();
  });

  it("shows disconnected message", () => {
    useMessagingStore.setState({ connectionStatus: "disconnected" });
    render(<ConnectionStatus />);
    expect(
      screen.getByText(/Frakoblet/)
    ).toBeInTheDocument();
  });
});
