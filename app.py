from flask import Flask, render_template, request, redirect, send_file, url_for
import os
import json
from datetime import datetime
from Preventivi import PDF, ridimensiona_immagine_infisso, rimuovi_caratteri_non_supportati, calcola_prezzo_mq

app = Flask(__name__)
PREZZI_FILE = "prezzi.json"

# Funzioni gestione prezzi
def carica_prezzi():
    if os.path.exists(PREZZI_FILE):
        with open(PREZZI_FILE, "r") as f:
            return json.load(f)
    else:
        return {
            "vetro_doppio": 250,
            "vetro_triplo": 300,
            "vetro_argon": 330,
            "cassonetto": 130,
            "avvolgibile_mq": 35,
            "rullo": 40,
            "pellicolato_percentuale": 20,
            "maggiorazione_spessore_massima": 8,
            "spessore_base": 76,
            "spessore_massimo": 96
        }

def salva_prezzi(dati):
    with open(PREZZI_FILE, "w") as f:
        json.dump(dati, f, indent=4)

from fpdf import FPDF

def pulisci_testo_pdf(testo):
    sostituzioni = {
        "\u2018": "'",  # apostrofo sinistro
        "\u2019": "'",  # apostrofo destro
        "\u201c": '"',  # virgolette alte sinistra
        "\u201d": '"',  # virgolette alte destra
        "\u2026": "...",  # puntini di sospensione
        "\u2013": "-",  # trattino medio
        "\u2014": "-",  # trattino lungo
        "’": "'",       # apostrofo Word
    }
    for k, v in sostituzioni.items():
        testo = testo.replace(k, v)
    return testo.encode("latin-1", "replace").decode("latin-1")

from fpdf import FPDF

def pulisci_testo_pdf(testo):
    sostituzioni = {
        "\u2018": "'",  # apostrofo sinistro
        "\u2019": "'",  # apostrofo destro
        "\u201c": '"',  # virgolette alte sinistra
        "\u201d": '"',  # virgolette alte destra
        "\u2026": "...",  # puntini di sospensione
        "\u2013": "-",  # trattino medio
        "\u2014": "-",  # trattino lungo
        "’": "'",       # apostrofo Word
    }
    for k, v in sostituzioni.items():
        testo = testo.replace(k, v)
    return testo.encode("latin-1", "replace").decode("latin-1")

def genera_numero_preventivo():
    from datetime import datetime
    anno = datetime.now().year
    progressivo_file = "progressivo.json"

    if os.path.exists(progressivo_file):
        with open(progressivo_file, "r") as f:
            dati = json.load(f)
    else:
        dati = {}

    numero = dati.get(str(anno), 0) + 1
    dati[str(anno)] = numero

    with open(progressivo_file, "w") as f:
        json.dump(dati, f)

    return f"{numero:04d}_{anno}"  # es. 0002_2025


