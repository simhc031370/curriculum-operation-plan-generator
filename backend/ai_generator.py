"""멀티 LLM 라우터.

업로드된 운영계획서 서식(골격)을 그대로 두고
입력 조건·공식 성취기준으로 내용만 채워
1학기 분량 교수학습평가 운영계획서를 생성한다.
"""

from __future__ import annotations

import re

SYSTEM_PROMPT = (
    "당신은 대한민국 초·중·고등학교 운영계획서 작성 전문가입니다. "
    "핵심 임무는 '새 문서를 창작'하는 것이 아니라 "
    "'사용자가 업로드한 서식 파일을 그대로 두고 빈칸·내용만 채우는 것'입니다. "
    "업로드 서식의 목차, 제목 문구, 항목 순서, 표의 열/행 구성, 번호 체계, 문체를 "
    "한 글자도 바꾸지 말고 복제한 뒤, 셀과 본문 내용만 새 입력 조건으로 교체하세요. "
    "서식에 없는 새로운 대목차·새 표 양식을 만들지 마세요. "
    "국가성취기준은 프롬프트에 제공된 공식 목록만 사용하세요. "
    "HTML 금지. GitHub Flavored Markdown만 출력하세요. "
    "빈칸·미정·추후작성·예시 문구를 남기지 마세요."
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
    written_exam_count: int,
    written_exam_ratio: int,
    performance_exam_count: int,
    performance_exam_ratio: int,
    document_text: str,
    official_standards_block: str,
) -> str:
    max_chars = 80000
    clipped = document_text[:max_chars]
    truncation_note = (
        "\n\n[참고: 업로드 문서가 길어 일부만 전달되었습니다. "
        "전달된 범위의 서식은 끝까지 채우세요.]"
        if len(document_text) > max_chars
        else ""
    )
    perf_count = _count_items(performance_items)

    return f"""# 임무
업로드된 「운영계획서 서식」을 골격으로 삼아, 아래 입력 조건으로 **내용만 채운 완성본**을 출력하라.
새 양식을 창작하지 말고, 서식을 **베껴 쓴 뒤 칸을 채우는** 방식으로 작업하라.

# 업로드 서식 (형식·목차·표의 유일한 기준 — 이 구조를 1:1로 복제해 채울 것)
{clipped}{truncation_note}

# 채워야 할 입력 조건
- 학교급: {school_level}
- 학년: {grade}
- 과목: {subject}
- 시수(학기 단위): {total_hours}시간
- 국가성취기준 교육과정: {curriculum}
- 해당 학기 수업 대단원명:
{unit_names}
- 수행평가 항목 ({perf_count}개):
{performance_items}
- 지필평가 횟수: {written_exam_count}회 / 반영 비율: {written_exam_ratio}%
- 수행평가 실시 횟수: {performance_exam_count}회 / 반영 비율: {performance_exam_ratio}%

{official_standards_block}

# 작성 절차 (반드시 이 순서)
1. 업로드 서식에서 대제목·중제목·소제목·표 헤더·열 구성을 있는 그대로 파악한다.
2. 출력도 같은 순서·같은 제목 문구·같은 표 열로 시작한다.
3. 각 칸/문단의 기존 예시 내용(다른 과목·작년 내용 등)을 지우고, 위 입력 조건으로 다시 쓴다.
4. 원본에 있는 모든 표·모든 항목을 빠짐없이 채운다. 원본에 없는 새 대목차·새 표 양식은 만들지 않는다.
5. 수행평가 항목 수가 원본보다 많으면, **원본의 수행평가/평가계획 영역 안에서만**
   행을 늘리거나 동일 양식의 세부표를 항목 수만큼 복제한다. 다른 양식을 새로 발명하지 않는다.
6. 성취기준은 위 「공식 국가성취기준」 표의 코드+진술만 그대로 사용한다. 창작 금지.

# 절대 금지
- 업로드 서식과 다른 목차로 처음부터 다시 쓰기
- 서식에 없는 섹션을 임의 추가 (예: 원본에 없는 '총론/개요'를 길게 창작)
- 표 열 이름을 바꾸거나 열을 마음대로 추가/삭제
- HTML 태그 사용
- 빈칸, '작성 예정', '예시', '추후 기입'
- 공식 목록에 없는 성취기준 코드 생성

# 수치 일치 (필수)
- 시수 합계 = {total_hours}
- 지필평가 {written_exam_count}회, 반영 {written_exam_ratio}%
- 수행평가 {performance_exam_count}회, 반영 {performance_exam_ratio}%
- 지필+수행 반영 비율 합계 100%
- 수행평가 항목별 반영 비율 합 = {performance_exam_ratio}%

# 출력
- 완성된 운영계획서 본문만 Markdown으로 출력
- 서식 분석 과정, 설명, 서론, 후기는 출력하지 말 것
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
    written_exam_count: int,
    written_exam_ratio: int,
    performance_exam_count: int,
    performance_exam_ratio: int,
    document_text: str,
    official_standards_block: str,
) -> str:
    """업로드 서식 골격 유지 + 공식 성취기준 반영 운영계획서를 반환한다."""
    if not (document_text or "").strip():
        raise ValueError(
            "업로드 서식에서 텍스트를 읽지 못했습니다. "
            "HWPX로 저장해 다시 업로드해 주세요."
        )

    provider_normalized = provider.strip().lower()
    user_prompt = _build_user_prompt(
        school_level=school_level,
        grade=grade,
        subject=subject,
        total_hours=total_hours,
        curriculum=curriculum,
        unit_names=unit_names,
        performance_items=performance_items,
        written_exam_count=written_exam_count,
        written_exam_ratio=written_exam_ratio,
        performance_exam_count=performance_exam_count,
        performance_exam_ratio=performance_exam_ratio,
        document_text=document_text,
        official_standards_block=official_standards_block,
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
        temperature=0.15,
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
        create_kwargs["temperature"] = 0.15

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
