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

# Funzione per generare PDF
from fpdf import FPDF

def genera_pdf(cliente, articoli, filepath):
    pdf = PDF()
    pdf.add_page()

    # Logo in alto al centro
    logo_path = os.path.join("immagini", "logo.jpg")
    if os.path.exists(logo_path):
        pdf.image(logo_path, x=40, y=10, w=130)
        pdf.ln(40)

    # Dati cliente
    pdf.set_xy(120, 50)
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 10, f"{cliente['nome']} {cliente['cognome']}", ln=True, align="R")
    pdf.cell(0, 10, cliente["indirizzo"], ln=True, align="R")
    pdf.cell(0, 10, f"Data: {cliente['data']}", ln=True, align="R")
    pdf.ln(10)

    prezzi = carica_prezzi()
    totale = 0
    accessori_tot = 0

    for i, a in enumerate(articoli):
        descrizione = a["descrizione"]
        if a["cassonetti"] == "s":
            descrizione += " - Con cassonetti"
            accessori_tot += prezzi["cassonetto"]
        if a["avvolgibili"] == "s":
            prezzo = prezzi["avvolgibile_mq"] * (a["larghezza"]/1000) * (a["altezza"]/1000)
            descrizione += f" - Avvolgibili ({prezzo:.2f} EUR)"
            accessori_tot += prezzo
        if a["rullo"] == "s":
            descrizione += " - Rullo puleggia"
            accessori_tot += prezzi["rullo"]
        if a["pellicolato"] == "s":
            descrizione += f" - Pellicolato ({a['effetto_pellicolato']})"

        if a["accessori"]:
            descrizione += f" - Accessori: {a['accessori']}"

        # Calcolo prezzo in base al tipo di vetro
        prezzo_mq_base = prezzi.get(f"vetro_{a['tipo_vetro']}", prezzi["vetro_doppio"])

        # Maggiorazione per spessore
        delta = a["spessore"] - prezzi["spessore_base"]
        range_spessore = prezzi["spessore_massimo"] - prezzi["spessore_base"]
        fattore_spessore = 1 + (delta / range_spessore) * (prezzi["maggiorazione_spessore_massima"] / 100)

        # Calcolo prezzo unitario
        prezzo_unitario, area = calcola_prezzo_mq(a["larghezza"], a["altezza"], prezzo_mq_base)
        prezzo_unitario *= fattore_spessore

        if a["pellicolato"] == "s":
            prezzo_unitario *= (1 + prezzi["pellicolato_percentuale"] / 100)

        tot = prezzo_unitario * a["quantita"]
        totale += tot

        tipo_vetro = {
            "doppio": "Doppio vetro",
            "triplo": "Triplo vetro",
            "argon": "Triplo vetro con gas Argon"
        }.get(a["tipo_vetro"], "Doppio vetro")

        trasmittanza = 0.8
        pdf.set_font("Arial", "", 12)
        pdf.cell(0, 10, descrizione, ln=True)

        immagine_output = f"finestra_{i+1}.png"
        immagine_base = os.path.join("immagini", "finestra.png")
        ridimensiona_immagine_infisso(a["larghezza"], a["altezza"], immagine_base, immagine_output)

        pdf.image(os.path.join("immagini", immagine_output), x=20, y=pdf.get_y(), w=50, h=50)
        pdf.set_xy(80, pdf.get_y())
        pdf.multi_cell(0, 10,
            f"Dimensioni: {a['larghezza']} x {a['altezza']} mm\n"
            f"Area: {area:.2f} mq\n"
            f"Tipo vetro: {tipo_vetro}\n"
            f"Spessore vetro: fino a 55 mm\n"
            f"Prezzo unitario: {prezzo_unitario:.2f} EUR\n"
            f"Quantità: {a['quantita']}\n"
            f"Totale: {tot:.2f} EUR\n"
            f"Trasmittanza Uw dichiarata: {trasmittanza} W/m²K"
        )
        pdf.ln(10)

    imponibile = totale + accessori_tot
    iva = imponibile * 0.10
    totale_finale = imponibile + iva
    pdf.ln(10)
    pdf.cell(0, 10, f"Imponibile: {imponibile:.2f} EUR", ln=True)
    pdf.cell(0, 10, f"IVA 10%: {iva:.2f} EUR", ln=True)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, f"Totale: {totale_finale:.2f} EUR", ln=True)

    # Pagina riepilogo tecnico
    pdf.add_page()
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Caratteristiche Tecniche del Sistema", ln=True)

    pdf.set_font("Arial", "", 11)
    pdf.multi_cell(0, 8,
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
        "Permeabilità all’aria: Classe 4\n"
        "Tenuta all’acqua: E750\n"
        "Resistenza al vento: C4\n"
        "Antieffrazione: RC3\n"
        "Abbattimento acustico: fino a 47 dB"
    )

    pdf.output(filepath)


