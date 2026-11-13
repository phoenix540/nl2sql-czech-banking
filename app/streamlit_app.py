"""Interface de démonstration : python -m streamlit run app/streamlit_app.py"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from app.charts import chart_frame, suggest_chart  # noqa: E402

EXAMPLES = [
    "Combien de comptes y a-t-il dans chaque district ?",
    "Quels sont les 10 comptes qui ont le plus de transactions ?",
    "Combien de prêts y a-t-il par statut ?",
    "Quel est le montant total des prêts par district ?",
    "Évolution mensuelle du nombre de transactions",
    "Combien de cartes y a-t-il par type ?",
]
st.set_page_config(page_title="Assistant de requêtage", page_icon="💬", layout="wide")


@st.cache_resource(show_spinner="Connexion à la base et lecture du schéma…")
def get_bot():
    from engine.pipeline import NL2SQL
    return NL2SQL.from_env()


def fmt(v) -> str:
    if isinstance(v, (int, float)):
        s = f"{v:,.0f}" if float(v).is_integer() else f"{v:,.2f}"
        return s.replace(",", " ")
    return str(v)


def describe_chart(df: pd.DataFrame):
    """Décrit l'affichage automatique ; renvoie (description, colonne libellé)."""
    if df.shape == (1, 1):
        return "valeur unique", None
    spec = suggest_chart(df)
    if not spec:
        return None, None
    kind = "courbe" if spec.kind == "line" else "diagramme en barres"
    return f"{kind} de {', '.join(spec.ys)} selon {spec.x}", spec.x


def make_explanation(ans):
    if not ans.ok or ans.df.empty:
        return None, None
    chart, label = describe_chart(ans.df)
    try:
        return bot.explain(ans, chart=chart, label_col=label), None
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)


POINT_ICONS = {"max": "🏆", "min": "📉", "tendance": "📈", "repartition": "🧩",
               "graphique": "👀", "info": "ℹ️"}


def show_explanation(exp, err):
    if exp is None:
        if err:
            st.caption(f"⚠️ Explication indisponible : {err}")
        return
    with st.container(border=True):
        st.markdown("##### 💡 Ce qu'il faut retenir")
        st.markdown(f"**{exp.title}**")
        if exp.highlights:
            cols = st.columns(len(exp.highlights))
            for col, h in zip(cols, exp.highlights):
                col.metric(h.label, h.value, h.delta, help=h.help)
        if exp.points:
            st.markdown("\n".join(f"- {POINT_ICONS.get(k, 'ℹ️')} {t}" for k, t in exp.points))
        st.caption("Explication générée automatiquement à partir des chiffres du résultat. "
                   "Vérifiez les valeurs dans le tableau.")


def render(ans, explanation=None, explain_error=None):
    if ans.impossible:
        st.info(f"Cette question sort du périmètre des données : {ans.impossible}")
        return
    if not ans.ok:
        st.error(f"Je n'ai pas réussi à répondre : {ans.error}")
        if ans.sql:
            st.code(ans.sql, language="sql")
        return

    df: pd.DataFrame = ans.df
    c1, c2, c3 = st.columns(3)
    c1.metric("Lignes", f"{len(df):,}".replace(",", " "))
    c2.metric("Temps", f"{ans.seconds:.1f} s")
    c3.metric("Corrections automatiques", max(len(ans.attempts) - 1, 0))
    if ans.truncated:
        st.warning("Résultat tronqué à la limite d'affichage (MAX_ROWS).")

    st.subheader("Requête SQL générée")
    st.code(ans.sql, language="sql")

    if df.empty:
        st.info("La requête s'est exécutée mais ne renvoie aucune ligne.")
        return
    st.subheader("Résultat")
    if df.shape == (1, 1):
        st.metric(str(df.columns[0]), fmt(df.iat[0, 0]))
        show_explanation(explanation, explain_error)
    else:
        mode = st.radio("Affichage", ["Auto", "Tableau seul", "Barres", "Lignes"], horizontal=True)
        force = {"Barres": "bar", "Lignes": "line"}.get(mode)
        spec = None if mode == "Tableau seul" else suggest_chart(df, force)
        if spec:
            frame = chart_frame(df, spec)
            (st.line_chart if spec.kind == "line" else st.bar_chart)(frame)
        elif mode in ("Barres", "Lignes"):
            st.caption("Pas de graphique possible pour ce résultat.")
        st.dataframe(df, hide_index=True)
        show_explanation(explanation, explain_error)
        st.download_button("Télécharger en CSV", df.to_csv(index=False).encode("utf-8-sig"),
                           "resultat.csv", "text/csv")

    if len(ans.attempts) > 1:
        with st.expander("Corrections effectuées par le moteur"):
            for i, a in enumerate(ans.attempts[:-1], 1):
                st.markdown(f"**Tentative {i}** — erreur : `{a['error']}`")
                st.code(a["sql"], language="sql")


# ----------------------------------------------------------------- page
st.title("Assistant intelligent de requêtage en langage naturel")
st.caption("BNS Engineering : posez une question sur vos données, sans écrire de SQL.")

try:
    bot = get_bot()
except Exception as exc:  # noqa: BLE001
    st.error(f"Initialisation impossible : {exc}")
    st.markdown("Vérifie que **PostgreSQL tourne** (`docker compose ps`) et que "
                "`GROQ_API_KEY` est renseignée dans `.env`.")
    st.stop()

st.session_state.setdefault("q", "")
st.session_state.setdefault("history", [])

with st.sidebar:
    st.header("Exemples")
    for ex in EXAMPLES:
        st.button(ex, key=f"ex_{ex}", on_click=lambda e=ex: st.session_state.update(q=e, go=True))
    st.divider()
    st.toggle("Expliquer les résultats", value=True, key="do_explain",
              help="Ajoute une explication en langage naturel (un appel Groq de plus).")
    st.caption(f"Modèle : `{bot.llm.model}`")
    st.caption(f"Sécurité : {getattr(bot, 'security_mode', 'n/a')}")
    with st.expander("Schéma envoyé au modèle"):
        st.code(bot.schema_text, language="text")
    if st.session_state["history"]:
        with st.expander("Historique de la session"):
            for q, ok in reversed(st.session_state["history"]):
                st.write(("✅ " if ok else "❌ ") + q)

question = st.text_input("Votre question", key="q",
                         placeholder="Ex. : Montant total encaissé par banque ce mois-ci")
clicked = st.button("Interroger", type="primary")
if (clicked or st.session_state.pop("go", False)) and question.strip():
    with st.spinner("Génération et exécution de la requête…"):
        ans = bot.ask(question.strip())
    explanation = explain_error = None
    if st.session_state.get("do_explain", True):
        with st.spinner("Rédaction de l'explication…"):
            explanation, explain_error = make_explanation(ans)
    st.session_state["history"].append((question.strip(), ans.ok))
    st.session_state["last"] = (ans, explanation, explain_error)

# Le dernier résultat reste affiché quand on change le mode d'affichage (rerun Streamlit).
if st.session_state.get("last"):
    render(*st.session_state["last"])
