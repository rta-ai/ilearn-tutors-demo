"""Exam format definitions.

These pin the structure (question types, marks, assessment objectives) so the
LLM only writes the *content*. Adding a new board/subject format means adding
a PaperSpec here; no prompt or pipeline changes are needed.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Question types (shared with core.schemas.QuestionType values)
MCQ = "mcq"
TRUE_FALSE = "true_false"
MULTI_SELECT = "multi_select"
SHORT_ANSWER = "short_answer"
EXTENDED = "extended"

OBJECTIVE_TYPES = {MCQ, TRUE_FALSE, MULTI_SELECT}

SECTION_A = "Section A: Reading"
SECTION_B = "Section B: Writing"
FULL_PAPER = "Full paper"

ENGLISH_AOS = {
    "AO1": "Identify and interpret explicit and implicit information and ideas; select and synthesise evidence",
    "AO2": "Explain, comment on and analyse how writers use language and structure to achieve effects",
    "AO3": "Compare writers' ideas and perspectives, and how these are conveyed, across two or more texts",
    "AO4": "Evaluate texts critically and support this with appropriate textual references",
    "AO5": "Communicate clearly, effectively and imaginatively; organise information and ideas",
    "AO6": "Use a range of vocabulary and sentence structures, with accurate spelling and punctuation",
}


# Student-friendly names used in results and weak-area reporting.
AO_LABELS = {
    "AO1": "Finding and selecting information (AO1)",
    "AO2": "Analysing language and structure (AO2)",
    "AO3": "Comparing writers' ideas and methods (AO3)",
    "AO4": "Evaluating texts critically (AO4)",
    "AO5/AO6": "Writing: content, organisation and accuracy (AO5/AO6)",
}


@dataclass(frozen=True)
class QuestionSpec:
    number: int
    section: str
    qtype: str
    marks: int
    ao: str
    pattern: str  # the real exam's question stem pattern
    guidance: str  # what the generator must do for this question


@dataclass(frozen=True)
class PaperSpec:
    key: str
    subject: str
    title: str
    duration_minutes: int
    num_sources: int  # source extracts printed in the insert booklet
    questions: tuple[QuestionSpec, ...]
    retrieval_queries: tuple[str, ...]
    assessment_objectives: dict[str, str] = field(default_factory=dict)
    original_sources: bool = False  # extracts are written fresh, never copied from the reference material
    sections: tuple[str, ...] = (SECTION_A, SECTION_B, FULL_PAPER)

    def questions_for(self, section: str) -> list[QuestionSpec]:
        if section == FULL_PAPER:
            return list(self.questions)
        return [q for q in self.questions if q.section == section]

    def duration_for(self, section: str) -> int:
        if section == FULL_PAPER:
            return self.duration_minutes
        share = sum(q.marks for q in self.questions_for(section)) / sum(q.marks for q in self.questions)
        return max(15, round(self.duration_minutes * share / 5) * 5)


GCSE_ENGLISH_PAPER_1 = PaperSpec(
    key="gcse_eng_p1",
    subject="English Language",
    title="Paper 1: Explorations in Creative Reading and Writing",
    duration_minutes=105,
    num_sources=1,
    original_sources=True,
    assessment_objectives=ENGLISH_AOS,
    retrieval_queries=(
        "fiction extract narrative prose describing a character, setting or event",
        "descriptive language imagery simile metaphor atmosphere",
        "story opening, structure, shift in focus, perspective, tension",
    ),
    questions=(
        QuestionSpec(1, SECTION_A, SHORT_ANSWER, 4, "AO1",
                     "Read again lines X to Y of the source. List four things from this part of the source about [topic].",
                     "Point to a short line range (about 4-8 lines) containing at least six retrievable facts."),
        QuestionSpec(2, SECTION_A, EXTENDED, 8, "AO2",
                     "Look in detail at lines X to Y of the source. How does the writer use language to describe [focus]?",
                     "Pick a language-rich line range. Add the standard bullet prompt: words and phrases, language "
                     "features and techniques, sentence forms."),
        QuestionSpec(3, SECTION_A, EXTENDED, 8, "AO2",
                     "You now need to think about the whole of the source. How has the writer structured the text to interest you as a reader?",
                     "Whole-text structure. Add the bullet prompt: what the writer focuses your attention on at the "
                     "beginning, how and why the writer changes this focus as the source develops, any other "
                     "structural features."),
        QuestionSpec(4, SECTION_A, EXTENDED, 20, "AO4",
                     "Focus on the second part of the source, from line X to the end. A student said, '[statement]'. To what extent do you agree?",
                     "Give a debatable student statement about the second half. Add the bullet prompt: consider your "
                     "own impressions of [focus], evaluate how the writer creates these impressions, support your "
                     "response with references to the text."),
        QuestionSpec(5, SECTION_B, EXTENDED, 40, "AO5 (24 marks), AO6 (16 marks)",
                     "Either: Write a description suggested by [image/scene]. Or: Write the opening part of a story about [theme].",
                     "Offer two choices inspired by the themes, settings or moods of the source material. 24 marks for "
                     "content and organisation, 16 marks for technical accuracy."),
    ),
)

GCSE_ENGLISH_PAPER_2 = PaperSpec(
    key="gcse_eng_p2",
    subject="English Language",
    title="Paper 2: Writers' Viewpoints and Perspectives",
    duration_minutes=105,
    num_sources=2,
    original_sources=True,
    assessment_objectives=ENGLISH_AOS,
    retrieval_queries=(
        "non-fiction article, letter, speech or diary expressing a viewpoint or opinion",
        "writer's attitude, perspective, argument and persuasive language",
        "nineteenth century non-fiction account compared with a modern account",
    ),
    questions=(
        QuestionSpec(1, SECTION_A, MULTI_SELECT, 4, "AO1",
                     "Read again the first part of Source A from lines X to Y. Choose four statements below which are TRUE.",
                     "Put all EIGHT statements in the 'options' list (four true, four false, mixed order), each a "
                     "complete standalone sentence about the line range. question_text must contain ONLY the "
                     "instruction and must NOT repeat the statements. Do not prefix options with letters."),
        QuestionSpec(2, SECTION_A, EXTENDED, 8, "AO1",
                     "You need to refer to Source A and Source B for this question. Write a summary of the differences between [subject] in each source.",
                     "Choose a point of comparison that genuinely differs between the two sources."),
        QuestionSpec(3, SECTION_A, EXTENDED, 12, "AO2",
                     "You now need to refer only to Source B, lines X to Y. How does the writer use language to describe [focus]?",
                     "Pick a language-rich line range in Source B."),
        QuestionSpec(4, SECTION_A, EXTENDED, 16, "AO3",
                     "For this question, you need to refer to the whole of Source A, together with the whole of Source B. Compare how the two writers convey their different attitudes to [subject].",
                     "Add the bullet prompt: compare their different attitudes, compare the methods they use, support "
                     "your response with references to both texts."),
        QuestionSpec(5, SECTION_B, EXTENDED, 40, "AO5 (24 marks), AO6 (16 marks)",
                     "'[Provocative statement]' Write [an article / a letter / a speech / an essay] in which you explain your point of view on this statement.",
                     "The statement must relate to the theme shared by the two sources. State audience/form."),
    ),
)

# Any subject: the LLM chooses question types; marks per type are fixed here.
GENERIC_MARKS = {MCQ: 1, TRUE_FALSE: 1, SHORT_ANSWER: 3, EXTENDED: 6}

GENERIC_TOPIC_TEST = PaperSpec(
    key="topic_test",
    subject="*",
    title="Topic Test",
    duration_minutes=0,  # derived from marks
    num_sources=0,
    retrieval_queries=(
        "key concepts, definitions and facts",
        "explanations of processes, causes and effects",
        "worked examples, case studies and applications",
    ),
    questions=(),
    sections=(),
)

PAPER_SPECS: dict[str, PaperSpec] = {
    s.key: s for s in (GCSE_ENGLISH_PAPER_1, GCSE_ENGLISH_PAPER_2, GENERIC_TOPIC_TEST)
}


def formats_for_subject(subject: str) -> list[PaperSpec]:
    return [s for s in PAPER_SPECS.values() if s.subject in (subject, "*")]


def generic_question_plan(num_questions: int) -> list[tuple[str, int]]:
    """A balanced mix of question types for a topic test, as (qtype, marks)."""
    mix = [MCQ, MCQ, TRUE_FALSE, SHORT_ANSWER, EXTENDED]
    if num_questions >= 10:
        mix = [MCQ, MCQ, MCQ, TRUE_FALSE, TRUE_FALSE, SHORT_ANSWER, SHORT_ANSWER, SHORT_ANSWER, EXTENDED, EXTENDED]
    plan = (mix * (num_questions // len(mix) + 1))[:num_questions]
    return [(q, GENERIC_MARKS[q]) for q in plan]
