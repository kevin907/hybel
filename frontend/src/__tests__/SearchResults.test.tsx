import { render, screen } from "@testing-library/react";
import SearchResults from "@/components/messaging/SearchResults";
import type { SearchResult } from "@/types/messaging";

const mockResults: SearchResult[] = [
  {
    id: "msg-1",
    conversation_id: "conv-1",
    conversation_subject: "Vannlekkasje på badet",
    sender: {
      id: "u-1",
      email: "ola@hybel.no",
      first_name: "Ola",
      last_name: "Nordmann",
    },
    content: "Vi trenger en rørlegger snarest.",
    snippet: "Vi trenger en <b>rørlegger</b> snarest.",
    message_type: "message",
    is_internal: false,
    created_at: new Date().toISOString(),
  },
  {
    id: "msg-2",
    conversation_id: "conv-1",
    conversation_subject: "Vannlekkasje på badet",
    sender: {
      id: "u-2",
      email: "kari@hybel.no",
      first_name: "Kari",
      last_name: "Hansen",
    },
    content: "Intern: Kontaktet forsikring.",
    snippet: "Intern: Kontaktet <b>forsikring</b>.",
    message_type: "internal_comment",
    is_internal: true,
    created_at: new Date().toISOString(),
  },
];

describe("SearchResults", () => {
  it("shows empty state when no results", () => {
    render(<SearchResults results={[]} totalCount={0} />);
    expect(screen.getByText("Fant ingen meldinger")).toBeInTheDocument();
  });

  it("shows total match count", () => {
    render(<SearchResults results={mockResults} totalCount={42} />);
    expect(screen.getByText("42 treff")).toBeInTheDocument();
  });

  it("renders search result entries", () => {
    render(<SearchResults results={mockResults} totalCount={2} />);

    const subjects = screen.getAllByText("Vannlekkasje på badet");
    expect(subjects).toHaveLength(2);
    expect(screen.getByText("Ola Nordmann")).toBeInTheDocument();
  });

  it("shows internal badge for internal comments", () => {
    render(<SearchResults results={mockResults} totalCount={2} />);
    expect(screen.getByText("Intern")).toBeInTheDocument();
  });

  it("renders links to conversations", () => {
    render(<SearchResults results={mockResults} totalCount={2} />);

    const links = screen.getAllByRole("link");
    expect(links[0]).toHaveAttribute("href", "/meldinger/conv-1");
  });
});