def genera_pdf(cliente, articoli, filepath, numero_preventivo):
    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    numero_preventivo = genera_numero_preventivo()

    # Logo in alto a sinistra
    logo_path = os.path.join("static", "immagini", "logo.jpg")
    if os.path.exists(logo_path):
        pdf.image(logo_path, x=10, y=5, w=120)

    # Numero preventivo sotto il logo
    pdf.set_xy(10, 55)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, f"Preventivo : n. {numero_preventivo}", ln=True)

    # Intestazione cliente
    pdf.set_xy(110, 15)
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 10, pulisci_testo_pdf(f"{cliente['nome']} {cliente['cognome']}"), ln=True, align="R")
    pdf.cell(0, 10, pulisci_testo_pdf(cliente["indirizzo"]), ln=True, align="R")
    pdf.cell(0, 10, f"Data: {cliente['data']}", ln=True, align="R")
    pdf.ln(20)

    prezzi = carica_prezzi()
    totale = 0
    accessori_tot = 0

    for i, a in enumerate(articoli):
        descrizione = a["descrizione"]
        if a.get("cassonetti") == "s":
            descrizione += " - Con cassonetti"
            accessori_tot += prezzi["cassonetto"]
        if a.get("avvolgibili") == "s":
            prezzo = prezzi["avvolgibile_mq"] * (a["larghezza"]/1000) * (a["altezza"]/1000)
            descrizione += f" - Avvolgibili ({prezzo:.2f} EUR)"
            accessori_tot += prezzo
        if a.get("rullo") == "s":
            descrizione += " - Rullo puleggia"
            accessori_tot += prezzi["rullo"]
        if a.get("pellicolato") == "s":
            descrizione += f" - Pellicolato ({a['effetto_pellicolato']})"
        descrizione += f" - Tipo serramento: {a.get('tipo_serramento', 'N/A')}"

        if a.get("accessori"):
            descrizione += f" - Accessori: {a['accessori']}"
            if "pro" in a["accessori"].lower():
                accessori_tot += prezzi.get("maniglia_pro_percentuale", 0) / 100
            else:
                accessori_tot += prezzi.get("maniglia_base", 0)

        prezzo_mq_base = prezzi.get(f"vetro_{a.get('tipo_vetro', 'doppio')}", prezzi["vetro_doppio"])
        delta = a["spessore"] - prezzi["spessore_base"]
        range_spessore = prezzi["spessore_massimo"] - prezzi["spessore_base"]
        fattore_spessore = 1 + (delta / range_spessore) * (prezzi["maggiorazione_spessore_massima"] / 100)

        prezzo_unitario, area = calcola_prezzo_mq(a["larghezza"], a["altezza"], prezzo_mq_base)
        prezzo_unitario *= fattore_spessore
        if a.get("pellicolato") == "s":
            prezzo_unitario *= (1 + prezzi["pellicolato_percentuale"] / 100)

        tot = prezzo_unitario * a["quantita"]
        totale += tot

        tipo_vetro = {
            "doppio": "Vetro camera base",
            "triplo": "Triplo vetro",
            "argon": "Triplo vetro con gas Argon"
        }.get(a["tipo_vetro"], "Vetro camera base")

        pdf.set_font("Arial", "", 10)
        pdf.multi_cell(0, 10, pulisci_testo_pdf(descrizione))
        pdf.ln(1)

        # Immagine
        colore = "legno" if "legno" in a["effetto_pellicolato"].lower() else "bianca"
        ante = a.get("numero_ante", "2")
        base_nome = f"finestra_{colore}_{'singola' if ante == '1' else 'doppia' if ante == '2' else 'tripla'}"
        immagine_base = os.path.join("static", "immagini", f"{base_nome}.jpg")
        immagine_output = os.path.join("static", "immagini", f"{base_nome}_{i+1}.png")

        if os.path.exists(immagine_base):
            larghezza_img = 45 if ante == '1' else 50
            ridimensiona_immagine_infisso(a["larghezza"], a["altezza"], immagine_base, immagine_output)
            pdf.image(immagine_output, x=20, y=pdf.get_y(), w=larghezza_img, h=50)

        pdf.set_xy(80, pdf.get_y())
        pdf.multi_cell(0, 10, pulisci_testo_pdf(
            f"Dimensioni: {a['larghezza']} x {a['altezza']} mm\n"
            f"Area: {area:.2f} mq\n"
            f"Tipo vetro: {tipo_vetro}\n"
            f"Spessore vetro: fino a 55 mm\n"
            f"Prezzo unitario: {prezzo_unitario:.2f} EUR\n"
            f"Quantità: {a['quantita']}\n"
            f"Totale: {tot:.2f} EUR\n"
            f"Trasmittanza Uw dichiarata: 0.8 W/m²K"
        ))
        pdf.ln(10)

    # Totali
    imponibile = totale + accessori_tot
    iva = imponibile * 0.10
    totale_finale = imponibile + iva
    pdf.ln(5)
    pdf.cell(0, 10, f"Imponibile: {imponibile:.2f} EUR", ln=True)
    pdf.cell(0, 10, f"IVA 10%: {iva:.2f} EUR", ln=True)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(0, 10, f"Totale: {totale_finale:.2f} EUR", ln=True)

    # Seconda pagina: Specifiche tecniche
    pdf.add_page()
    pdf.set_font("Arial", "B", 10)
    pdf.cell(0, 10, "Caratteristiche Tecniche del Sistema", ln=True)
    pdf.set_font("Arial", "", 11)
    pdf.multi_cell(0, 8, pulisci_testo_pdf(
        "Profondità telaio: 76 mm\n"
        "Profondità anta: 80 mm\n"
        "Fermavetro: arrotondato o squadrato\n"
        "Spessore vetro fino a: 55 mm\n"
        "Sistema di guarnizioni: tripla guarnizione\n"
        "Incollaggio vetro: opzionale\n"
        "Trasmittanza nodo Uf: 1,0 W/m²K\n"
        "Trasmittanza serramento Uw: 0,8 W/m²K\n"
        "Portata cerniere: fino a 130 kg\n"
        "Resistenza al fuoco: Classe 1\n"
        "Permeabilità all'aria: Classe 4\n"
        "Tenuta all'acqua: E750\n"
        "Resistenza al vento: C4\n"
        "Antieffrazione: RC3\n"
        "Abbattimento acustico: fino a 47 dB"
    ))

    # Aggiunta immagine pellicole
    img_pellicole = os.path.join("static", "immagini", "pellicole.jpg")
    if os.path.exists(img_pellicole):
        pdf.image(img_pellicole, x=20, y=pdf.get_y()+10, w=180)

    # Salvataggio PDF
    pdf.output(filepath)


from PIL import Image

