import { renderHook, act } from "@testing-library/react";
import { useDebounce } from "@/hooks/useDebounce";

describe("useDebounce", () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it("returns initial value immediately", () => {
    const { result } = renderHook(() => useDebounce("hello", 300));
    expect(result.current).toBe("hello");
  });

  it("returns debounced value after delay", () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebounce(value, 300),
      { initialProps: { value: "hello" } }
    );

    rerender({ value: "world" });
    expect(result.current).toBe("hello");

    act(() => {
      jest.advanceTimersByTime(300);
    });

    expect(result.current).toBe("world");
  });

  it("resets timer on rapid changes", () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebounce(value, 300),
      { initialProps: { value: "a" } }
    );

    rerender({ value: "b" });
    act(() => {
      jest.advanceTimersByTime(200);
    });

    rerender({ value: "c" });
    act(() => {
      jest.advanceTimersByTime(200);
    });

    // "c" shouldn't be applied yet (only 200ms since last change)
    expect(result.current).toBe("a");

    act(() => {
      jest.advanceTimersByTime(100);
    });

    expect(result.current).toBe("c");
  });
});
