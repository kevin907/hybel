import { render, screen } from "@testing-library/react";
import Avatar from "@/components/ui/Avatar";

describe("Avatar", () => {
  it("renders initials from first and last name", () => {
    render(<Avatar firstName="Kevin" lastName="Trivedi" />);
    expect(screen.getByText("KT")).toBeInTheDocument();
  });

  it("applies correct size class for xl", () => {
    const { container } = render(
      <Avatar firstName="A" lastName="B" size="xl" />
    );
    const el = container.firstChild as HTMLElement;
    expect(el.className).toContain("h-10");
    expect(el.className).toContain("w-10");
  });

  it("applies correct size class for xs", () => {
    const { container } = render(
      <Avatar firstName="A" lastName="B" size="xs" />
    );
    const el = container.firstChild as HTMLElement;
    expect(el.className).toContain("h-5");
    expect(el.className).toContain("w-5");
  });

  it("shows inactive style when inactive", () => {
    const { container } = render(
      <Avatar firstName="A" lastName="B" inactive />
    );
    const el = container.firstChild as HTMLElement;
    expect(el.className).toContain("bg-gray-400");
  });

  it("applies color based on colorIndex", () => {
    const { container } = render(
      <Avatar firstName="A" lastName="B" colorIndex={1} />
    );
    const el = container.firstChild as HTMLElement;
    expect(el.className).toContain("bg-emerald-500");
  });

  it("applies default blue when no colorIndex", () => {
    const { container } = render(<Avatar firstName="A" lastName="B" />);
    const el = container.firstChild as HTMLElement;
    expect(el.className).toContain("bg-blue-500");
  });

  it("applies custom className", () => {
    const { container } = render(
      <Avatar firstName="A" lastName="B" className="ring-2" />
    );
    const el = container.firstChild as HTMLElement;
    expect(el.className).toContain("ring-2");
  });
});
