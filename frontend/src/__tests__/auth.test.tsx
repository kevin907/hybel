import { render, screen, waitFor, act } from "@testing-library/react";
import { AuthProvider, useAuth } from "@/lib/auth";
import * as api from "@/lib/api";

jest.mock("@/lib/api");
const mockedApi = api as jest.Mocked<typeof api>;

function TestConsumer() {
  const { user, isLoading, isAuthenticated } = useAuth();
  return (
    <div>
      <span data-testid="loading">{String(isLoading)}</span>
      <span data-testid="authenticated">{String(isAuthenticated)}</span>
      {user && <span data-testid="email">{user.email}</span>}
    </div>
  );
}

describe("AuthProvider", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("fetches current user on mount", async () => {
    mockedApi.getCurrentUser.mockResolvedValue({
      id: "u-1",
      email: "test@hybel.no",
      first_name: "Test",
      last_name: "User",
    });

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId("loading").textContent).toBe("false");
    });

    expect(screen.getByTestId("authenticated").textContent).toBe("true");
    expect(screen.getByTestId("email").textContent).toBe("test@hybel.no");
  });

  it("sets user to null when fetch fails", async () => {
    mockedApi.getCurrentUser.mockRejectedValue(new Error("Unauthorized"));

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId("loading").textContent).toBe("false");
    });

    expect(screen.getByTestId("authenticated").textContent).toBe("false");
  });

  it("isLoading is true during initial fetch", () => {
    mockedApi.getCurrentUser.mockReturnValue(new Promise(() => {})); // Never resolves

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    );

    expect(screen.getByTestId("loading").textContent).toBe("true");
  });
});

describe("useAuth", () => {
  it("throws when used outside AuthProvider", () => {
    // Suppress console.error for this test
    const spy = jest.spyOn(console, "error").mockImplementation(() => {});

    expect(() => render(<TestConsumer />)).toThrow(
      "useAuth must be used within AuthProvider"
    );

    spy.mockRestore();
  });

  it("login sets user", async () => {
    mockedApi.getCurrentUser.mockRejectedValue(new Error("Not logged in"));
    mockedApi.fetchCsrfToken.mockResolvedValue({ csrfToken: "token" });
    mockedApi.login.mockResolvedValue({
      id: "u-2",
      email: "new@hybel.no",
      first_name: "New",
      last_name: "User",
    });

    function LoginConsumer() {
      const { user, login } = useAuth();
      return (
        <div>
          {user && <span data-testid="email">{user.email}</span>}
          <button onClick={() => login("new@hybel.no", "pass123")}>
            Login
          </button>
        </div>
      );
    }

    render(
      <AuthProvider>
        <LoginConsumer />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.queryByTestId("email")).not.toBeInTheDocument();
    });

    await act(async () => {
      screen.getByText("Login").click();
    });

    await waitFor(() => {
      expect(screen.getByTestId("email").textContent).toBe("new@hybel.no");
    });
  });

  it("logout clears user", async () => {
    mockedApi.getCurrentUser.mockResolvedValue({
      id: "u-1",
      email: "test@hybel.no",
      first_name: "Test",
      last_name: "User",
    });
    mockedApi.logout.mockResolvedValue(undefined);

    function LogoutConsumer() {
      const { user, logout } = useAuth();
      return (
        <div>
          {user && <span data-testid="email">{user.email}</span>}
          <button onClick={() => logout()}>Logout</button>
        </div>
      );
    }

    render(
      <AuthProvider>
        <LogoutConsumer />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId("email")).toBeInTheDocument();
    });

    await act(async () => {
      screen.getByText("Logout").click();
    });

    await waitFor(() => {
      expect(screen.queryByTestId("email")).not.toBeInTheDocument();
    });
  });
});
