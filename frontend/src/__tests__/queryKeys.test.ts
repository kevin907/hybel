import { queryKeys } from "@/lib/queryKeys";

describe("queryKeys", () => {
  it("conversations returns static key", () => {
    expect(queryKeys.conversations).toEqual(["conversations"]);
  });

  it("conversation returns key with id", () => {
    expect(queryKeys.conversation("conv-1")).toEqual(["conversation", "conv-1"]);
  });

  it("messages returns key with id", () => {
    expect(queryKeys.messages("conv-1")).toEqual(["messages", "conv-1"]);
  });

  it("search returns key with params", () => {
    const params = { q: "test", status: "open" };
    expect(queryKeys.search(params)).toEqual(["search", params]);
  });

  it("userSearch returns key with query", () => {
    expect(queryKeys.userSearch("ola")).toEqual(["user-search", "ola"]);
  });
});