def ridimensiona_immagine_infisso(larghezza_mm, altezza_mm, path_input, path_output):
    try:
        # Carica immagine base (jpg)
        img = Image.open(path_input)

        # Calcola proporzioni reali (conversione mm → px arbitraria per simulazione)
        rapporto = altezza_mm / larghezza_mm
        base = 150  # larghezza fissa di riferimento in pixel

        if rapporto > 1.5:
            nuova_larghezza = int(base * 0.6)
            nuova_altezza = int(base * 1.8)
        elif rapporto < 0.75:
            nuova_larghezza = int(base * 1.8)
            nuova_altezza = int(base * 0.6)
        else:
            nuova_larghezza = base
            nuova_altezza = base

        # Ridimensiona l'immagine
        img = img.resize((nuova_larghezza, nuova_altezza), Image.LANCZOS)

        # Salva come PNG per il PDF
        img.save(path_output, format="PNG")

    except Exception as e:
        print(f"[ERRORE] Impossibile ridimensionare immagine: {e}")


import uuid

@app.route("/", methods=["GET", "POST"])
def index():
    oggi = datetime.now().strftime("%d/%m/%Y")
    if request.method == "POST":
        session_id = str(uuid.uuid4())
        cliente = {
            "nome": request.form["nome"],
            "cognome": request.form["cognome"],
            "email": request.form["email"],
            "indirizzo": request.form["indirizzo"],
            "data": request.form["data"],
            "session_id": session_id
        }
        os.makedirs("sessione", exist_ok=True)
        with open(f"sessione/cliente_{session_id}.json", "w") as f:
            json.dump(cliente, f)
        return redirect(f"/articolo/1?session={session_id}")
    return render_template("index.html", data_oggi=oggi)


@app.route("/articolo/<int:n>", methods=["GET", "POST"])
def articolo(n):
    session_id = request.args.get("session")

    if request.method == "POST":
        articolo = {
        "descrizione": request.form["descrizione"],
        "larghezza": float(request.form["larghezza"]),
        "altezza": float(request.form["altezza"]),
        "cassonetti": request.form.get("cassonetti", "n"),
        "avvolgibili": request.form.get("avvolgibili", "n"),
        "rullo": request.form.get("rullo", "n"),
        "pellicolato": request.form.get("pellicolato", "n"),
        "effetto_pellicolato": request.form.get("effetto_pellicolato", ""),
        "accessori": request.form.get("accessori", ""),
        "costo_accessori": 0,
        "quantita": int(request.form["quantita"]),
        "spessore": float(request.form["spessore"]),
        "tipo_vetro": request.form.get("tipo_vetro", "doppio"),
        "numero_ante": request.form.get("numero_ante", "2"),
        "tipo_serramento": request.form.get("tipo_serramento", "pvc")  # <-- AGGIUNTO QUI
    }

        # Salva articolo
        os.makedirs("sessione", exist_ok=True)
        articoli = []
        lista_file = f"sessione/articoli_{session_id}.json"
        if os.path.exists(lista_file):
            with open(lista_file, "r") as f:
                articoli = json.load(f)
        articoli.append(articolo)
        with open(lista_file, "w") as f:
            json.dump(articoli, f)

        azione = request.form["azione"]
        if azione == "continua":
            return redirect(f"/articolo/{n+1}?session={session_id}")
        else:
            return redirect(f"/conferma?session={session_id}")

    return render_template("articolo.html", numero=n, totale=n)

@app.route("/conferma", methods=["GET", "POST"])
def conferma():
    session_id = request.args.get("session")

    with open(f"sessione/cliente_{session_id}.json") as f:
        cliente = json.load(f)
    with open(f"sessione/articoli_{session_id}.json") as f:
        articoli = json.load(f)

    if request.method == "POST":
        numero_preventivo = genera_numero_preventivo()
        filename = f"Preventivo_{numero_preventivo}.pdf"
        filepath = os.path.join("preventivi", filename)
        os.makedirs("preventivi", exist_ok=True)

        try:
            genera_pdf(cliente, articoli, filepath, numero_preventivo)

            # ✅ Elimina i JSON temporanei
            os.remove(f"sessione/cliente_{session_id}.json")
            os.remove(f"sessione/articoli_{session_id}.json")

            return render_template("conferma.html", success=True, file=filename)
        except Exception as e:
            return f"<h1>Errore nella generazione del PDF</h1><p>{e}</p>"

    return render_template("conferma.html", cliente=cliente, articoli=articoli, success=False)


@app.route("/download/<filename>")
def download(filename):
    path = os.path.join("preventivi", filename)
    if os.path.exists(path):
        return send_file(path, as_attachment=True)
    return f"File {filename} non trovato", 404

@app.route("/prezzi", methods=["GET", "POST"])
def prezzi_view():
    prezzi_file = "prezzi.json"

    if request.method == "POST":
        # Aggiorna i prezzi dal form
        with open(prezzi_file, "r") as f:
            prezzi = json.load(f)

        for key in prezzi:
            if key in request.form:
                try:
                    prezzi[key] = float(request.form[key].replace(",", "."))
                except ValueError:
                    pass  # ignora valori non validi

        with open(prezzi_file, "w") as f:
            json.dump(prezzi, f, indent=4)

        return redirect("/prezzi")

    # GET: carica i prezzi e mostra il form
    with open(prezzi_file, "r") as f:
        prezzi = json.load(f)

    return render_template("prezzi.html", prezzi=prezzi)
