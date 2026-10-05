"""Generic levels-based marking criteria for the English Language papers.

Written for this platform in our own words (not copied from any exam board's mark scheme).
Each rubric is a list of (level, mark range, descriptor); ranges add up to the question's marks.
Used when importing hand-authored papers (see core/pool.py).
"""
from __future__ import annotations

from core.schemas import LevelDescriptor

Rubric = list[tuple[str, str, str]]

_LIST_FOUR: Rubric = [
    ("Full marks", "4", "Four accurate points, each taken from the lines named in the question and about the focus given."),
    ("Partial", "1-3", "One mark for each accurate point. Quotation or paraphrase is acceptable."),
    ("No credit", "0", "Points from outside the lines named, points about a different focus, or inaccurate statements."),
]

_TRUE_STATEMENTS: Rubric = [
    ("Full marks", "4", "All four true statements chosen and no false statements chosen."),
    ("Partial", "1-3", "One mark for each true statement chosen. Choosing more than four loses the surplus."),
]


def _levels(*rows: tuple[str, str, str]) -> Rubric:
    return list(rows)


_ANALYSIS_8 = _levels(
    ("Level 4", "7-8", "Perceptive, detailed analysis of the writer's methods. Precise subject terminology, well-chosen "
                       "quotations, and an exploration of effects on the reader."),
    ("Level 3", "5-6", "Clear, consistent explanation of the writer's methods. Relevant terminology and quotations "
                       "with some comment on effect."),
    ("Level 2", "3-4", "Some understanding. Methods are identified and quotations are used, but explanation of effect "
                       "is partial or uneven."),
    ("Level 1", "1-2", "Simple awareness of the writer's choices. Little or no terminology and limited use of the text."),
    ("Level 0", "0", "Nothing worthy of credit."),
)

_ANALYSIS_12 = _levels(
    ("Level 4", "10-12", "Perceptive, detailed analysis of how the writer uses language to influence the reader, "
                         "with precise terminology and judicious quotation."),
    ("Level 3", "7-9", "Clear, consistent explanation of language choices and their effects, supported by relevant "
                       "quotations."),
    ("Level 2", "4-6", "Some understanding. Language features are identified with partial explanation of effect."),
    ("Level 1", "1-3", "Simple, general comments on language with little support from the text."),
    ("Level 0", "0", "Nothing worthy of credit."),
)

_EVALUATION_20 = _levels(
    ("Level 4", "16-20", "Perceptive, detailed evaluation. A convincing, critical response to the statement, with "
                         "well-chosen quotations and a thorough exploration of how the writer creates the impressions."),
    ("Level 3", "11-15", "Clear, relevant evaluation. A consistent response to the statement, supported by "
                         "appropriate quotations and comment on the writer's methods."),
    ("Level 2", "6-10", "Some evaluation. An attempt to respond to the statement, with some support from the text and "
                        "limited comment on methods."),
    ("Level 1", "1-5", "Simple, limited opinion with little evidence from the text."),
    ("Level 0", "0", "Nothing worthy of credit."),
)

_SUMMARY_8 = _levels(
    ("Level 4", "7-8", "Perceptive, detailed differences drawn from both sources, with well-supported inferences."),
    ("Level 3", "5-6", "Clear differences from both sources, with relevant inferences and supporting detail."),
    ("Level 2", "3-4", "Some differences identified, with simple inference or uneven use of both sources."),
    ("Level 1", "1-2", "Simple or general differences, with little textual support or reliance on one source."),
    ("Level 0", "0", "Nothing worthy of credit. Comment on language techniques earns no marks on this question."),
)

_COMPARE_16 = _levels(
    ("Level 4", "13-16", "Perceptive, detailed comparison of the writers' attitudes and the methods they use, with "
                         "judicious quotation from both sources."),
    ("Level 3", "9-12", "Clear, consistent comparison of attitudes and methods, supported by relevant quotations."),
    ("Level 2", "5-8", "Some comparison of attitudes, with partial or uneven comment on methods."),
    ("Level 1", "1-4", "Simple comments on one or both texts with little comparison."),
    ("Level 0", "0", "Nothing worthy of credit."),
)

_WRITING_40 = _levels(
    ("Content and organisation, Level 4", "19-24", "Compelling, convincing writing with a clear purpose, ambitious "
                                                  "vocabulary and a controlled, well-sequenced structure."),
    ("Content and organisation, Level 3", "13-18", "Consistent, clear writing that holds the reader's interest, with "
                                                  "varied vocabulary and logical organisation."),
    ("Content and organisation, Level 2", "7-12", "Some success in engaging the reader, with some variety in "
                                                 "vocabulary and a simple structure."),
    ("Content and organisation, Level 1", "1-6", "Limited, simple writing with basic vocabulary and weak organisation."),
    ("Technical accuracy, Level 4", "13-16", "Sentence structures are varied and controlled; spelling and punctuation "
                                            "are accurate, including ambitious vocabulary."),
    ("Technical accuracy, Level 3", "9-12", "Mostly secure sentence demarcation, with generally accurate spelling "
                                           "and punctuation."),
    ("Technical accuracy, Level 2", "5-8", "Some control of sentence structure, with some errors in spelling and "
                                          "punctuation."),
    ("Technical accuracy, Level 1", "1-4", "Limited control. Frequent errors in spelling, punctuation and grammar."),
)

RUBRICS: dict[tuple[str, int], Rubric] = {
    ("gcse_eng_p1", 1): _LIST_FOUR,
    ("gcse_eng_p1", 2): _ANALYSIS_8,
    ("gcse_eng_p1", 3): _ANALYSIS_8,
    ("gcse_eng_p1", 4): _EVALUATION_20,
    ("gcse_eng_p1", 5): _WRITING_40,
    ("gcse_eng_p2", 1): _TRUE_STATEMENTS,
    ("gcse_eng_p2", 2): _SUMMARY_8,
    ("gcse_eng_p2", 3): _ANALYSIS_12,
    ("gcse_eng_p2", 4): _COMPARE_16,
    ("gcse_eng_p2", 5): _WRITING_40,
}


def criteria_for(paper_key: str, number: int) -> list[LevelDescriptor]:
    return [LevelDescriptor(level=lv, marks=m, descriptor=d) for lv, m, d in RUBRICS.get((paper_key, number), [])]
