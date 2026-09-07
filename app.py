#!/usr/bin/env python3
"""
Funeral Calendar - servizio web
Mostra i necrologi di oggi per Città di Castello (incl. Trestina), Umbertide
e San Giustino. Aggiorna i dati al massimo una volta al giorno (cache su
disco) invece di scaricare la pagina a ogni visita.
"""
import calendar
import json
import time
from datetime import datetime
from pathlib import Path

import requests
from flask import Flask, redirect, render_template, url_for

import funeral_party as fp

MESI_IT = [
    "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
    "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre",
]

app = Flask(__name__)

CACHE_FILE = Path(__file__).resolve().parent / "cache.json"
CACHE_TTL_SECONDI = 3 * 3600  # riscarica al massimo ogni 3 ore


def carica_cache():
    if not CACHE_FILE.exists():
        return None
    try:
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def salva_cache(dati):
    CACHE_FILE.write_text(json.dumps(dati, ensure_ascii=False, indent=2), encoding="utf-8")


def raccogli_dati():
    """Scarica i necrologi di ogni località. Non solleva eccezioni: gli
    errori per singola località finiscono nel campo 'errore' di quel blocco.

    Ritorna sia i necrologi di oggi (con foto e agenzia, per la home) sia
    l'elenco completo di quelli ancora presenti in pagina sul sito sorgente
    (senza foto/agenzia, per non moltiplicare le richieste), usato per la
    vista calendario.
    """
    risultati = []
    tutti = []
    for nome_localita, url in fp.LOCALITA.items():
        slug = url.rstrip("/").split("/")[-1]
        try:
            necrologi = fp.scarica_necrologi(url, slug)
            for n in necrologi:
                tutti.append({"nome": n["nome"], "data": n["data"], "link": n["link"], "localita": nome_localita})

            di_oggi, data_oggi = fp.filtra_oggi(necrologi)
            for n in di_oggi:
                try:
                    dettagli = fp.ottieni_dettagli(n["link"])
                    n["foto"] = dettagli["foto"]
                    n["agenzia"] = dettagli["agenzia"]
                except (requests.RequestException, RuntimeError):
                    n["foto"] = None
                    n["agenzia"] = None
            risultati.append({
                "localita": nome_localita,
                "data_oggi": data_oggi,
                "necrologi": di_oggi,
                "errore": None,
            })
        except (requests.RequestException, RuntimeError) as e:
            risultati.append({
                "localita": nome_localita,
                "data_oggi": None,
                "necrologi": [],
                "errore": str(e),
            })
    return {
        "timestamp": time.time(),
        "generato_il": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "risultati": risultati,
        "tutti": tutti,
    }


def ottieni_dati(forza=False):
    cache = carica_cache()
    if not forza and cache and (time.time() - cache["timestamp"] < CACHE_TTL_SECONDI):
        return cache
    dati = raccogli_dati()
    salva_cache(dati)
    return dati


def costruisci_calendario(tutti, anno):
    """Raggruppa i necrologi (di qualunque delle 3 località) per giorno e
    costruisce la griglia dei 12 mesi dell'anno indicato. Ogni mese è una
    lista di settimane, ogni settimana una lista di 7 celle {giorno, voci}
    (giorno None per le celle fuori mese, come restituite da calendar.Calendar).
    """
    per_giorno = {}
    for n in tutti:
        if not n["data"] or not n["data"].endswith(f"/{anno}"):
            continue
        per_giorno.setdefault(n["data"], []).append(n)

    cal = calendar.Calendar(firstweekday=0)  # lunedì
    mesi = []
    for mese in range(1, 13):
        settimane = []
        for settimana in cal.monthdayscalendar(anno, mese):
            celle = []
            for giorno in settimana:
                if giorno == 0:
                    celle.append({"giorno": None, "voci": []})
                else:
                    data_str = f"{giorno:02d}/{mese:02d}/{anno}"
                    celle.append({"giorno": giorno, "voci": per_giorno.get(data_str, [])})
            settimane.append(celle)
        mesi.append({"nome": MESI_IT[mese - 1], "numero": mese, "settimane": settimane})
    return mesi


@app.route("/")
def home():
    dati = ottieni_dati()
    return render_template("index.html", dati=dati)


@app.route("/calendario")
def calendario():
    dati = ottieni_dati()
    anno = 2026
    mesi = costruisci_calendario(dati.get("tutti", []), anno)
    oggi = datetime.now().strftime("%d/%m/%Y")
    return render_template("calendario.html", mesi=mesi, anno=anno, oggi=oggi, generato_il=dati["generato_il"])


@app.route("/aggiorna")
def aggiorna():
    ottieni_dati(forza=True)
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
