/**
 * LLM 응답에 섞인 HTML·깨진 표기를 마크다운 렌더링에 맞게 정리한다.
 */
export function sanitizeMarkdown(raw: string): string {
  let text = raw ?? "";

  // 코드펜스 안의 html 래퍼 제거
  text = text.replace(/^```(?:html|markdown|md)?\s*/i, "");
  text = text.replace(/\s*```$/i, "");

  // 줄바꿈·공백 HTML → 마크다운
  text = text.replace(/<br\s*\/?>/gi, "\n");
  text = text.replace(/<\/\s*p\s*>/gi, "\n\n");
  text = text.replace(/<\s*p\s*[^>]*>/gi, "");
  text = text.replace(/<\/\s*div\s*>/gi, "\n");
  text = text.replace(/<\s*div\s*[^>]*>/gi, "");
  text = text.replace(/<\/\s*li\s*>/gi, "\n");
  text = text.replace(/<\s*li\s*[^>]*>/gi, "- ");
  text = text.replace(/<\/?\s*(ul|ol)\s*>/gi, "\n");
  text = text.replace(/<\/?\s*(strong|b)\s*>/gi, "**");
  text = text.replace(/<\/?\s*(em|i)\s*>/gi, "*");

  // 엔티티
  text = text
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/&quot;/gi, '"')
    .replace(/&#39;/g, "'")
    .replace(/&mdash;/gi, "—")
    .replace(/&ndash;/gi, "–");

  // 남은 HTML 태그 제거 (내용은 유지)
  text = text.replace(/<\/?[a-zA-Z][^>]*>/g, "");

  // 표 셀 안의 과도한 공백 정리
  text = text.replace(/[ \t]+\n/g, "\n");
  text = text.replace(/\n{4,}/g, "\n\n\n");

  // 플레이스홀더성 문구 완화 표시는 프롬프트에서 막고, 여기선 흔한 잔여물만 제거
  text = text.replace(/\[(?:작성|기입|입력|TODO|TBD)[^\]]*\]/gi, "");

  return text.trim();
}
