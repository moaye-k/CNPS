import os
import csv
import io
import datetime
import uuid
from flask import Flask, Response, render_template, request, session, redirect, url_for
from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from reference_data import STRUCTURES, SITES, get_agents, ECHELLE

app = Flask(__name__, static_folder="ASSET", static_url_path="/assets")
app.secret_key = os.environ.get("SECRET_KEY", "change-moi-en-production")

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
RESPONSES_FILE = os.path.join(DATA_DIR, "reponses.csv")
VISITORS_FILE = os.path.join(DATA_DIR, "visitors.txt")

CSV_HEADERS = [
    "date_soumission", "site", "structure", "agents_evalues", "moment_journee",
    "q4_salutation", "q5_courtoisie", "q6_apparence",
    "q7_disponibilite", "q8_comprehension", "q9_ecoute", "q10_reformulation",
    "q11_orientation", "q12_efficacite", "q13_prise_conge",
    "q14_satisfaction_globale", "q15_facilite", "q16_recommandation",
    "q17_positif", "q18_amelioration", "q19_encouragement",
]

RATING_FIELDS = [
    "q4_salutation", "q5_courtoisie", "q6_apparence",
    "q7_disponibilite", "q8_comprehension", "q9_ecoute",
    "q10_reformulation", "q11_orientation", "q12_efficacite",
    "q13_prise_conge", "q14_satisfaction_globale", "q15_facilite",
]


def _normalize_score_0_100(value):
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0
    return max(0, min(100, (numeric / 5) * 100))


def _normalize_recommendation_score(value):
    if value is None:
        return 0

    try:
        numeric = float(value)
        if 0 <= numeric <= 10:
            return max(0, min(100, (numeric / 10) * 100))
    except (TypeError, ValueError):
        pass

    normalized = str(value).strip().lower()
    mapping = {
        "oui, tout à fait": 100,
        "oui, tout a fait": 100,
        "plutôt oui": 75,
        "plutot oui": 75,
        "neutre": 50,
        "insatisfait": 25,
        "pas du tout": 0,
        "non, pas vraiment": 25,
        "non": 25,
    }
    return mapping.get(normalized, 50)


def _is_positive_recommendation(value):
    try:
        return float(value) >= 9
    except (TypeError, ValueError):
        return str(value).strip().lower() in {
            "oui, tout à fait", "oui, tout a fait", "très satisfait",
        }


def get_response_score(row):
    scores = []
    if str(row.get("q14_satisfaction_globale", "")).strip():
        scores.append(_normalize_score_0_100(row.get("q14_satisfaction_globale")))
    if str(row.get("q15_facilite", "")).strip():
        scores.append(_normalize_score_0_100(row.get("q15_facilite")))
    if str(row.get("q16_recommandation", "")).strip():
        scores.append(_normalize_recommendation_score(row.get("q16_recommandation")))
    return round(sum(scores) / len(scores), 1) if scores else 0


def get_ranked_agents(rows, limit=5):
    agent_stats = {}

    for row in rows:
        agents = [agent.strip() for agent in row.get("agents_evalues", "").split(";") if agent.strip()]
        if not agents:
            continue

        has_score = any(str(row.get(field, "")).strip() for field in (
            "q14_satisfaction_globale", "q15_facilite", "q16_recommandation"
        ))
        if not has_score:
            continue
        composite = get_response_score(row)
        for agent in agents:
            stats = agent_stats.setdefault(agent, {"total_score": 0, "responses": 0})
            stats["total_score"] += composite
            stats["responses"] += 1

    ranked = []
    for agent, stats in agent_stats.items():
        score = round(stats["total_score"] / stats["responses"], 1)
        ranked.append({"agent": agent, "score": score})

    ranked.sort(key=lambda item: item["score"], reverse=True)
    return ranked[:limit]


def get_best_agent(rows):
    ranked = get_ranked_agents(rows, limit=1)
    if not ranked:
        return None
    best = ranked[0]
    return {"agent": best["agent"], "score": best["score"], "recommendation_rate": 0}


def get_agent_rank_label(agent_name, agent_rank_map):
    if not agent_name:
        return "Non renseigné"
    names = [name.strip() for name in str(agent_name).split(";") if name.strip()]
    if not names:
        return "Non renseigné"
    labels = []
    for name in names:
        ranking = agent_rank_map.get(name)
        if ranking:
            labels.append(f"{ranking['rank']} — {name} — Moyenne : {ranking['score']}/100")
        else:
            labels.append(name)
    return "; ".join(labels)


