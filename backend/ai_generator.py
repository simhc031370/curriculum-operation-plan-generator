"""멀티 LLM 라우터.

업로드된 운영계획서의 형식을 유지한 채,
대단원 국가성취기준과 수행평가 항목을 반영하여
1학기 분량 교수학습평가 운영계획서를 생성한다.
"""

from __future__ import annotations

import re

SYSTEM_PROMPT = (
    "당신은 대한민국 초·중·고등학교의 교육과정·국가성취기준·수행평가 설계에 "
    "정통한 교육과정 전문가입니다. "
    "업로드된 운영계획서의 문서 형식(목차, 항목 순서, 표 구조, 제목 체계, 문체)을 "
    "절대 벗어나지 말고 그대로 따라 작성합니다. "
    "사용자가 선택한 교육과정(2015 개정 또는 2022 개정)의 국가성취기준만 사용합니다. "
    "입력된 대단원의 국가성취기준을 확인·매핑하고, "
    "입력된 수행평가 항목마다 세부 평가 계획을 빠짐없이·구체적으로 작성합니다. "
    "수행평가 항목이 2개 이상이면 총괄 표와 항목별 세부 표를 모두 작성합니다. "
    "출력은 간결하고 정돈되게 작성하세요. 불필요하게 내용을 늘리거나 "
    "같은 내용을 반복·확장하지 마세요. "
    "HTML 태그(<br>, <p>, <div> 등)는 절대 사용하지 말고, "
    "순수 마크다운(제목, 목록, GFM 표)만 출력하세요. "
    "빈칸, '작성 필요', '예시', '...' 같은 미완성 표현을 남기지 마세요. "
    "모든 항목을 실제 수업에서 바로 쓸 수 있는 완성본으로 채우세요."
)