@app.route("/prezzi", methods=["GET", "POST"])
def prezzi():
    if request.method == "POST":
        nuovi_prezzi = {
            "vetro_doppio": float(request.form["vetro_doppio"]),
            "vetro_triplo": float(request.form["vetro_triplo"]),
            "vetro_argon": float(request.form["vetro_argon"]),
            "cassonetto": float(request.form["cassonetto"]),
            "avvolgibile_mq": float(request.form["avvolgibile_mq"]),
            "rullo": float(request.form["rullo"]),
            "pellicolato_percentuale": float(request.form["pellicolato_percentuale"]),
            "maggiorazione_spessore_massima": float(request.form["maggiorazione_spessore_massima"]),
            "spessore_base": float(request.form["spessore_base"]),
            "spessore_massimo": float(request.form["spessore_massimo"]),
        }
        salva_prezzi(nuovi_prezzi)
        return redirect(url_for("prezzi"))

    prezzi = carica_prezzi()
    return render_template("prezzi.html", prezzi=prezzi)


@app.route("/", methods=["GET", "POST"])
def index():
    oggi = datetime.now().strftime("%d/%m/%Y")
    if request.method == "POST":
        cliente = {
            "nome": request.form["nome"],
            "cognome": request.form["cognome"],
            "email": request.form["email"],
            "indirizzo": request.form["indirizzo"],
            "data": request.form["data"]
        }
        os.makedirs("sessione", exist_ok=True)
        with open("sessione/cliente.json", "w") as f:
            json.dump(cliente, f)
        return redirect("/articolo/1")
    return render_template("index.html", data_oggi=oggi)

@app.route("/articolo/<int:n>", methods=["GET", "POST"])
def articolo(n):
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
            "tipo_vetro": request.form.get("tipo_vetro", "doppio")
        }
        os.makedirs("sessione", exist_ok=True)
        lista_file = "sessione/articoli.json"
        articoli = []
        if os.path.exists(lista_file):
            with open(lista_file, "r") as f:
                articoli = json.load(f)
        articoli.append(articolo)
        with open(lista_file, "w") as f:
            json.dump(articoli, f)

        if n < int(request.form["totale_articoli"]):
            return redirect(f"/articolo/{n+1}")
        else:
            return redirect("/conferma")
    totale = 1
    return render_template("articolo.html", numero=n, totale=totale)

@app.route("/conferma", methods=["GET", "POST"])
def conferma():
    with open("sessione/cliente.json") as f:
        cliente = json.load(f)
    with open("sessione/articoli.json") as f:
        articoli = json.load(f)

    if request.method == "POST":
        filename = f"Preventivo_{rimuovi_caratteri_non_supportati(cliente['nome'])}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
        filepath = os.path.join("preventivi", filename)
        os.makedirs("preventivi", exist_ok=True)
        genera_pdf(cliente, articoli, filepath)
        return render_template("conferma.html", success=True, file=filename)

    return render_template("conferma.html", cliente=cliente, articoli=articoli, success=False)

@app.route("/download/<filename>")
def download(filename):
    return send_file(os.path.join("preventivi", filename), as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)
