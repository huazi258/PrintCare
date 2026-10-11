import { afterEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "@/services/http";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("apiClient", () => {
  it("通过同源代理发送 JSON 请求并携带浏览器 Cookie", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ title: "查询服务器" }), {
        headers: { "content-type": "application/json" },
      }),
    );

    const response = await apiClient.get<{ title: string }>("core", "openapi.json");

    expect(response).toEqual({ title: "查询服务器" });
    expect(fetchMock).toHaveBeenCalledWith("/api/core/openapi.json", {
      credentials: "include",
      method: "GET",
    });
  });

  it("将非 2xx 响应转换为可识别的 ApiError", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "诊断会话不存在" }), {
        status: 404,
        headers: { "content-type": "application/json" },
      }),
    );

    await expect(apiClient.get("core", "/diagnoses/missing")).rejects.toMatchObject({
      name: "ApiError",
      status: 404,
      message: "诊断会话不存在",
    });
  });

  it("将网络中断转换为 status 为 0 的 ApiError", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("Failed to fetch"));

    await expect(apiClient.get("admin", "/openapi.json")).rejects.toMatchObject({
      name: "ApiError",
      status: 0,
      message: "网络连接失败，请检查服务是否可用。",
    });
  });
});
