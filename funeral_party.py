#!/usr/bin/env python3
"""
Funeral Calendar - Necrologi del giorno, Città di Castello
Fonte: inmemoria.paginebianche.it (aggregatore pubblico di necrologi)

Uso:
    python necrologi_castello.py              -> stampa i necrologi di oggi
    python necrologi_castello.py --tutti       -> stampa tutti quelli presenti in pagina (ultimi giorni)

Dipendenze:
    pip install requests beautifulsoup4
"""

import re
import sys
import time
from datetime import date, datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

FILE_OUTPUT = Path(__file__).resolve().parent / "funeral_party_oggi.txt"

LOCALITA = {
    "Città di Castello (incl. Trestina)": "https://inmemoria.paginebianche.it/necrologi/umbria/citta-di-castello",
    "Umbertide": "https://inmemoria.paginebianche.it/necrologi/umbria/umbertide",
    "San Giustino": "https://inmemoria.paginebianche.it/necrologi/umbria/san-giustino",
}
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}
TENTATIVI = 3
ATTESA_TRA_TENTATIVI_SEC = 5


def _scarica_con_retry(url):
    """GET con retry. Il sito è dietro un WAF che a volte risponde con una
    pagina vuota (202, nessun contenuto) invece della pagina richiesta: è un
    comportamento intermittente lato server, non legato ai parametri della
    richiesta, quindi ritentiamo un paio di volte prima di arrenderci.
    """
    ultimo_errore = None
    for tentativo in range(1, TENTATIVI + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            # Il sito non dichiara il charset nell'header Content-Type, quindi
            # requests userebbe ISO-8859-1 (default HTTP) invece di UTF-8,
            # corrompendo ogni carattere accentato: forziamo UTF-8, che è la
            # codifica reale della pagina.
            resp.encoding = "utf-8"
            if resp.text.strip():
                return resp
            ultimo_errore = "risposta vuota dal server"
        except requests.RequestException as e:
            ultimo_errore = str(e)
        if tentativo < TENTATIVI:
            time.sleep(ATTESA_TRA_TENTATIVI_SEC)
    raise RuntimeError(f"impossibile ottenere la pagina dopo {TENTATIVI} tentativi ({ultimo_errore})")


def scarica_necrologi(url, slug):
    """Scarica e fa il parsing di una pagina necrologi. Ritorna una lista di dict."""
    resp = _scarica_con_retry(url)
    soup = BeautifulSoup(resp.text, "html.parser")

    necrologi = []
    link_visti = set()

    # Ogni necrologio in pagina è un blocco <div class="row media-body"> con:
    # nome in <h3 class="name-title"> > <a>, data (testo tipo "27/07/2026") nel
    # blocco, e un secondo link "Vai al necrologio" che punta alla stessa pagina
    # (va ignorato per non duplicare la voce). Ci ancoriamo all'h3 del nome,
    # che compare una sola volta per necrologio.
    for h3 in soup.find_all("h3", class_="name-title"):
        link_tag = h3.find("a", href=True)
        if not link_tag:
            continue
        href = link_tag["href"]
        if f"/necrologi/umbria/{slug}/" not in href:
            continue

        nome = link_tag.get_text(strip=True)
        if not nome:
            continue

        link = href if href.startswith("http") else f"https://inmemoria.paginebianche.it{href}"
        if link in link_visti:
            continue
        link_visti.add(link)

        # Risaliamo al blocco contenitore per trovare la data vicina
        blocco = h3.find_parent(["article", "div", "li"]) or h3.parent
        testo_blocco = blocco.get_text(" ", strip=True) if blocco else ""

        m_data = re.search(r"(\d{2}/\d{2}/\d{4})", testo_blocco)
        data_decesso = m_data.group(1) if m_data else None

        necrologi.append({
            "nome": nome,
            "data": data_decesso,
            "link": link,
        })

    return necrologi


def filtra_oggi(necrologi):
    oggi = date.today().strftime("%d/%m/%Y")
    return [n for n in necrologi if n["data"] == oggi], oggi


def ottieni_dettagli(link_necrologio):
    """Apre la pagina del singolo necrologio e legge quello che c'è oltre al
    nome e alla data: la foto del defunto e l'agenzia funebre che se ne
    occupa. Il sito NON pubblica da nessuna parte (né in testo né in
    immagine) la chiesa, il cimitero o l'orario del funerale: l'unico modo
    per saperlo è aprire il link del necrologio o contattare l'agenzia.

    Ritorna {"foto": url|None, "agenzia": {nome, localita, link}|None}.
    """
    resp = _scarica_con_retry(link_necrologio)
    soup = BeautifulSoup(resp.text, "html.parser")

    img_foto = soup.find("img", alt="Foto del defunto")
    foto = img_foto["src"] if img_foto and img_foto.get("src") else None

    agenzia = None
    titolo = soup.find("h3", class_="title-rev-08")
    if titolo:
        nome_agenzia = titolo.get_text(strip=True)

        p_localita = titolo.find_next("p")
        localita = re.sub(r"\s+", " ", p_localita.get_text(" ", strip=True)) if p_localita else None

        a_onoranza = titolo.find_next("a", href=True)
        link_onoranza = None
        if a_onoranza:
            href = a_onoranza["href"]
            link_onoranza = href if href.startswith("http") else f"https://inmemoria.paginebianche.it{href}"

        agenzia = {"nome": nome_agenzia, "localita": localita, "link": link_onoranza}

    return {"foto": foto, "agenzia": agenzia}


def formatta(necrologi, titolo):
    righe = [f"\n=== {titolo} ===\n"]
    if not necrologi:
        righe.append("Nessun necrologio trovato per questa data.")
        return righe
    for n in necrologi:
        righe.append(f"- {n['nome']}  ({n['data']})")
        righe.append(f"    Link: {n['link']}")
        righe.append("")
    return righe


if __name__ == "__main__":
    mostra_tutti = "--tutti" in sys.argv

    output = [
        f"Funeral Calendar - generato il {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    ]

    errori = []
    for nome_localita, url in LOCALITA.items():
        slug = url.rstrip("/").split("/")[-1]
        try:
            necrologi = scarica_necrologi(url, slug)
        except (requests.RequestException, RuntimeError) as e:
            errori.append(f"{nome_localita}: errore durante lo scaricamento ({e})")
            output.append(f"\n=== {nome_localita} ===\n\nERRORE: impossibile scaricare la pagina ({e}).")
            continue

        if mostra_tutti:
            output.extend(formatta(necrologi, f"Tutti i necrologi presenti in pagina - {nome_localita}"))
        else:
            di_oggi, data_oggi = filtra_oggi(necrologi)
            output.extend(formatta(di_oggi, f"Necrologi di oggi ({data_oggi}) - {nome_localita}"))

    output.append(
        "\nNota: l'orario e la chiesa/luogo del funerale non sono pubblicati in\n"
        "formato testo su questa fonte. Apri il link del necrologio, oppure chiama\n"
        "direttamente l'agenzia funebre indicata per l'orario esatto.\n"
        "Per Trestina: agenzia locale di riferimento Bastianoni, tel. 075 8642146."
    )

    testo = "\n".join(output)
    print(testo)

    FILE_OUTPUT.write_text(testo + "\n", encoding="utf-8")

    if errori:
        sys.exit(1)
