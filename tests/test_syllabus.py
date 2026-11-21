from datetime import date
from pathlib import Path

from studypilot.syllabus import classify, detect_course, parse_syllabus

SAMPLE = (Path(__file__).parent.parent / "examples" / "cs101_syllabus.txt").read_text()


def test_extracts_all_deadlines():
    items = parse_syllabus(SAMPLE, year=2026)
    by_title = {i.title: i for i in items}
    assert by_title["Midterm Exam"].due == date(2026, 10, 14)
    assert by_title["Midterm Exam"].type == "Exam"
    assert by_title["Quiz 1"].due == date(2026, 9, 15)
    assert by_title["Problem Set 2"].due == date(2026, 9, 26)
    assert by_title["Lab 2: Loops and lists"].due == date(2026, 9, 18)
    assert by_title["Final Exam"].due == date(2026, 12, 10)
    assert all(i.course == "CS 101" for i in items)
    assert [i.due for i in items] == sorted(i.due for i in items)


def test_skips_lines_without_deadline_words():
    items = parse_syllabus(SAMPLE, year=2026)
    assert not any("Course intro" in i.title for i in items)


def test_term_start_rolls_year_forward():
    items = parse_syllabus("Final exam Jan 12", year=2026, term_start=date(2026, 9, 1))
    assert items[0].due == date(2027, 1, 12)


def test_classify_and_course():
    assert classify("Midterm on Oct 3") == "Exam"
    assert classify("Read chapter 4") == "Reading"
    assert classify("Group project demo") == "Project"
    assert detect_course("MATH-221 Linear Algebra") == "MATH 221"


def test_formats():
    text = "HW 3 due 2026-11-03\nQuiz 4 on 3rd December\nEssay due Tue, Nov 17"
    due = {i.title: i.due for i in parse_syllabus(text, year=2026, course="")}
    assert due == {"HW 3": date(2026, 11, 3), "Quiz 4": date(2026, 12, 3), "Essay": date(2026, 11, 17)}


def test_final_project_is_project():
    assert classify("Final Project presentation - Dec 2") == "Project"
    assert classify("Final Exam on December 10") == "Exam"
