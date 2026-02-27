import { render, screen, fireEvent } from "@testing-library/react";
import SearchBar from "@/components/messaging/SearchBar";

// Mock the zustand store
const mockSetSearchQuery = jest.fn();

const mockState = {
  searchQuery: "",
  setSearchQuery: mockSetSearchQuery,
  isSearchActive: false,
};

jest.mock("@/stores/messaging", () => ({
  useMessagingStore: (selector?: (state: Record<string, unknown>) => unknown) =>
    selector ? selector(mockState) : mockState,
}));

describe("SearchBar", () => {
  beforeEach(() => {
    mockSetSearchQuery.mockClear();
  });

  it("renders the search input", () => {
    render(<SearchBar />);
    expect(
      screen.getByPlaceholderText("Søk i meldinger...")
    ).toBeInTheDocument();
  });

  it("calls setSearchQuery on input change", () => {
    render(<SearchBar />);
    const input = screen.getByPlaceholderText("Søk i meldinger...");
    fireEvent.change(input, { target: { value: "vannlekkasje" } });
    expect(mockSetSearchQuery).toHaveBeenCalledWith("vannlekkasje");
  });
});