def sanitize_markdown(text: str) -> str:
    """LLM 응답의 HTML·잡음을 제거해 프론트 렌더링 품질을 높인다."""
    cleaned = text or ""
    cleaned = re.sub(r"^```(?:html|markdown|md)?\s*", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = re.sub(r"<br\s*/?>", "\n", cleaned, flags=re.I)
    cleaned = re.sub(r"</\s*p\s*>", "\n\n", cleaned, flags=re.I)
    cleaned = re.sub(r"<\s*p\s*[^>]*>", "", cleaned, flags=re.I)
    cleaned = re.sub(r"</?\s*div\s*[^>]*>", "\n", cleaned, flags=re.I)
    cleaned = re.sub(r"<\s*li\s*[^>]*>", "- ", cleaned, flags=re.I)
    cleaned = re.sub(r"</\s*li\s*>", "\n", cleaned, flags=re.I)
    cleaned = re.sub(r"</?\s*(ul|ol)\s*>", "\n", cleaned, flags=re.I)
    cleaned = re.sub(r"</?\s*(strong|b)\s*>", "**", cleaned, flags=re.I)
    cleaned = re.sub(r"</?\s*(em|i)\s*>", "*", cleaned, flags=re.I)
    cleaned = (
        cleaned.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
    )
    cleaned = re.sub(r"</?[a-zA-Z][^>]*>", "", cleaned)
    cleaned = re.sub(r"\[(?:작성|기입|입력|TODO|TBD)[^\]]*\]", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\n{4,}", "\n\n\n", cleaned)
    return cleaned.strip()


def _count_items(raw: str) -> int:
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    if len(lines) >= 2:
        return len(lines)
    # 한 줄에 쉼표/슬래시로 나열한 경우
    parts = re.split(r"[,/·|]", raw)
    parts = [p.strip() for p in parts if p.strip()]
    return max(len(parts), 1) if raw.strip() else 0


def _build_user_prompt(
    school_level: str,
    grade: str,
    subject: str,
    total_hours: int,
    curriculum: str,
    unit_names: str,
    performance_items: str,
    document_text: str,
) -> str:
    max_chars = 60000
    clipped = document_text[:max_chars]
    truncation_note = (
        "\n\n[참고: 업로드 문서가 길어 일부만 전달되었습니다.]"
        if len(document_text) > max_chars
        else ""
    )
    perf_count = _count_items(performance_items)
    multi_perf_rule = (
        f"""
## 수행평가 작성 규칙 (항목 {perf_count}개 — 복수이므로 표 필수)
1. 먼저 '수행평가 총괄표'를 Markdown 표로 작성할 것
   (열 예: 번호, 평가 항목명, 관련 대단원, 관련 성취기준, 평가 시기, 반영 비율, 평가 방법)
2. 이어서 각 수행평가 항목마다 별도의 세부 계획 표/소절을 작성할 것
3. 항목별 세부 계획에 반드시 포함할 내용:
   - 평가 목표
   - 관련 국가성취기준(코드+진술)
   - 평가 과제/활동 설명(구체적)
   - 평가 방법·도구
   - 채점 기준(상/중/하 또는 배점 Rubric을 표로)
   - 배점 및 반영 비율
   - 평가 시기
   - 유의사항·피드백 계획
4. 모든 수행평가 항목을 빠짐없이 작성하고, 비율 합계가 문서 형식상 맞도록 할 것
"""
        if perf_count >= 2
        else f"""
## 수행평가 작성 규칙 (항목 {perf_count}개)
1. 입력된 수행평가 항목에 맞춰 세부 평가 계획을 원본 형식에 맞게 작성할 것
2. 세부 계획에 반드시 포함할 내용:
   - 평가 목표, 관련 국가성취기준(코드+진술), 평가 과제/활동,
     평가 방법·도구, 채점 기준(표), 배점·반영 비율, 평가 시기, 유의사항
3. 추상적 한 줄 설명으로 끝내지 말고 수업에서 바로 쓸 수 있게 구체적으로 채울 것
"""
    )

    return f"""업로드된 운영계획서를 분석한 뒤, 아래 조건으로 1학기 교수학습평가 운영계획서를 작성해라.

## 입력 조건
- 학교급: {school_level}
- 학년: {grade}
- 과목: {subject}
- 시수(학기 단위): {total_hours}시간
- 국가성취기준 교육과정: {curriculum}
- 해당 학기 수업 대단원명:
{unit_names}
- 수행평가 항목:
{performance_items}

## 업로드된 운영계획서 원문 (형식의 유일한 기준)
{clipped}{truncation_note}

## 최우선 규칙: 형식 절대 준수
1. 업로드 파일의 형식을 절대 벗어나지 말 것
2. 구성 항목, 목차 순서, 표의 열 구성, 소제목, 번호 매기기, 문체를 원본과 동일하게 유지할 것
3. 원본에 없는 양식을 마음대로 만들지 말 것. 단, 수행평가 항목이 2개 이상이면
   원본의 수행평가/평가계획 영역 안에서 총괄표+항목별 세부표를 보강하는 것은 허용
4. 내용은 새 조건에 맞게 바꾸되 형식은 원본을 복제할 것

## 국가성취기준 반영 규칙
1. 반드시 「{curriculum}」의 국가성취기준만 사용할 것 (다른 개정 교육과정 혼용 금지)
2. 입력된 각 대단원명에 대해 {school_level} {grade} {subject} 성취기준을 확인할 것
3. 성취기준 코드와 진술을 명시하고, 대단원·수행평가·차시 계획에 구체적으로 연결할 것
4. 빈약한 요약 대신 개념·활동·평가 요소를 구체적으로 기술하되, 문장은 간결하게 유지할 것

{multi_perf_rule}

## 완성도·출력 품질 규칙 (매우 중요)
1. HTML 태그(<br>, <p>, <div>, <span>, <table> 등)를 절대 넣지 말 것. Markdown만 사용
2. 표는 GitHub Flavored Markdown 표(| --- |)만 사용할 것
3. 모든 칸·모든 항목을 실제 내용으로 채울 것. 빈칸/미정/추후작성/예시 금지
4. 시수 합계가 {total_hours}와 일치하는지 문서에 명시할 것
5. 각 대단원마다 학습 내용, 성취기준, 시수, 평가 연계가 빠지지 않게 작성할 것
6. 불필요한 서론·반복 설명·과도한 확장 없이 운영계획서 본문만 간결하게 출력할 것
7. 표 칸은 핵심만 쓰고 장문 나열을 피할 것. 같은 내용을 여러 섹션에 복붙하지 말 것
8. 출력 전에 스스로 검수: 누락 항목, HTML 잔여, 표 깨짐, 시수 불일치, 교육과정 혼용이 있으면 수정 후 제출
"""


def generate_operation_plan(
    provider: str,
    model: str,
    api_key: str,
    school_level: str,
    grade: str,
    subject: str,
    total_hours: int,
    curriculum: str,
    unit_names: str,
    performance_items: str,
    document_text: str,
) -> str:
    """형식 유지 + 성취기준 + 수행평가 세부계획 반영 운영계획서를 반환한다."""
    provider_normalized = provider.strip().lower()
    user_prompt = _build_user_prompt(
        school_level=school_level,
        grade=grade,
        subject=subject,
        total_hours=total_hours,
        curriculum=curriculum,
        unit_names=unit_names,
        performance_items=performance_items,
        document_text=document_text,
    )

    if provider_normalized == "openai":
        raw = _generate_with_openai(model, api_key, user_prompt)
    elif provider_normalized == "anthropic":
        raw = _generate_with_anthropic(model, api_key, user_prompt)
    elif provider_normalized in {"gemini", "google"}:
        raw = _generate_with_gemini(model, api_key, user_prompt)
    else:
        raise ValueError(
            f"지원하지 않는 AI 공급사입니다: {provider}. "
            "openai / anthropic / gemini 중 하나를 선택하세요."
        )

    return sanitize_markdown(raw)


generate_lesson_plan = generate_operation_plan


def _generate_with_openai(model: str, api_key: str, user_prompt: str) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=api_key)

    if model.startswith("gpt-5"):
        response = client.responses.create(
            model=model,
            instructions=SYSTEM_PROMPT,
            input=user_prompt,
        )
        text = (getattr(response, "output_text", None) or "").strip()
        if text:
            return text
        raise RuntimeError("OpenAI 응답이 비어 있습니다.")

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.25,
    )
    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("OpenAI 응답이 비어 있습니다.")
    return content


def _generate_with_anthropic(model: str, api_key: str, user_prompt: str) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)

    is_claude_5_plus = any(
        token in model
        for token in (
            "claude-fable-5",
            "claude-opus-5",
            "claude-sonnet-5",
            "claude-mythos",
        )
    )

    create_kwargs: dict = {
        "model": model,
        "max_tokens": 16384,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    if not is_claude_5_plus:
        create_kwargs["temperature"] = 0.25

    message = client.messages.create(**create_kwargs)

    parts: list[str] = []
    for block in message.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)

    text = "".join(parts).strip()
    if not text:
        raise RuntimeError("Anthropic 응답이 비어 있습니다.")
    return text


def _generate_with_gemini(model: str, api_key: str, user_prompt: str) -> str:
    from google import genai

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=f"{SYSTEM_PROMPT}\n\n{user_prompt}",
    )
    text = (response.text or "").strip()
    if not text:
        raise RuntimeError("Gemini 응답이 비어 있습니다.")
    return text
