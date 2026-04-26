import { describe, expect, it } from "vitest";

import { normalizeApiBase, resolveApiUrl } from "./api";

describe("api transport helpers", () => {
  it("uses relative api paths by default", () => {
    expect(normalizeApiBase(undefined)).toBe("");
    expect(resolveApiUrl("/api/presets", "")).toBe("/api/presets");
  });

  it("uses an explicit API base override when provided", () => {
    expect(normalizeApiBase("https://api.example.com/")).toBe("https://api.example.com");
    expect(resolveApiUrl("/api/presets", "https://api.example.com")).toBe("https://api.example.com/api/presets");
  });
});
