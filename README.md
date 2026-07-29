# 교수학습평가 운영계획서 자동 생성

기존 운영계획서(**PDF / HWP / HWPX**)를 업로드하고 학교급·학년·과목·시수(학기 단위)·대단원·수행평가·교육과정을 입력하면,
AI가 문서를 분석하여 **학기 분량** 교수학습평가 운영계획서를 생성합니다.

- **Frontend**: Next.js (App Router) + Tailwind CSS → Vercel 배포
- **Backend**: Python FastAPI → 별도 호스팅 필요 (Render / Railway / Fly.io 등)
- **LLM**: OpenAI / Anthropic / Gemini (사용자 API 키, BYOK)

## GitHub

https://github.com/simhc031370/curriculum-operation-plan-generator

## Vercel 배포 (프론트엔드)

1. [Vercel New Project](https://vercel.com/new) 에서 위 GitHub 저장소를 Import
2. **Root Directory** 를 `frontend` 로 설정
3. Environment Variables 추가:
   - `BACKEND_API_BASE_URL` = (배포된 FastAPI 서버 주소, 예: `https://your-api.example.com`)
4. Deploy

CLI로 배포할 경우 (`frontend` 폴더에서):

```bash
cd frontend
npx vercel --prod
```

## 백엔드 배포

FastAPI는 PDF/HWP 파싱과 LLM 호출을 담당합니다. Docker 이미지로 배포할 수 있습니다.

```bash
cd backend
docker build -t curriculum-plan-api .
docker run -p 8000:8000 curriculum-plan-api
```

배포 후 Vercel 프론트의 `BACKEND_API_BASE_URL`에 백엔드 URL을 넣으면 됩니다.

## 로컬 실행

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

## 입력 항목

| 항목 | 설명 |
|------|------|
| 참고 파일 | PDF, HWP, HWPX 운영계획서 |
| 학교급 | 초등학교 / 중학교 / 고등학교 |
| 학년 | 학교급에 따른 학년 |
| 과목 | 예: 정보, 수학, 국어 |
| 시수 입력(학기 단위) | 학기 총 수업 시수 |
| 국가성취기준 | 2015 개정 / 2022 개정 교육과정 |
| 대단원명 | 학기 수업 대단원 |
| 수행평가 항목 | 수행평가 과제명 |
