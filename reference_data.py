"""
Données de référence pour le formulaire d'évaluation
Prix d'Excellence - Meilleure Secrétaire CNPS
"""
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ------------------------------------------------------------------
# Q1 : Site de la visite -> sous-menu dépendant
# ------------------------------------------------------------------
STRUCTURES = {
    "Siege": [
        "DRH", "DG", "DP", "DJC", "APEX", "DPPSST", "DCM", "DPM",
        "DPRES", "DQE", "DSI", "DIF", "DREC", "DMC", "CA", "DCF",
        "IM2S", "CARF", "DAI", "MA-CNPS",
    ],
    "APS Abidjan": [
        "APS Plateau", "APS Adjame", "APS Cocody", "APS Abobo",
        "APS Yopougon", "APS Koumassi", "APS Treichville", "APS Bingerville",
        "Controle Medical Cocody", "Controle Medical Yopougon",
        "Controle Medical Koumassi", "Controle Medical Treichville",
        "Controle Medical Adjame",
    ],
    "APS Province": [
        "APS Yamoussoukro", "APS Bonoua", "APS Agboville", "APS San-Pedro",
        "APS Divo", "APS Korhogo", "APS Gagnoa", "APS Abengourou",
        "APS Daloa", "APS Bouake", "APS Man", "APS Daoukro",
        "APS Adzope", "APS Odienne", "APS Bondoukou",
        "Controle Medical Bouake",
    ],
}

SITES = ["Siege CNPS", "APS Abidjan", "APS Province"]


# ------------------------------------------------------------------
# Q2 : Liste complète des agents (nom + poste), choix multiples
# ------------------------------------------------------------------
def get_agents():
    with open(os.path.join(BASE_DIR, "data", "agents.json"), encoding="utf-8") as f:
        return json.load(f)


# ------------------------------------------------------------------
# Échelle de notation utilisée pour les questions notées 1 à 5
# ------------------------------------------------------------------
ECHELLE = [
    (1, "Pas du tout"),
    (2, "Plutôt non"),
    (3, "Moyennement"),
    (4, "Plutôt oui"),
    (5, "Tout à fait"),
]