app.jinja_env.globals['get_agent_rank_label'] = get_agent_rank_label


def save_response(data: dict):
    os.makedirs(DATA_DIR, exist_ok=True)
    file_exists = os.path.isfile(RESPONSES_FILE)
    with open(RESPONSES_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(data)


def record_visit():
    visitor_id = session.get("visitor_id") or str(uuid.uuid4())
    os.makedirs(DATA_DIR, exist_ok=True)
    if not session.get("visitor_id"):
        with open(VISITORS_FILE, "a", encoding="utf-8") as f:
            f.write(f"{visitor_id}\n")
    return visitor_id


def get_visitor_count():
    if not os.path.isfile(VISITORS_FILE):
        return 0
    with open(VISITORS_FILE, encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


# ----------------------------------------------------------------
# Étape 0 : Accueil
# ----------------------------------------------------------------
@app.route("/health")
def health():
    return {"status": "ok"}, 200


@app.route("/")
@app.route("/prix-excellence-cnps")
def home():
    visitor_id = record_visit()
    session.clear()
    session["visitor_id"] = visitor_id
    return render_template("home.html")


# ----------------------------------------------------------------
# Étape 1 : Section A - Contexte (Q1, Q2, Q3)
# ----------------------------------------------------------------
@app.route("/etape1", methods=["GET", "POST"])
def etape1():
    if request.method == "POST":
        session["site"] = request.form.get("site")
        session["structure"] = request.form.get("structure")
        session["agents_evalues"] = request.form.getlist("agents")
        session["moment_journee"] = request.form.get("moment_journee")
        return redirect(url_for("etape2"))

    return render_template(
        "etape1.html",
        sites=SITES,
        structures_json=STRUCTURES,
        agents=get_agents(),
        step=1, total_steps=5,
    )


# ----------------------------------------------------------------
# Étape 2 : Section B - Accueil et apparence (Q4, Q5, Q6)
# ----------------------------------------------------------------
@app.route("/etape2", methods=["GET", "POST"])
def etape2():
    if "site" not in session:
        return redirect(url_for("etape1"))

    if request.method == "POST":
        session["q4_salutation"] = request.form.get("q4")
        session["q5_courtoisie"] = request.form.get("q5")
        session["q6_apparence"] = request.form.get("q6")
        return redirect(url_for("etape3"))

    questions = [
        ("q4", "L'agent vous a précédé(e) dans la salutation, avec le sourire."),
        ("q5", "L'agent s'est montré(e) courtois(e) et respectueux(se) tout au long de l'échange."),
        ("q6", "La présentation de l'agent était propre et soignée (tenue, coiffure, hygiène générale)."),
    ]
    return render_template("notation.html", questions=questions, echelle=ECHELLE,
                            section="Section B — Accueil et apparence",
                            step=2, total_steps=5, next_url=url_for("etape2"),
                            previous_url=url_for("etape1"))


# ----------------------------------------------------------------
# Étape 3 : Section C - Disponibilité et écoute (Q7 à Q10)
# ----------------------------------------------------------------
@app.route("/etape3", methods=["GET", "POST"])
def etape3():
    if "site" not in session:
        return redirect(url_for("etape1"))

    if request.method == "POST":
        session["q7_disponibilite"] = request.form.get("q7")
        session["q8_comprehension"] = request.form.get("q8")
        session["q9_ecoute"] = request.form.get("q9")
        session["q10_reformulation"] = request.form.get("q10")
        return redirect(url_for("etape4"))

    questions = [
        ("q7", "L'agent s'est rendu(e) pleinement disponible pour vous, sans vous expédier."),
        ("q8", "L'agent a pris le temps de bien comprendre votre demande."),
        ("q9", "L'agent vous a écouté(e) sans vous interrompre, en montrant de l'intérêt."),
        ("q10", "L'agent a reformulé votre demande pour s'assurer de l'avoir bien comprise."),
    ]
    return render_template("notation.html", questions=questions, echelle=ECHELLE,
                            section="Section C — Disponibilité et écoute",
                            step=3, total_steps=5, next_url=url_for("etape3"),
                            previous_url=url_for("etape2"))


# ----------------------------------------------------------------
# Étape 4 : Section D - Orientation et prise de congé (Q11 à Q13)
# ----------------------------------------------------------------
@app.route("/etape4", methods=["GET", "POST"])
def etape4():
    if "site" not in session:
        return redirect(url_for("etape1"))

    if request.method == "POST":
        session["q11_orientation"] = request.form.get("q11")
        session["q12_efficacite"] = request.form.get("q12")
        session["q13_prise_conge"] = request.form.get("q13")
        return redirect(url_for("etape5"))

    questions = [
        ("q11", "L'agent vous a clairement orienté(e) (borne à tickets, invitation à patienter, information utile)."),
        ("q12", "L'agent a répondu à votre demande ou vous a dirigé(e) efficacement vers la bonne personne."),
        ("q13", "L'agent a pris congé de manière courtoise et personnalisée, avec le sourire."),
    ]
    return render_template("notation.html", questions=questions, echelle=ECHELLE,
                            section="Section D — Orientation et prise de congé",
                            step=4, total_steps=5, next_url=url_for("etape4"),
                            previous_url=url_for("etape3"))


# ----------------------------------------------------------------
# Étape 5 : Section E - Appréciation d'ensemble (Q14 à Q19)
# ----------------------------------------------------------------
@app.route("/etape5", methods=["GET", "POST"])
def etape5():
    if "site" not in session:
        return redirect(url_for("etape1"))

    if request.method == "POST":
        response_data = {
            "date_soumission": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "site": session.get("site", ""),
            "structure": session.get("structure", ""),
            "agents_evalues": "; ".join(session.get("agents_evalues", [])),
            "moment_journee": session.get("moment_journee", ""),
            "q4_salutation": session.get("q4_salutation", ""),
            "q5_courtoisie": session.get("q5_courtoisie", ""),
            "q6_apparence": session.get("q6_apparence", ""),
            "q7_disponibilite": session.get("q7_disponibilite", ""),
            "q8_comprehension": session.get("q8_comprehension", ""),
            "q9_ecoute": session.get("q9_ecoute", ""),
            "q10_reformulation": session.get("q10_reformulation", ""),
            "q11_orientation": session.get("q11_orientation", ""),
            "q12_efficacite": session.get("q12_efficacite", ""),
            "q13_prise_conge": session.get("q13_prise_conge", ""),
            "q14_satisfaction_globale": request.form.get("q14", ""),
            "q15_facilite": request.form.get("q15", ""),
            "q16_recommandation": request.form.get("q16", ""),
            "q17_positif": request.form.get("q17", ""),
            "q18_amelioration": request.form.get("q18", ""),
            "q19_encouragement": request.form.get("q19", ""),
        }
        save_response(response_data)
        session.clear()
        return redirect(url_for("merci"))

    return render_template("etape5.html", echelle=ECHELLE, step=5, total_steps=5,
                           previous_url=url_for("etape4"))


@app.route("/merci")
def merci():
    return render_template("merci.html")


# ----------------------------------------------------------------
# Espace administrateur simple : voir / exporter les réponses
# ----------------------------------------------------------------
@app.route("/admin/reponses")
def admin_reponses():
    admin_key = request.args.get("cle")
    if admin_key != os.environ.get("ADMIN_KEY", "cnps2026"):
        return "Accès refusé. Ajoutez ?cle=VOTRE_CLE à l'URL.", 403

    rows = []
    if os.path.isfile(RESPONSES_FILE):
        with open(RESPONSES_FILE, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

    selected_site = request.args.get("site", "")
    selected_agent = request.args.get("agent", "")
    filtered_rows = [row for row in rows if not selected_site or row.get("site") == selected_site]
    if selected_agent:
        filtered_rows = [
            row for row in filtered_rows
            if any(
                agent.strip() == selected_agent or agent.strip().startswith(f"{selected_agent} (")
                for agent in row.get("agents_evalues", "").split(";")
            )
        ]
    filtered_rows.sort(
        key=lambda row: (get_response_score(row), row.get("date_soumission", "")),
        reverse=True,
    )

    site_structure_groups = {
        "Siege CNPS": "Siege",
        "APS Abidjan": "APS Abidjan",
        "APS Province": "APS Province",
    }
    selected_structures = STRUCTURES[site_structure_groups[selected_site]] if selected_site in site_structure_groups else None
    available_agents = [
        agent for agent in get_agents()
        if not selected_structures
        or agent.get("structure", "").casefold() in {structure.casefold() for structure in selected_structures}
    ]
    total_site_visitors = get_visitor_count()

    if request.args.get("format") == "xlsx":
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "Réponses"
        worksheet.append(CSV_HEADERS)
        for row in filtered_rows:
            worksheet.append([row.get(header, "") for header in CSV_HEADERS])
        worksheet.freeze_panes = "A2"
        worksheet.auto_filter.ref = worksheet.dimensions
        for column_cells in worksheet.columns:
            width = min(max(max(len(str(cell.value or "")) for cell in column_cells) + 2, 12), 40)
            worksheet.column_dimensions[column_cells[0].column_letter].width = width
        output = io.BytesIO()
        workbook.save(output)
        return Response(
            output.getvalue(),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=reponses_cnps.xlsx"},
        )

    if request.args.get("format") == "pdf":
        output = io.BytesIO()
        document = SimpleDocTemplate(
            output,
            pagesize=landscape(A4),
            rightMargin=12 * mm,
            leftMargin=12 * mm,
            topMargin=12 * mm,
            bottomMargin=12 * mm,
        )
        styles = getSampleStyleSheet()
        title_style = styles["Title"]
        title_style.textColor = colors.HexColor("#0b294b")
        body_style = styles["BodyText"]
        body_style.fontSize = 8
        body_style.leading = 10
        scores = [int(row["q14_satisfaction_globale"]) for row in filtered_rows if row.get("q14_satisfaction_globale", "").isdigit()]
        recommendations = [row.get("q16_recommandation", "") for row in filtered_rows]
        positive_recommendations = sum(_is_positive_recommendation(value) for value in recommendations)
        average_score = round(sum(scores) / len(scores), 1) if scores else 0
        recommendation_rate = round(positive_recommendations / len(recommendations) * 100) if recommendations else 0
        scope = selected_site or "Tous les sites"
        story = [
            Paragraph("Réponses collectées — Prix d'excellence CNPS", title_style),
            Paragraph(f"Filtre : {scope} | Réponses : {len(filtered_rows)} | Note moyenne : {average_score}/5 | Recommandation : {recommendation_rate}%", body_style),
            Spacer(1, 8),
        ]
        table_data = [["Moment de la visite", "Site", "Agent(s) évalué(s)", "Structure", "Satisfaction", "Recommandation"]]
        for row in filtered_rows:
            table_data.append([
            row.get("moment_journee", "") or "-",
                Paragraph(row.get("site", ""), body_style),
                Paragraph(row.get("agents_evalues", "") or "Non renseigné", body_style),
                Paragraph(row.get("structure", ""), body_style),
                f"{row.get('q14_satisfaction_globale', '-')}/5",
                Paragraph(row.get("q16_recommandation", "") or "-", body_style),
            ])
        table = Table(table_data, colWidths=[25 * mm, 34 * mm, 70 * mm, 42 * mm, 28 * mm, 50 * mm], repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0b294b")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 8),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#d9e0e8")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f6f9")]),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(table)
        document.build(story)
        return Response(
            output.getvalue(),
            mimetype="application/pdf",
            headers={"Content-Disposition": "attachment; filename=reponses_cnps.pdf"},
        )

    scores = [int(row["q14_satisfaction_globale"]) for row in filtered_rows if row.get("q14_satisfaction_globale", "").isdigit()]
    recommendations = [row.get("q16_recommandation", "") for row in filtered_rows]
    positive_recommendations = sum(_is_positive_recommendation(value) for value in recommendations)
    average_score = round(sum(scores) / len(scores), 1) if scores else 0
    recommendation_rate = round(positive_recommendations / len(recommendations) * 100) if recommendations else 0
    ranked_agents = get_ranked_agents(filtered_rows, limit=None)
    best_agent = ranked_agents[0] if ranked_agents else None
    agent_rank_map = {}
    for index, item in enumerate(ranked_agents, start=1):
        suffix = "er" if index == 1 else "e"
        agent_rank_map[item["agent"]] = {
            "rank": f"{index}{suffix}",
            "score": item["score"],
        }

    display_rows = []
    for row in filtered_rows[:5]:
        agents = [agent.strip() for agent in row.get("agents_evalues", "").split(";") if agent.strip()]
        for agent in agents or [""]:
            display_row = dict(row)
            display_row["agents_evalues"] = agent
            display_rows.append(display_row)

    return render_template(
        "admin.html",
        rows=display_rows,
        headers=CSV_HEADERS,
        sites=SITES,
        selected_site=selected_site,
        selected_agent=selected_agent,
        available_agents=available_agents,
        total_count=len(filtered_rows),
        average_score=average_score,
        best_agent=best_agent,
        recommendation_rate=recommendation_rate,
        ranked_agents=ranked_agents,
        total_site_visitors=total_site_visitors,
        agent_rank_map=agent_rank_map,
    )


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
