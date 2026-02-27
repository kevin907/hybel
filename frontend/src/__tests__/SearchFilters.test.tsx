import { render, screen, fireEvent } from "@testing-library/react";
import SearchFilters from "@/components/messaging/SearchFilters";

describe("SearchFilters", () => {
  it("renders filter toggle button", () => {
    render(<SearchFilters filters={{}} onChange={() => {}} />);
    expect(screen.getByText("Filtre")).toBeInTheDocument();
  });

  it("expands filter panel on click", () => {
    render(<SearchFilters filters={{}} onChange={() => {}} />);

    fireEvent.click(screen.getByText("Filtre"));

    expect(screen.getByText("Alle statuser")).toBeInTheDocument();
    expect(screen.getByText("Alle typer")).toBeInTheDocument();
    expect(screen.getByText("Kun med vedlegg")).toBeInTheDocument();
    expect(screen.getByText("Kun uleste")).toBeInTheDocument();
  });

  it("shows active filter count badge", () => {
    render(
      <SearchFilters
        filters={{ status: "open", has_attachment: true }}
        onChange={() => {}}
      />
    );

    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("shows reset button when filters are active", () => {
    render(
      <SearchFilters filters={{ status: "open" }} onChange={() => {}} />
    );

    expect(screen.getByText("Nullstill")).toBeInTheDocument();
  });

  it("does not show reset button when no filters active", () => {
    render(<SearchFilters filters={{}} onChange={() => {}} />);

    expect(screen.queryByText("Nullstill")).not.toBeInTheDocument();
  });

  it("calls onChange with empty object on reset", () => {
    const onChange = jest.fn();
    render(
      <SearchFilters filters={{ status: "open" }} onChange={onChange} />
    );

    fireEvent.click(screen.getByText("Nullstill"));

    expect(onChange).toHaveBeenCalledWith({});
  });

  it("calls onChange when status filter changes", () => {
    const onChange = jest.fn();
    render(<SearchFilters filters={{}} onChange={onChange} />);

    fireEvent.click(screen.getByText("Filtre"));

    const statusSelect = screen.getByDisplayValue("Alle statuser");
    fireEvent.change(statusSelect, { target: { value: "open" } });

    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ status: "open" })
    );
  });
});
