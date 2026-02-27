import { render } from "@testing-library/react";
import Icon from "@/components/ui/Icon";

describe("Icon", () => {
  it("renders SVG with correct size", () => {
    const { container } = render(<Icon name="search" size={20} />);
    const svg = container.querySelector("svg");
    expect(svg).toBeTruthy();
    expect(svg?.getAttribute("width")).toBe("20");
    expect(svg?.getAttribute("height")).toBe("20");
  });

  it("returns null for unknown icon name", () => {
    // @ts-expect-error testing unknown icon
    const { container } = render(<Icon name="nonexistent" />);
    expect(container.firstChild).toBeNull();
  });

  it("applies className", () => {
    const { container } = render(
      <Icon name="lock" className="text-amber-500" />
    );
    const svg = container.querySelector("svg");
    expect(svg?.getAttribute("class")).toContain("text-amber-500");
  });

  it("renders spinner with animation class", () => {
    const { container } = render(<Icon name="spinner" />);
    const svg = container.querySelector("svg");
    expect(svg?.getAttribute("class")).toContain("animate-spin");
  });

  it("renders send icon with fill", () => {
    const { container } = render(<Icon name="send" />);
    const svg = container.querySelector("svg");
    expect(svg?.getAttribute("fill")).toBe("currentColor");
  });

  it("renders stroke icons with stroke properties", () => {
    const { container } = render(<Icon name="message" />);
    const svg = container.querySelector("svg");
    expect(svg?.getAttribute("stroke")).toBe("currentColor");
    expect(svg?.getAttribute("stroke-width")).toBe("2");
  });
});
