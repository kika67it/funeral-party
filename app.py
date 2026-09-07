#!/usr/bin/env python3
"""
Funeral Party - servizio web
Mostra i necrologi di oggi per Città di Castello (incl. Trestina), Umbertide
e San Giustino. Aggiorna i dati al massimo una volta al giorno (cache su
disco) invece di scaricare la pagina a ogni visita.
"""
import json
import time
from datetime import datetime
from pathlib import Path

import requests
from flask import Flask, redirect, render_template, url_for

import funeral_party as fp

app = Flask(__name__)

CACHE_FILE = Path(__file__).resolve().parent / "cache.json"
CACHE_TTL_SECONDI = 24 * 3600  # riscarica al massimo una volta al giorno


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
    """Scarica i necrologi di oggi per ogni località. Non solleva eccezioni:
    gli errori per singola località finiscono nel campo 'errore' di quel blocco."""
    risultati = []
    for nome_localita, url in fp.LOCALITA.items():
        slug = url.rstrip("/").split("/")[-1]
        try:
            necrologi = fp.scarica_necrologi(url, slug)
            di_oggi, data_oggi = fp.filtra_oggi(necrologi)
            for n in di_oggi:
                try:
                    n["agenzia"] = fp.ottieni_agenzia(n["link"])
                except (requests.RequestException, RuntimeError):
                    n["agenzia"] = None
            risultati.append({
                "localita": nome_localita,
                "data_oggi": data_oggi,
                "necrologi": di_oggi,
                "errore": None,
                "coordinate": fp.COORDINATE_LOCALITA.get(nome_localita),
            })
        except (requests.RequestException, RuntimeError) as e:
            risultati.append({
                "localita": nome_localita,
                "data_oggi": None,
                "necrologi": [],
                "errore": str(e),
                "coordinate": fp.COORDINATE_LOCALITA.get(nome_localita),
            })
    return {
        "timestamp": time.time(),
        "generato_il": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "risultati": risultati,
    }


def ottieni_dati(forza=False):
    cache = carica_cache()
    if not forza and cache and (time.time() - cache["timestamp"] < CACHE_TTL_SECONDI):
        return cache
    dati = raccogli_dati()
    salva_cache(dati)
    return dati


@app.route("/")
def home():
    dati = ottieni_dati()
    return render_template("index.html", dati=dati)


@app.route("/aggiorna")
def aggiorna():
    ottieni_dati(forza=True)
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
