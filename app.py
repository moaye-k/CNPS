import os
import csv
import io
import datetime
from flask import Flask, Response, render_template, request, session, redirect, url_for
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

CSV_HEADERS = [
    "date_soumission", "site", "structure", "agents_evalues", "moment_journee",
    "q4_salutation", "q5_courtoisie", "q6_apparence",
    "q7_disponibilite", "q8_comprehension", "q9_ecoute", "q10_reformulation",
    "q11_orientation", "q12_efficacite", "q13_prise_conge",
    "q14_satisfaction_globale", "q15_facilite", "q16_recommandation",
    "q17_positif", "q18_amelioration", "q19_encouragement",
]


def save_response(data: dict):
    os.makedirs(DATA_DIR, exist_ok=True)
    file_exists = os.path.isfile(RESPONSES_FILE)
    with open(RESPONSES_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(data)


# ----------------------------------------------------------------
# Étape 0 : Accueil
# ----------------------------------------------------------------
@app.route("/")
def home():
    session.clear()
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
                            step=2, total_steps=5, next_url=url_for("etape2"))


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
                            step=3, total_steps=5, next_url=url_for("etape3"))


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
                            step=4, total_steps=5, next_url=url_for("etape4"))


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

    return render_template("etape5.html", echelle=ECHELLE, step=5, total_steps=5)


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
    filtered_rows = [row for row in rows if not selected_site or row.get("site") == selected_site]
    filtered_rows.sort(key=lambda row: row.get("date_soumission", ""), reverse=True)

    if request.args.get("format") == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=CSV_HEADERS)
        writer.writeheader()
        writer.writerows(filtered_rows)
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=reponses_cnps.csv"},
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
        positive_recommendations = sum(value.startswith("Oui") for value in recommendations)
        average_score = round(sum(scores) / len(scores), 1) if scores else 0
        recommendation_rate = round(positive_recommendations / len(recommendations) * 100) if recommendations else 0
        scope = selected_site or "Tous les sites"
        story = [
            Paragraph("Réponses collectées — Prix d'excellence CNPS", title_style),
            Paragraph(f"Filtre : {scope} | Réponses : {len(filtered_rows)} | Note moyenne : {average_score}/5 | Recommandation : {recommendation_rate}%", body_style),
            Spacer(1, 8),
        ]
        table_data = [["Date", "Site", "Agent(s) évalué(s)", "Structure", "Satisfaction", "Recommandation"]]
        for row in filtered_rows:
            table_data.append([
                row.get("date_soumission", "")[:10],
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
    positive_recommendations = sum(value.startswith("Oui") for value in recommendations)
    average_score = round(sum(scores) / len(scores), 1) if scores else 0
    recommendation_rate = round(positive_recommendations / len(recommendations) * 100) if recommendations else 0

    return render_template(
        "admin.html",
        rows=filtered_rows[:5],
        headers=CSV_HEADERS,
        sites=SITES,
        selected_site=selected_site,
        total_count=len(filtered_rows),
        average_score=average_score,
        recommendation_rate=recommendation_rate,
    )


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
