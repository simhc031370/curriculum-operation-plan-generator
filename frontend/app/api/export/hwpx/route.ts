import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const maxDuration = 60;

const BACKEND_BASE =
  process.env.BACKEND_API_BASE_URL ?? "http://127.0.0.1:8000";

export async function POST(request: NextRequest) {
  try {
    const body = await request.text();

    const backendResponse = await fetch(`${BACKEND_BASE}/api/export/hwpx`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      cache: "no-store",
    });

    if (!backendResponse.ok) {
      const text = await backendResponse.text();
      let detail = text || "한글 파일 생성에 실패했습니다.";
      try {
        const json = JSON.parse(text) as { detail?: unknown };
        if (typeof json.detail === "string") detail = json.detail;
      } catch {
        /* keep text */
      }
      return NextResponse.json({ detail }, { status: backendResponse.status });
    }

    const bytes = await backendResponse.arrayBuffer();
    const disposition =
      backendResponse.headers.get("Content-Disposition") ??
      "attachment; filename=plan.hwpx";

    return new NextResponse(bytes, {
      status: 200,
      headers: {
        "Content-Type": "application/hwp+zip",
        "Content-Disposition": disposition,
      },
    });
  } catch (error) {
    const message =
      error instanceof Error
        ? error.message
        : "백엔드 서버에 연결하지 못했습니다.";
    return NextResponse.json(
      {
        detail: `${message} (백엔드: ${BACKEND_BASE} 가 실행 중인지 확인하세요)`,
      },
      { status: 502 }
    );
  }
}
