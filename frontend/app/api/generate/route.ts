import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const maxDuration = 300;

const BACKEND_BASE =
  process.env.BACKEND_API_BASE_URL ?? "http://127.0.0.1:8000";

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData();

    const backendResponse = await fetch(`${BACKEND_BASE}/api/generate`, {
      method: "POST",
      body: formData,
      // Node fetch는 브라우저 CORS 제약을 받지 않음
      cache: "no-store",
    });

    const text = await backendResponse.text();
    let payload: unknown = null;
    try {
      payload = text ? JSON.parse(text) : null;
    } catch {
      payload = { detail: text || "백엔드 응답을 해석하지 못했습니다." };
    }

    return NextResponse.json(payload, { status: backendResponse.status });
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
