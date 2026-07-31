"""멀티 LLM 라우터.

업로드 서식에서 만든 '잠긴 골격'의 [작성] 칸만 채운다.
형식 검증 후 부족하면 1회 교정 재생성한다.
"""

from __future__ import annotations

import re

from template_skeleton import (
    TemplateSkeleton,
    build_locked_checklist,
    build_template_skeleton,
    fidelity_report,
)

SYSTEM_PROMPT = (
    "당신은 학교 운영계획서 '서식 채우기' 전담 작성자입니다. "
    "절대 새 양식을 창작하지 마세요. "
    "주어진 서식 골격의 제목·표 헤더·행 라벨·순서를 한 글자도 바꾸지 말고, "
    "[작성] 칸과 [작성: ...] 문단만 새 입력 조건으로 채우세요. "
    "골격에 없는 새 대목차·새 표 양식을 추가하지 마세요. "
    "국가성취기준은 제공된 공식 목록만 사용하세요. "
    "HTML 금지. GitHub Flavored Markdown만 출력하세요. "
    "설명·서론·작업과정은 출력하지 말고 완성본 본문만 출력하세요."
)


def sanitize_markdown(text: str) -> str:
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
    cleaned = re.sub(r"\[(?:TODO|TBD)[^\]]*\]", "", cleaned, flags=re.I)
    # 남은 [작성] 표기는 제거하지 않음 — 검증용. 최종에서만 정리
    cleaned = re.sub(r"\n{4,}", "\n\n\n", cleaned)
    return cleaned.strip()


def _strip_unfilled_markers(text: str) -> str:
    text = re.sub(
        r"\[작성(?::[^\]]*)?\]",
        "",
        text,
    )
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _count_items(raw: str) -> int:
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    if len(lines) >= 2:
        return len(lines)
    parts = re.split(r"[,/·|]", raw)
    parts = [p.strip() for p in parts if p.strip()]
    return max(len(parts), 1) if raw.strip() else 0


def _build_fill_prompt(
    *,
    skeleton: TemplateSkeleton,
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
    official_standards_block: str,
    original_excerpt: str,
) -> str:
    perf_count = _count_items(performance_items)
    checklist = build_locked_checklist(skeleton)
    excerpt = original_excerpt[:12000]

    return f"""# 작업
아래 「서식 골격」을 그대로 복사한 뒤, `[작성]` / `[작성: ...]` 자리만 채워 완성본을 출력하라.

# 규칙 (위반 금지)
1. 골격의 제목 문구·순서·표 헤더·열 수·행 라벨을 변경·삭제·재배치하지 말 것
2. 골격에 없는 새 섹션/새 표 양식을 만들지 말 것
3. `[작성]` 칸은 실제 내용으로 대체 (남기지 말 것)
4. 수행평가 항목이 늘어난 경우에만, 기존 수행평가 표 양식의 행을 항목 수에 맞게 추가
5. 성취기준은 공식 목록의 코드+진술만 사용
6. 완성본 본문만 출력 (분석/설명 금지)

# 서식 골격 (이것을 1:1로 채워 출력)
{skeleton.skeleton_markdown}

{checklist}

# 입력 조건 (내용 채움용)
- 학교급: {school_level}
- 학년: {grade}
- 과목: {subject}
- 시수(학기 단위): {total_hours}시간
- 교육과정: {curriculum}
- 대단원명:
{unit_names}
- 수행평가 항목 ({perf_count}개):
{performance_items}
- 지필평가: {written_exam_count}회 / {written_exam_ratio}%
- 수행평가: {performance_exam_count}회 / {performance_exam_ratio}%
- 지필+수행 반영비율 합계 100%, 수행 항목별 비율 합 = {performance_exam_ratio}%

{official_standards_block}

# 원문 참고 발췌 (표현·문체만 참고, 구조는 위 골격 우선)
{excerpt}
"""


