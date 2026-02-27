import {
  cn,
  truncate,
  getInitials,
  getParticipantDisplayName,
  getRoleLabelNO,
  getTypeLabelNO,
  getStatusLabelNO,
  formatFileSize,
  formatShortTime,
  formatMessageTime,
} from "@/lib/utils";

describe("cn", () => {
  it("merges class names", () => {
    expect(cn("a", "b")).toBe("a b");
  });

  it("handles conditional classes", () => {
    expect(cn("base", false && "hidden", "visible")).toBe("base visible");
  });
});

describe("truncate", () => {
  it("returns short strings unchanged", () => {
    expect(truncate("hello", 10)).toBe("hello");
  });

  it("truncates long strings with ellipsis", () => {
    expect(truncate("hello world!", 5)).toBe("hello…");
  });

  it("handles exact length", () => {
    expect(truncate("hello", 5)).toBe("hello");
  });
});

describe("getInitials", () => {
  it("returns uppercase initials", () => {
    expect(getInitials("ola", "nordmann")).toBe("ON");
  });

  it("handles empty strings", () => {
    expect(getInitials("", "")).toBe("");
  });

  it("handles single character names", () => {
    expect(getInitials("A", "B")).toBe("AB");
  });
});

describe("getParticipantDisplayName", () => {
  it("prefers name field", () => {
    expect(
      getParticipantDisplayName({
        name: "Ola Nordmann",
        first_name: "Ola",
        last_name: "Nordmann",
      })
    ).toBe("Ola Nordmann");
  });

  it("falls back to first_name + last_name", () => {
    expect(
      getParticipantDisplayName({
        first_name: "Kari",
        last_name: "Hansen",
      })
    ).toBe("Kari Hansen");
  });

  it("handles missing fields", () => {
    expect(getParticipantDisplayName({})).toBe("");
  });
});

describe("getRoleLabelNO", () => {
  it("returns Norwegian labels for all roles", () => {
    expect(getRoleLabelNO("tenant")).toBe("Leietaker");
    expect(getRoleLabelNO("landlord")).toBe("Utleier");
    expect(getRoleLabelNO("property_manager")).toBe("Forvalter");
    expect(getRoleLabelNO("contractor")).toBe("Håndverker");
    expect(getRoleLabelNO("staff")).toBe("Stab");
  });
});

describe("getTypeLabelNO", () => {
  it("returns Norwegian labels for all types", () => {
    expect(getTypeLabelNO("general")).toBe("Generell");
    expect(getTypeLabelNO("maintenance")).toBe("Vedlikehold");
    expect(getTypeLabelNO("lease")).toBe("Leiekontrakt");
    expect(getTypeLabelNO("rent_query")).toBe("Leiespørsmål");
  });
});

describe("getStatusLabelNO", () => {
  it("returns Norwegian labels for all statuses", () => {
    expect(getStatusLabelNO("open")).toBe("Åpen");
    expect(getStatusLabelNO("closed")).toBe("Lukket");
    expect(getStatusLabelNO("archived")).toBe("Arkivert");
  });
});

describe("formatFileSize", () => {
  it("formats bytes", () => {
    expect(formatFileSize(500)).toBe("500 B");
  });

  it("formats kilobytes", () => {
    expect(formatFileSize(1024)).toBe("1.0 KB");
    expect(formatFileSize(1536)).toBe("1.5 KB");
  });

  it("formats megabytes", () => {
    expect(formatFileSize(1024 * 1024)).toBe("1.0 MB");
    expect(formatFileSize(2.5 * 1024 * 1024)).toBe("2.5 MB");
  });
});

describe("formatShortTime", () => {
  it("returns HH:mm for today", () => {
    const now = new Date();
    now.setHours(14, 30, 0, 0);
    expect(formatShortTime(now.toISOString())).toBe("14:30");
  });

  it("returns 'i går' for yesterday", () => {
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    expect(formatShortTime(yesterday.toISOString())).toBe("i går");
  });
});

describe("formatMessageTime", () => {
  it("returns HH:mm for today", () => {
    const now = new Date();
    now.setHours(9, 15, 0, 0);
    expect(formatMessageTime(now.toISOString())).toBe("09:15");
  });

  it("returns 'i går HH:mm' for yesterday", () => {
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    yesterday.setHours(16, 0, 0, 0);
    expect(formatMessageTime(yesterday.toISOString())).toMatch(/^i går 16:00$/);
  });
});
