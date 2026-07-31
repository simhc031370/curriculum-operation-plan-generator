"""공식 국가성취기준 조회 모듈.

2022/2015 개정 교육과정 성취기준은 교육부·KICE 학생평가지원포털(STAS)에서
조회하며, 에듀넷·티클리어를 교차 확인 출처로 명시한다.

- STAS: https://stas.moe.go.kr/cmn/main
- 에듀넷: https://www.edunet.net/main
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

STAS_BASE = "https://stas.moe.go.kr"
STAS_MAIN = "https://stas.moe.go.kr/cmn/main"
EDUNET_MAIN = "https://www.edunet.net/main"

SCHOOL_LEVEL_CODE = {
    "초등학교": "s1",
    "중학교": "s2",
    "고등학교": "s3",
}

CURRICULUM_CODE = {
    "2022 개정 교육과정": "2022",
    "2015 개정 교육과정": "2015",
}

DEFAULT_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Referer": f"{STAS_BASE}/acvmt/acvmtStd/acvmtStdList:s2",
}


@dataclass
class AchievementStandard:
    code: str
    name: str
    area: str
    school_level: str
    grade_group: str
    subject: str
    curriculum: str


class CurriculumLookupError(Exception):
    """공식 사이트에서 성취기준을 찾지 못했을 때."""


def _get_json(client: httpx.Client, path: str, params: dict[str, Any]) -> Any:
    url = f"{STAS_BASE}/rest{path}"
    response = client.get(url, params=params, headers=DEFAULT_HEADERS, timeout=40.0)
    response.raise_for_status()
    return response.json()


def _normalize(text: str) -> str:
    cleaned = re.sub(r"[\s\[\]\(\)（）·.,，、/\-]+", "", text or "")
    return cleaned.lower()


def _tokens(text: str) -> set[str]:
    parts = re.findall(r"[가-힣A-Za-z0-9]{2,}", text or "")
    return {_normalize(p) for p in parts if len(_normalize(p)) >= 2}


def _match_name(candidate: str, query: str) -> bool:
    c = _normalize(candidate)
    q = _normalize(query)
    if not c or not q:
        return False
    if c in q or q in c:
        return True
    c_tokens = _tokens(candidate)
    q_tokens = _tokens(query)
    if not c_tokens or not q_tokens:
        return False
    return bool(c_tokens & q_tokens)


def _pick_by_name(options: list[dict[str, Any]], query: str) -> dict[str, Any] | None:
    if not options:
        return None
    for opt in options:
        name = str(opt.get("name") or "")
        if _normalize(name) == _normalize(query) or _match_name(name, query):
            return opt
    return None


def _first_grade_group(options: list[dict[str, Any]], grade: str) -> dict[str, Any] | None:
    if not options:
        return None
    m = re.search(r"(\d+)", grade or "")
    if m:
        num = m.group(1)
        for opt in options:
            name = str(opt.get("name") or "")
            if num in name:
                return opt
    return options[0]


def fetch_official_standards(
    curriculum: str,
    school_level: str,
    grade: str,
    subject: str,
    unit_names: str,
) -> tuple[list[AchievementStandard], str]:
    """STAS에서 공식 성취기준을 조회하고, 출처 메모를 함께 반환한다."""
    cur_code = CURRICULUM_CODE.get(curriculum.strip())
    if not cur_code:
        raise CurriculumLookupError(
            "지원하지 않는 교육과정입니다. 2015/2022 개정 교육과정만 가능합니다."
        )

    schl_code = SCHOOL_LEVEL_CODE.get(school_level.strip())
    if not schl_code:
        raise CurriculumLookupError("학교급을 확인해 주세요. (초/중/고등학교)")

    subject_query = subject.strip()
    if not subject_query:
        raise CurriculumLookupError("과목명이 필요합니다.")

    unit_lines = [line.strip(" -\t") for line in unit_names.splitlines() if line.strip()]
    if len(unit_lines) <= 1 and unit_names.strip():
        split_units = [p.strip() for p in re.split(r"[,/|]", unit_names) if p.strip()]
        if len(split_units) > 1:
            unit_lines = split_units
    if not unit_lines:
        unit_lines = [subject_query]

    with httpx.Client(follow_redirects=True, timeout=40.0) as client:
        try:
            grade_groups = _get_json(
                client,
                "/cmn/clsfc/grdGrpList:combo",
                {"sEduCurclmCd": cur_code, "sSchlClsCd": schl_code},
            )
        except Exception as exc:
            raise CurriculumLookupError(f"STAS 학년군 조회 실패: {exc}") from exc

        if isinstance(grade_groups, dict):
            grade_groups = [grade_groups]
        if not isinstance(grade_groups, list) or not grade_groups:
            raise CurriculumLookupError(
                f"STAS에서 학년군 정보를 찾지 못했습니다. ({STAS_MAIN})"
            )

        grade_opt = _first_grade_group(grade_groups, grade)
        assert grade_opt is not None
        grade_code = str(grade_opt["code"])
        grade_name = str(grade_opt.get("name") or grade)

        try:
            courses = _get_json(
                client,
                "/cmn/clsfc/corsList:combo",
                {"sEduCurclmCd": cur_code, "sGrdGrpCd": grade_code},
            )
        except Exception as exc:
            raise CurriculumLookupError(f"STAS 교과 조회 실패: {exc}") from exc

        if not isinstance(courses, list) or not courses:
            raise CurriculumLookupError(
                f"STAS에서 '{school_level}' 교과 목록을 찾지 못했습니다."
            )

        course = _pick_by_name(courses, subject_query)
        if course is None:
            names = ", ".join(str(c.get("name")) for c in courses[:20])
            raise CurriculumLookupError(
                f"STAS에서 과목 '{subject_query}'에 해당하는 교과를 찾지 못했습니다. "
                f"사용 가능한 교과 예: {names}"
            )

        cors_code = str(course["code"])
        cors_name = str(course.get("name") or subject_query)

        collected: list[dict[str, Any]] = []
        page = 0
        total_pages = 1
        while page < total_pages and page < 20:
            try:
                payload = _get_json(
                    client,
                    "/acvmt/acvmtStd/acvmtStdList",
                    {
                        "sEduCurclmCd": cur_code,
                        "sSchlClsCd": schl_code,
                        "sGrdGrpCd": grade_code,
                        "sCorsCd": cors_code,
                        "page": page,
                        "size": 50,
                    },
                )
            except Exception as exc:
                raise CurriculumLookupError(
                    f"STAS 성취기준 목록 조회 실패: {exc}"
                ) from exc

            content = payload.get("content") if isinstance(payload, dict) else None
            if not content:
                break
            collected.extend(content)
            total_pages = int(payload.get("totalPages") or 1)
            page += 1

        if not collected:
            raise CurriculumLookupError(
                f"STAS에서 {curriculum} / {school_level} / {cors_name} 성취기준을 "
                f"찾지 못했습니다. 출처: {STAS_MAIN}"
            )

    standards: list[AchievementStandard] = []
    for row in collected:
        standards.append(
            AchievementStandard(
                code=str(row.get("acvmtStdCd") or "").strip(),
                name=str(row.get("acvmtStdNm") or "").strip(),
                area=str(row.get("corsSbjtClsfcA1Nm") or "").strip(),
                school_level=str(row.get("schlClsNm") or school_level),
                grade_group=str(row.get("grdGrpNm") or grade_name),
                subject=str(row.get("sbjtNm") or cors_name),
                curriculum=str(row.get("eduCurclmNm") or curriculum),
            )
        )

    filtered: list[AchievementStandard] = []
    for unit in unit_lines:
        unit_hits = [
            s
            for s in standards
            if _match_name(s.area, unit)
            or _match_name(s.name, unit)
            or _match_name(s.code, unit)
        ]
        for hit in unit_hits:
            if hit not in filtered:
                filtered.append(hit)

    used = filtered if filtered else standards
    match_note = (
        "대단원명과 영역명이 매칭된 성취기준만 선별했습니다."
        if filtered
        else (
            "대단원명과 직접 매칭된 항목이 없어 해당 과목의 STAS 공식 성취기준 전체를 "
            "제공합니다. 작성 시 사용자가 입력한 대단원에 해당하는 항목만 골라 사용하세요."
        )
    )

    source_note = (
        f"공식 출처\n"
        f"1) KICE 학생평가지원포털(STAS): {STAS_MAIN}\n"
        f"2) 에듀넷·티클리어: {EDUNET_MAIN}\n"
        f"조회 조건: {curriculum} / {school_level} / {grade_name} / {cors_name}\n"
        f"비고: {match_note}\n"
        f"검색 페이지: {STAS_BASE}/acvmt/acvmtStd/acvmtStdList:{schl_code}"
    )
    return used, source_note


def format_standards_for_prompt(
    standards: list[AchievementStandard],
    source_note: str,
) -> str:
    lines = [
        "## 공식 국가성취기준 (임의 생성 금지 - 아래 목록만 사용)",
        source_note,
        "",
        "| 코드 | 영역(단원군) | 성취기준 진술 |",
        "| --- | --- | --- |",
    ]
    for s in standards:
        code = s.code.replace("|", "/")
        area = (s.area or "-").replace("|", "/")
        name = s.name.replace("|", "/")
        lines.append(f"| {code} | {area} | {name} |")

    lines.append("")
    lines.append(
        "위 표의 코드·진술 문구를 변경·창작·혼합하지 말고 그대로 인용하세요. "
        "목록에 없는 성취기준 코드를 절대 만들지 마세요."
    )
    return "\n".join(lines)


def build_official_standards_block(
    curriculum: str,
    school_level: str,
    grade: str,
    subject: str,
    unit_names: str,
) -> str:
    """프롬프트에 넣을 공식 성취기준 블록을 생성한다."""
    standards, source_note = fetch_official_standards(
        curriculum=curriculum,
        school_level=school_level,
        grade=grade,
        subject=subject,
        unit_names=unit_names,
    )
    return format_standards_for_prompt(standards, source_note)