def _build_repair_prompt(
    *,
    draft: str,
    missing: list[str],
    skeleton: TemplateSkeleton,
    school_level: str,
    grade: str,
    subject: str,
    total_hours: int,
    unit_names: str,
    performance_items: str,
    written_exam_count: int,
    written_exam_ratio: int,
    performance_exam_count: int,
    performance_exam_ratio: int,
    official_standards_block: str,
) -> str:
    missing_block = "\n".join(f"- {m}" for m in missing[:40]) or "- (세부 누락 다수)"
    checklist = build_locked_checklist(skeleton)
    return f"""# 교정 작업
아래 초안은 업로드 서식과 맞지 않는다. 서식 골격에 맞게 **전면 재작성**하라.

# 누락·불일치
{missing_block}

# 서식 골격 (이 구조를 다시 따라 채울 것)
{skeleton.skeleton_markdown}

{checklist}

# 입력 조건
- {school_level} {grade} {subject}, 시수 {total_hours}시간
- 대단원:
{unit_names}
- 수행평가 항목:
{performance_items}
- 지필 {written_exam_count}회 {written_exam_ratio}% / 수행 {performance_exam_count}회 {performance_exam_ratio}%

{official_standards_block}

# 잘못된 초안 (참고만, 구조를 따르지 말 것)
{draft[:12000]}

# 출력
골격과 동일한 제목·표 헤더 순서로 된 완성본만 Markdown 출력.
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
    if not (document_text or "").strip():
        raise ValueError(
            "업로드 서식에서 텍스트를 읽지 못했습니다. "
            "HWPX로 저장해 다시 업로드해 주세요."
        )

    skeleton = build_template_skeleton(document_text)
    provider_normalized = provider.strip().lower()

    fill_prompt = _build_fill_prompt(
        skeleton=skeleton,
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
        official_standards_block=official_standards_block,
        original_excerpt=document_text,
    )

    raw = _call_llm(provider_normalized, model, api_key, fill_prompt)
    draft = sanitize_markdown(raw)
    score, missing = fidelity_report(skeleton, draft)

    # 서식 충실도가 낮으면 1회 교정
    if score < 0.72 and (skeleton.locked_headings or skeleton.locked_table_headers):
        repair_prompt = _build_repair_prompt(
            draft=draft,
            missing=missing,
            skeleton=skeleton,
            school_level=school_level,
            grade=grade,
            subject=subject,
            total_hours=total_hours,
            unit_names=unit_names,
            performance_items=performance_items,
            written_exam_count=written_exam_count,
            written_exam_ratio=written_exam_ratio,
            performance_exam_count=performance_exam_count,
            performance_exam_ratio=performance_exam_ratio,
            official_standards_block=official_standards_block,
        )
        repaired_raw = _call_llm(provider_normalized, model, api_key, repair_prompt)
        repaired = sanitize_markdown(repaired_raw)
        score2, missing2 = fidelity_report(skeleton, repaired)
        if score2 >= score:
            draft = repaired
            missing = missing2

    return _strip_unfilled_markers(draft)


generate_lesson_plan = generate_operation_plan


def generate_hwpx_fill_plan(
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
    official_standards_block: str,
    slots_json: str,
) -> dict[str, str]:
    """HWPX 원본 슬롯을 채울 JSON 맵을 생성한다."""
    from hwpx_inplace import parse_fills_json

    perf_count = _count_items(performance_items)
    prompt = f"""당신은 학교 운영계획서 HWPX 서식의 '빈칸 기입' 담당이다.
서식 구조는 이미 완성되어 있다. 아래 슬롯에만 값을 넣어라.

# 입력 조건
- 학교급/학년/과목: {school_level} / {grade} / {subject}
- 시수(학기): {total_hours}
- 교육과정: {curriculum}
- 대단원:
{unit_names}
- 수행평가 항목({perf_count}개):
{performance_items}
- 지필평가 {written_exam_count}회 {written_exam_ratio}% / 수행평가 {performance_exam_count}회 {performance_exam_ratio}%

{official_standards_block}

# 슬롯 JSON
{slots_json}

# 규칙
1. 출력은 JSON만: {{"fills":{{"id":"값"}}}}
2. 값이 없으면 해당 id를 생략 (빈 문자열 넣지 말 것)
3. OO/O O → "{subject}"
4. ○% → 숫자% (정기시험/지필={written_exam_ratio}, 수행={performance_exam_ratio}). ○를 과목명으로 바꾸지 말 것
5. 달력 표: 월/주/기간/공휴일은 변경 금지. 단원명·시수·성취기준·수업방법만 수업 가능 주에 기입
6. 시험주·휴업주 단원/시수는 비움(생략)
7. 성취기준은 공식 목록 코드+짧은 사용
8. 수행평가 영역명 칸에만 수행평가 항목명 기입
9. 같은 문장을 여러 빈칸에 복붙하지 말 것
10. JSON 외 텍스트 금지
"""
    provider_normalized = provider.strip().lower()
    raw = _call_llm(provider_normalized, model, api_key, prompt)
    try:
        return parse_fills_json(raw)
    except Exception:
        # 한 번 더 엄격히 재요청
        repair = (
            "이전 응답이 유효한 JSON이 아니다. "
            '반드시 {"fills":{"id":"text"}} 형식의 JSON만 출력하라.\n\n'
            f"슬롯:\n{slots_json[:20000]}\n\n이전 응답:\n{raw[:4000]}"
        )
        raw2 = _call_llm(provider_normalized, model, api_key, repair)
        return parse_fills_json(raw2)


def _call_llm(provider: str, model: str, api_key: str, user_prompt: str) -> str:
    if provider == "openai":
        return _generate_with_openai(model, api_key, user_prompt)
    if provider == "anthropic":
        return _generate_with_anthropic(model, api_key, user_prompt)
    if provider in {"gemini", "google"}:
        return _generate_with_gemini(model, api_key, user_prompt)
    raise ValueError(
        f"지원하지 않는 AI 공급사입니다: {provider}. "
        "openai / anthropic / gemini 중 하나를 선택하세요."
    )


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
        temperature=0.1,
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
        create_kwargs["temperature"] = 0.1

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
