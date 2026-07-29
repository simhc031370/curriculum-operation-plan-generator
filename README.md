# 교수학습평가 운영계획서 자동 생성

기존 운영계획서(**PDF / HWP / HWPX**)를 업로드하고 학교급·학년·과목·총 시수를 입력하면,
AI가 문서를 분석하여 **1학기 분량** 교수학습평가 운영계획서를 생성합니다.

- **Frontend**: Next.js (App Router) + Tailwind CSS
- **Backend**: Python FastAPI
- **LLM**: OpenAI / Anthropic / Gemini (사용자 API 키, BYOK)

## 입력 항목

| 항목 | 설명 |
|------|------|
| 참고 파일 | PDF, HWP, HWPX 운영계획서 |
| 학교급 | 초등학교 / 중학교 / 고등학교 |
| 학년 | 학교급에 따른 학년 |
| 과목 | 예: 정보, 수학, 국어 |
| 총 시수 | 1학기 총 수업 시수 |

## 실행

### 백엔드

```bash
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn main:app --reload --port 8000
```

### 프론트엔드

```bash
cd frontend
npm run dev -- --port 3003
```

접속: http://localhost:3003
