import { render, screen, fireEvent } from "@testing-library/react";
import Sidebar from "@/components/messaging/Sidebar";
import { useMessagingStore } from "@/stores/messaging";

const mockLogout = jest.fn();

jest.mock("next/navigation", () => ({
  usePathname: () => "/meldinger",
}));

jest.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: {
      id: "u-1",
      email: "ola@hybel.no",
      first_name: "Ola",
      last_name: "Nordmann",
    },
    logout: mockLogout,
  }),
}));

describe("Sidebar", () => {
  beforeEach(() => {
    mockLogout.mockClear();
    useMessagingStore.setState({ unreadCounts: {} });
  });

  it("renders navigation items", () => {
    render(<Sidebar />);

    expect(screen.getByText("Annonser")).toBeInTheDocument();
    expect(screen.getByText("Meldinger")).toBeInTheDocument();
    expect(screen.getByText("Leiekontrakter")).toBeInTheDocument();
    expect(screen.getByText("Min konto")).toBeInTheDocument();
  });

  it("displays user name", () => {
    render(<Sidebar />);
    expect(screen.getByText("Ola Nordmann")).toBeInTheDocument();
  });

  it("displays user initials", () => {
    render(<Sidebar />);
    expect(screen.getByText("ON")).toBeInTheDocument();
  });

  it("shows total unread count", () => {
    useMessagingStore.setState({
      unreadCounts: { "conv-1": 3, "conv-2": 2 },
    });
    render(<Sidebar />);
    expect(screen.getByText("5")).toBeInTheDocument();
  });

  it("renders logout button", () => {
    render(<Sidebar />);
    expect(screen.getByText("Logg ut")).toBeInTheDocument();
  });

  it("calls logout on button click", () => {
    render(<Sidebar />);

    fireEvent.click(screen.getByText("Logg ut"));
    expect(mockLogout).toHaveBeenCalled();
  });
});
