import { render, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import UserAutocomplete from "@/components/ui/UserAutocomplete";
import type { User } from "@/types/messaging";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false } },
});

function Wrapper({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

const mockUser: User = {
  id: "u-1",
  email: "ola@hybel.no",
  first_name: "Ola",
  last_name: "Nordmann",
};

describe("UserAutocomplete", () => {
  it("renders input with placeholder", () => {
    render(
      <Wrapper>
        <UserAutocomplete onSelect={jest.fn()} placeholder="Søk etter bruker..." />
      </Wrapper>
    );
    expect(
      screen.getByPlaceholderText("Søk etter bruker...")
    ).toBeInTheDocument();
  });

  it("shows selected user with clear button", () => {
    const onClear = jest.fn();
    render(
      <Wrapper>
        <UserAutocomplete
          onSelect={jest.fn()}
          selectedUser={mockUser}
          onClear={onClear}
        />
      </Wrapper>
    );

    expect(screen.getByText("Ola Nordmann")).toBeInTheDocument();
    expect(screen.getByText("ON")).toBeInTheDocument();
    expect(screen.getByText("×")).toBeInTheDocument();
  });

  it("calls onClear when clear button clicked", () => {
    const onClear = jest.fn();
    render(
      <Wrapper>
        <UserAutocomplete
          onSelect={jest.fn()}
          selectedUser={mockUser}
          onClear={onClear}
        />
      </Wrapper>
    );

    fireEvent.click(screen.getByText("×"));
    expect(onClear).toHaveBeenCalledTimes(1);
  });

  it("applies custom className", () => {
    const { container } = render(
      <Wrapper>
        <UserAutocomplete onSelect={jest.fn()} className="mt-4" />
      </Wrapper>
    );
    const el = container.firstChild as HTMLElement;
    expect(el.className).toContain("mt-4");
  });
});
