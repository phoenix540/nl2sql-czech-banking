from datetime import date

import pandas as pd

from engine.explain import build_messages, explain, highlights, parse, summarize


def test_summarize_reports_max_min_with_labels():
    df = pd.DataFrame({"district_name": ["A", "B", "C", "D"], "account_count": [10, 554, 3, 33]})
    text = summarize(df)
    assert "4 ligne(s)" in text
    assert "total 600" in text
    assert "max 554 (B)" in text
    assert "min 3 (C)" in text
    assert "les 3 plus grandes valeurs" in text


def test_summarize_time_series_gives_evolution():
    df = pd.DataFrame({"month": [date(1993, 2, 1), date(1993, 1, 1)], "n": [20, 5]})
    text = summarize(df, label_col="month")
    assert "évolution de n : 5 au 1993-01-01 -> 20 au 1993-02-01" in text


def test_summarize_ignores_id_columns_and_samples_long_results():
    df = pd.DataFrame({"account_id": range(40), "amount": [1.5] * 40})
    text = summarize(df)
    assert "- account_id" not in text
    assert "Premières 15 lignes (échantillon)" in text


def test_build_messages_mentions_chart_and_truncation():
    df = pd.DataFrame({"x": ["a", "b"], "y": [1, 2]})
    user = build_messages("Q ?", "SELECT 1", df, chart="diagramme en barres", truncated=True)[1]["content"]
    assert "diagramme en barres" in user and "tronqué" in user


def test_parse_reads_json_and_normalises_types():
    raw = ('ok ```json\n{"titre": "B domine.", "points": [{"type": "MAX", "texte": "B : 554."},'
           ' {"type": "bizarre", "texte": "Autre."}, {"type": "min", "texte": " "}]}\n```')
    exp = parse(raw)
    assert exp.title == "B domine."
    assert exp.points == [("max", "B : 554."), ("info", "Autre.")]


def test_parse_falls_back_to_plain_text():
    exp = parse("Première phrase. Deuxième phrase !")
    assert exp.title == "Première phrase."
    assert exp.points == [("info", "Deuxième phrase !")]


def test_highlights_categorical_and_time_series():
    cat = highlights(pd.DataFrame({"type": ["classic", "gold", "junior"], "nb_cartes": [659, 88, 145]}))
    assert [(h.label, h.value) for h in cat] == [
        ("Total", "892"), ("Plus élevé : classic", "659"), ("Plus faible : gold", "88")]

    ts = highlights(pd.DataFrame({"mois": [date(1993, 1, 1), date(1993, 2, 1)], "n": [100, 150]}))
    assert ts[1].value == "150" and ts[1].delta == "+50 % depuis le début"
    assert highlights(pd.DataFrame({"n": [5]})) == []

    big = highlights(pd.DataFrame({"mois": [date(1993, 1, 1), date(1998, 1, 1)], "n": [177, 23553]}))
    assert big[1].delta == "× 133 depuis le début"


def test_summarize_flags_irregular_series_and_drop_after_peak():
    df = pd.DataFrame({"mois": [date(1993, m, 1) for m in (1, 2, 3, 4)], "n": [10, 30, 20, 15]})
    text = summarize(df, label_col="mois")
    assert "1 hausses et 2 baisses" in text
    assert "après le pic du 1993-02-01 (30), la valeur redescend à 15" in text


def test_explain_returns_structured_explanation():
    class FakeLLM:
        def chat(self, messages):
            self.messages = messages
            return '<think>calcul</think>{"titre": "B concentre la majorité.", "points": []}'

    llm = FakeLLM()
    df = pd.DataFrame({"x": ["a", "b"], "y": [1, 2]})
    exp = explain(llm, "Q ?", "SELECT 1", df)
    assert exp.title == "B concentre la majorité."
    assert [h.label for h in exp.highlights] == ["Total", "Plus élevé : b", "Plus faible : a"]
    assert llm.messages[0]["role"] == "system"
