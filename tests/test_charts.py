import json
from datetime import date, datetime, time, timedelta
from urllib.parse import parse_qs, urlparse

from studypilot.charts import balance_chart, chart_url, course_hours_chart, week_hours_chart
from studypilot.models import Item, Plan, Session

TODAY = date(2026, 11, 21)


def _realistic_plan():
    items = [
        Item(
            f"Assignment {course}",
            TODAY + timedelta(days=30 + index),
            course=course,
            notion_id=f"item-{index}",
        )
        for index, course in enumerate(("CS 101", "MAT 216", "ENG 201", "BIO 110"))
    ]
    sessions = []
    for index in range(127):
        day = TODAY + timedelta(days=index % 28)
        start_time = time(8, 0) if index % 10 == 0 else time(18, index % 2 * 30)
        if index % 10 == 0:
            sessions.append(Session("Walk", datetime.combine(day, start_time), 0.5, kind="Life", label="Walk"))
            continue
        item = items[index % len(items)]
        sessions.append(
            Session(
                item.title,
                datetime.combine(day, start_time),
                1 + index % 3 * 0.25,
                course=item.course,
                item_notion_id=item.notion_id,
            )
        )
    weeks = [
        {
            "start": (TODAY + timedelta(weeks=index)).isoformat(),
            "score": score,
            "label": label,
        }
        for index, (score, label) in enumerate(
            ((82, "Balanced"), (64, "Stretched"), (42, "Burnout risk"), (75, "Balanced"))
        )
    ]
    return items, Plan(sessions=sessions, weeks=weeks)


def _config(url):
    return json.loads(parse_qs(urlparse(url).query)["c"][0])


def test_chart_url_encodes_compact_quickchart_config():
    url = chart_url({"type": "bar", "data": {"labels": ["A"], "datasets": [{"data": [1]}]}}, width=480, height=240)
    assert url.startswith("https://quickchart.io/chart?w=480&h=240&bkg=white&c=")
    assert _config(url)["data"]["labels"] == ["A"]


def test_balance_chart_has_week_labels_score_colors_and_fixed_scale():
    _, plan = _realistic_plan()
    config = _config(balance_chart(plan.weeks))

    assert config["data"]["labels"] == ["Nov 21", "Nov 28", "Dec 5", "Dec 12"]
    dataset = config["data"]["datasets"][0]
    assert dataset["data"] == [82, 64, 42, 75]
    assert dataset["backgroundColor"] == ["#0f7b6c", "#d9730d", "#e03e3e", "#0f7b6c"]
    assert config["options"]["scales"]["yAxes"][0]["ticks"] == {"min": 0, "max": 100}
    assert config["options"]["title"]["text"] == "Balance Score by week"
    assert config["options"]["legend"] == {"display": False}


def test_week_hours_chart_stacks_daily_study_and_life_hours():
    _, plan = _realistic_plan()
    config = _config(week_hours_chart(plan, TODAY))
    datasets = config["data"]["datasets"]

    assert config["data"]["labels"] == ["Sat 21", "Sun 22", "Mon 23", "Tue 24", "Wed 25", "Thu 26", "Fri 27"]
    assert [dataset["label"] for dataset in datasets] == ["Study", "Life"]
    assert [dataset["backgroundColor"] for dataset in datasets] == ["#2383e2", "#0f7b6c"]
    assert config["options"]["scales"]["xAxes"][0]["stacked"] is True
    assert config["options"]["scales"]["yAxes"][0]["stacked"] is True
    for offset in range(7):
        day = TODAY + timedelta(days=offset)
        expected = sum(plan.hours_by_day(kind).get(day, 0) for kind in ("Study", "Life"))
        actual = sum(dataset["data"][offset] for dataset in datasets)
        assert actual == round(expected, 1)


def test_course_chart_aggregates_by_item_course_and_falls_back_to_other():
    items = [Item("Homework 1", TODAY, course="CS 101", notion_id="cs")]
    plan = Plan(
        sessions=[
            Session("Homework 1", datetime.combine(TODAY, time(18)), 1.25, item_notion_id="cs"),
            Session("Homework 1", datetime.combine(TODAY, time(19)), 0.75),
            Session("Unlinked item", datetime.combine(TODAY, time(19)), 0.5),
            Session("Life activity", datetime.combine(TODAY, time(20)), 2, kind="Life"),
        ]
    )
    config = _config(course_hours_chart(plan, items))

    assert config["type"] == "doughnut"
    assert config["data"]["labels"] == ["CS 101", "Other"]
    assert config["data"]["datasets"][0]["data"] == [2.0, 0.5]
    assert config["options"]["title"]["text"] == "Planned study hours by course"


def test_realistic_chart_urls_stay_below_notion_limit():
    items, plan = _realistic_plan()
    urls = [
        balance_chart(plan.weeks),
        week_hours_chart(plan, TODAY),
        course_hours_chart(plan, items),
    ]

    assert len(plan.sessions) == 127
    assert len(urls) == 3
    assert all(len(url) < 1900 for url in urls)
