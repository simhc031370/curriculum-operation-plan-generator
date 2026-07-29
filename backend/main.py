"""교수학습평가 운영계획서 자동 생성 FastAPI 서버.

실행:
    cd backend
    pip install -r requirements.txt
    uvicorn main:app --reload --port 8000
"""

from __future__ import annotations

import os
import tempfile
import traceback
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ai_generator import generate_operation_plan
from document_parser import extract_text_from_file

app = FastAPI(
    title="교수학습평가 운영계획서 자동 생성 API",
    description=(
        "업로드한 운영계획서(PDF/HWP/HWPX)를 분석하고 "
        "학교급·학년·과목·총 시수에 맞는 1학기 운영계획서를 생성합니다."
    ),
    version="2.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok", "message": "교수학습평가 운영계획서 자동 생성 API"}


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.post("/api/generate")
async def generate(
    file: UploadFile = File(..., description="참고용 운영계획서 (PDF/HWP/HWPX)"),
    school_level: str = Form(..., description="학교급"),
    grade: str = Form(..., description="학년"),
    subject: str = Form(..., description="과목명"),
    total_hours: int = Form(..., description="시수 입력(학기 단위)"),
    curriculum: str = Form(..., description="국가성취기준 교육과정"),
    unit_names: str = Form(..., description="해당 학기 수업 대단원명"),
    performance_items: str = Form(..., description="수행평가 항목"),
    provider: str = Form(..., description="AI 공급사"),
    model: str = Form(..., description="모델명"),
    api_key: str = Form(..., description="사용자 API 키"),
) -> JSONResponse:
    allowed_curriculums = {"2015 개정 교육과정", "2022 개정 교육과정"}

    if not school_level.strip():
        raise HTTPException(status_code=400, detail="학교급을 선택해 주세요.")
    if not grade.strip():
        raise HTTPException(status_code=400, detail="학년을 선택해 주세요.")
    if not subject.strip():
        raise HTTPException(status_code=400, detail="과목명을 입력해 주세요.")
    if total_hours <= 0:
        raise HTTPException(status_code=400, detail="시수(학기 단위)는 1 이상이어야 합니다.")
    if total_hours > 200:
        raise HTTPException(status_code=400, detail="시수(학기 단위)는 200 이하로 입력해 주세요.")
    if curriculum.strip() not in allowed_curriculums:
        raise HTTPException(
            status_code=400,
            detail="교육과정은 '2015 개정 교육과정' 또는 '2022 개정 교육과정' 중 선택해 주세요.",
        )
    if not unit_names.strip():
        raise HTTPException(
            status_code=400,
            detail="해당 학기에 수업할 대단원명을 입력해 주세요.",
        )
    if not performance_items.strip():
        raise HTTPException(
            status_code=400,
            detail="수행평가 항목을 입력해 주세요.",
        )
    if not provider.strip():
        raise HTTPException(status_code=400, detail="AI 공급사를 선택해 주세요.")
    if not model.strip():
        raise HTTPException(status_code=400, detail="모델을 선택해 주세요.")
    if not api_key.strip():
        raise HTTPException(status_code=400, detail="API Key를 입력해 주세요.")
    if not file.filename:
        raise HTTPException(status_code=400, detail="운영계획서 파일을 업로드해 주세요.")

    suffix = Path(file.filename).suffix.lower() or ".bin"
    if suffix not in {".pdf", ".hwp", ".hwpx"}:
        raise HTTPException(
            status_code=400,
            detail="PDF, HWP, HWPX 파일만 업로드할 수 있습니다.",
        )

    tmp_path: str | None = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            if not content:
                raise HTTPException(status_code=400, detail="빈 파일입니다.")
            tmp.write(content)
            tmp_path = tmp.name

        document_text = extract_text_from_file(tmp_path)
        if not document_text.strip():
            raise HTTPException(
                status_code=400,
                detail="문서에서 텍스트를 추출하지 못했습니다.",
            )

        markdown = generate_operation_plan(
            provider=provider,
            model=model,
            api_key=api_key.strip(),
            school_level=school_level.strip(),
            grade=grade.strip(),
            subject=subject.strip(),
            total_hours=total_hours,
            curriculum=curriculum.strip(),
            unit_names=unit_names.strip(),
            performance_items=performance_items.strip(),
            document_text=document_text,
        )

        return JSONResponse(
            content={
                "success": True,
                "filename": file.filename,
                "school_level": school_level.strip(),
                "grade": grade.strip(),
                "subject": subject.strip(),
                "total_hours": total_hours,
                "curriculum": curriculum.strip(),
                "unit_names": unit_names.strip(),
                "performance_items": performance_items.strip(),
                "provider": provider.strip().lower(),
                "model": model.strip(),
                "markdown": markdown,
            }
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"운영계획서 생성 중 오류가 발생했습니다: {exc}",
        ) from exc
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
