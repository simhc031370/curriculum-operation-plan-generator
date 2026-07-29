export type SchoolLevel = "초등학교" | "중학교" | "고등학교";

export type Curriculum =
  | "2015 개정 교육과정"
  | "2022 개정 교육과정";

export const SCHOOL_LEVELS: SchoolLevel[] = ["초등학교", "중학교", "고등학교"];

export const CURRICULUMS: Curriculum[] = [
  "2015 개정 교육과정",
  "2022 개정 교육과정",
];

export const GRADES_BY_LEVEL: Record<SchoolLevel, string[]> = {
  초등학교: ["1학년", "2학년", "3학년", "4학년", "5학년", "6학년"],
  중학교: ["1학년", "2학년", "3학년"],
  고등학교: ["1학년", "2학년", "3학년"],
};

export const DEFAULT_TOTAL_HOURS = 17;
export const DEFAULT_CURRICULUM: Curriculum = "2022 개정 교육과정";
