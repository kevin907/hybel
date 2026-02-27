import { render, screen, fireEvent } from "@testing-library/react";
import ParticipantList from "@/components/messaging/ParticipantList";
import type { Participant } from "@/types/messaging";

const mockParticipants: Participant[] = [
  {
    id: "p-1",
    user: { id: "u-1", email: "tenant@hybel.no", first_name: "Kari", last_name: "Hansen" },
    role: "tenant",
    side: "tenant_side",
    is_active: true,
    joined_at: new Date().toISOString(),
    left_at: null,
  },
  {
    id: "p-2",
    user: { id: "u-2", email: "landlord@hybel.no", first_name: "Ola", last_name: "Nordmann" },
    role: "landlord",
    side: "landlord_side",
    is_active: true,
    joined_at: new Date().toISOString(),
    left_at: null,
  },
  {
    id: "p-3",
    user: { id: "u-3", email: "removed@hybel.no", first_name: "Per", last_name: "Berg" },
    role: "contractor",
    side: "landlord_side",
    is_active: false,
    joined_at: new Date().toISOString(),
    left_at: new Date().toISOString(),
  },
];

describe("ParticipantList", () => {
  it("shows active participant count", () => {
    render(
      <ParticipantList
        participants={mockParticipants}
        isLandlordSide={false}
      />
    );
    expect(screen.getByText("2 deltakere")).toBeInTheDocument();
  });

  it("expands to show participant details on click", () => {
    render(
      <ParticipantList
        participants={mockParticipants}
        isLandlordSide={false}
      />
    );

    fireEvent.click(screen.getByText("2 deltakere"));

    expect(screen.getByText("Kari Hansen")).toBeInTheDocument();
    expect(screen.getByText("Ola Nordmann")).toBeInTheDocument();
    expect(screen.getByText("Per Berg")).toBeInTheDocument();
  });

  it("shows role labels in Norwegian", () => {
    render(
      <ParticipantList
        participants={mockParticipants}
        isLandlordSide={false}
      />
    );

    fireEvent.click(screen.getByText("2 deltakere"));

    expect(screen.getByText(/Leietaker/)).toBeInTheDocument();
    expect(screen.getByText(/Utleier/)).toBeInTheDocument();
  });

  it("shows 'Fjernet' for inactive participants", () => {
    render(
      <ParticipantList
        participants={mockParticipants}
        isLandlordSide={false}
      />
    );

    fireEvent.click(screen.getByText("2 deltakere"));

    expect(screen.getByText(/Fjernet/)).toBeInTheDocument();
  });

  it("shows remove button for landlord side", () => {
    const onRemove = jest.fn();
    render(
      <ParticipantList
        participants={mockParticipants}
        isLandlordSide={true}
        onRemove={onRemove}
      />
    );

    fireEvent.click(screen.getByText("2 deltakere"));

    const removeButtons = screen.getAllByText("Fjern");
    expect(removeButtons.length).toBeGreaterThan(0);
  });

  it("does not show remove button for tenant side", () => {
    render(
      <ParticipantList
        participants={mockParticipants}
        isLandlordSide={false}
        onRemove={() => {}}
      />
    );

    fireEvent.click(screen.getByText("2 deltakere"));

    expect(screen.queryByText("Fjern")).not.toBeInTheDocument();
  });

  it("calls onRemove with user id", () => {
    const onRemove = jest.fn();
    render(
      <ParticipantList
        participants={mockParticipants}
        isLandlordSide={true}
        onRemove={onRemove}
      />
    );

    fireEvent.click(screen.getByText("2 deltakere"));

    const removeButtons = screen.getAllByText("Fjern");
    fireEvent.click(removeButtons[0]);

    expect(onRemove).toHaveBeenCalled();
  });
});
