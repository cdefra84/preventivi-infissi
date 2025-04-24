from flask import Flask, render_template, request, redirect, send_file, url_for
import random
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

def scrivi_intestazione_tabella(pdf):
    pdf.set_font("Arial", "B", 9)
    pdf.set_fill_color(50, 200, 240)
    pdf.cell(15, 10, "Art.", border=1, align="C", fill=True)
    pdf.cell(85, 10, "Descrizione", border=1, align="C", fill=True)
    pdf.cell(20, 10, "Pz", border=1, align="C", fill=True)
    pdf.cell(35, 10, "Prezzo", border=1, align="C", fill=True)
    pdf.cell(35, 10, "Totale", border=1, ln=True, align="C", fill=True)

    # 🔻 Reset del font normale (non in grassetto)
    pdf.set_font("Arial", "", 9)

def calcola_sconto_migliore(totale, totale_pezzi, prezzi):
    # Sconti per pezzi
    if totale_pezzi > 50:
        sconto_pezzi = prezzi.get("sconto_oltre_50_pezzi", 0)
    elif totale_pezzi > 10:
        sconto_pezzi = prezzi.get("sconto_11_20_pezzi", 0)
    elif totale_pezzi >= 5:
        sconto_pezzi = prezzi.get("sconto_5_10_pezzi", 0)
    else:
        sconto_pezzi = 0

    # Sconti per importo
    if totale > 50000:
        sconto_importo = prezzi.get("sconto_oltre_50000", 0)
    elif totale > 10000:
        sconto_importo = prezzi.get("sconto_10000_50000", 0)
    elif totale >= 5000:
        sconto_importo = prezzi.get("sconto_5000_10000", 0)
    else:
        sconto_importo = 0

    # Applica il maggiore dei due
    sconto_percentuale = max(sconto_pezzi, sconto_importo)
    sconto_valore = totale * sconto_percentuale / 100
    return sconto_percentuale, round(sconto_valore, 2)

from geopy.geocoders import Nominatim
from geopy.distance import geodesic

def calcola_distanza_km(citta_destinazione):
    from geopy.geocoders import Nominatim
    from geopy.distance import geodesic
    geolocator = Nominatim(user_agent="preventivo_infissi")
    origine = geolocator.geocode("Rocchetta Sant'Antonio, Italia")
    destinazione = geolocator.geocode(citta_destinazione + ", Italia")
    if not origine or not destinazione:
        raise ValueError("Città non trovata")
    coord_origine = (origine.latitude, origine.longitude)
    coord_destinazione = (destinazione.latitude, destinazione.longitude)
    return round(geodesic(coord_origine, coord_destinazione).km, 2)

def get_zona_climatica(citta):
    try:
        with open("comuni_zona_climatica.json", "r", encoding="utf-8") as f:
            mapping = json.load(f)
        return mapping.get(citta.strip().lower())
    except:
        return None

def genera_pdf(cliente, articoli, filepath, numero_preventivo):
    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # 🔺 Posizionamento iniziale
    start_y = 10
    logo_path = os.path.join("static", "immagini", "logo.jpg")

    # 🔻 Logo a sinistra
    if os.path.exists(logo_path):
        pdf.image(logo_path, x=20, y=start_y, w=40)  # più piccolo e più alto

    # 🔹 Testo a destra del logo
    pdf.set_xy(70, start_y + 2)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 6, "INFISSI MOBILIFICIO E FALEGNAMERIA", ln=True)

    pdf.set_x(70)
    pdf.set_font("Arial", "", 9)
    pdf.cell(0, 5, "SHOWROOM ROCCHETTA SANT'ANTONIO - Cell. 333.4352383", ln=True)

    pdf.set_x(70)
    pdf.cell(0, 5, "SHOWROOM MONTEFALCIONE (AV) - Cell. 389.9686594", ln=True)

    pdf.set_x(70)
    pdf.cell(0, 5, "Email: falegnameriaamerico@tiscali.it", ln=True)

    pdf.ln(15)  # Spazio extra prima del numero preventivo

    # 🔸 Numero preventivo
    pdf.set_font("Arial", "B", 11)
    pdf.set_x(10)
    pdf.cell(0, 10, f"Preventivo n. {numero_preventivo}", ln=True)

    pdf.ln(15)
    pdf.set_font("Arial", "", 8)
    pdf.multi_cell(0, 10, pulisci_testo_pdf(
        "Ringraziandola per la sua richiesta, Le sottoponiamo la nostra miglior offerta."
    ))

    # Intestazione cliente
    pdf.set_xy(110, 40)
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 5, pulisci_testo_pdf("Spett.le"), ln=True, align="R")
    pdf.cell(0, 5, pulisci_testo_pdf(f"Sig. {cliente['nome']} {cliente['cognome']}"), ln=True, align="R")
    pdf.cell(0, 5, pulisci_testo_pdf(f"{cliente['indirizzo']} – {cliente['citta']}"), ln=True, align="R")
    pdf.cell(0, 5, pulisci_testo_pdf(f"TEL: {cliente['telefono']}"), ln=True, align="R")
    pdf.cell(0, 5, pulisci_testo_pdf(f"Email: {cliente['email']}"), ln=True, align="R")
    pdf.cell(0, 10, pulisci_testo_pdf(f"Data: {cliente['data']}"), ln=True, align="S")
    pdf.ln(5)

    prezzi = carica_prezzi()
    totale = 0
    accessori_tot = 0

    # Sposta il cursore più in basso
    pdf.set_y(pdf.get_y() + 5)

    pdf.set_fill_color(150, 200, 240)
    scrivi_intestazione_tabella(pdf)

    for i, a in enumerate(articoli):
        descrizione = a["descrizione"]
        dettagli = []
    # Dati binari/descrittivi
        
        dettagli.append(f"Dimensioni: {a['larghezza']} x {a['altezza']} mm")
        dettagli.append(f"Numero ante: {a.get('numero_ante', '2')}")
        dettagli.append(f"Tipo serramento: {a.get('tipo_serramento', 'pvc')}")
        dettagli.append(f"Spessore: {a.get('spessore', 76)} mm")

        cassonetti = a.get("cassonetti", "n")
        avvolgibili = a.get("avvolgibili", "n")
        rullo = a.get("rullo", "n")
        vasistas = a.get("vasistas", "n")
        pellicolato = a.get("pellicolato", "n")
        effetto = a.get("effetto_pellicolato", "Nessuno")
        accessori = a.get("accessori", "")
        dettagli.append(f"Tipo Telaio: Telaio L")
        if cassonetti == 's':
            dettagli.append("Cassonetti: Sì")
        if avvolgibili == 's':
            dettagli.append("Avvolgibili: Sì")
        if rullo == 's':
            dettagli.append("Rullo puleggia: Sì")
        tipo_vetro_raw = a.get("tipo_vetro", "doppio")
        if tipo_vetro_raw == "doppio":
            tipo_descrizione = "Doppio vetro 33.1/15 Super Spacer"
        elif tipo_vetro_raw == "triplo":
            tipo_descrizione = "Triplo vetro 33.1/15 Super Spacer"
        elif tipo_vetro_raw == "argon":
            tipo_descrizione = "Triplo vetro 33.1/15 Super Spacer con Gas Argon / 33.1BE 1.0"
        else:
            tipo_descrizione = tipo_vetro_raw

        dettagli.append(f"Tipo vetro: {tipo_descrizione}")
        dettagli.append(f"Vasistas (Ribaltabile): {'Sì' if vasistas == 's' else 'No'}")
        if pellicolato == 's':
            if "-" in effetto:
                interno, esterno = effetto.split("-", 1)
                dettagli.append(f"Pellicolato bicolore: Interno {interno.strip()} / Esterno {esterno.strip()}")
            else:
                dettagli.append(f"Pellicolato: {effetto}")
        else:
            dettagli.append("Pellicolato: No")

        dettagli.append(f"Accessori: {accessori if accessori else 'Nessuno'}")
        if a.get("soglia_ribassata") == "s":
            dettagli.append(f"Soglia ribassata: Sì – quantità {a['quantita']}")
        else:
            dettagli.append("Soglia ribassata: No")
        dettagli.append("Piattina da 30 colore")
        colore_guida = effetto if pellicolato == "s" else "bianco"


        prezzo_mq_base = prezzi.get(f"vetro_{a.get('tipo_vetro', 'doppio')}", prezzi["vetro_doppio"])
        delta = a["spessore"] - prezzi["spessore_base"]
        range_spessore = prezzi["spessore_massimo"] - prezzi["spessore_base"]
        fattore_spessore = 1 + (delta / range_spessore) * (prezzi["maggiorazione_spessore_massima"] / 100)
        prezzo_unitario, area = calcola_prezzo_mq(a["larghezza"], a["altezza"], prezzo_mq_base)
        prezzo_unitario *= fattore_spessore
        if a.get("pellicolato") == "s":
            prezzo_unitario *= (1 + prezzi["pellicolato_percentuale"] / 100)
            if "-" in effetto:
                prezzo_unitario *= (1 + prezzi.get("pellicolato_bicolore_percentuale", 10) / 100)

        # Imposta prezzo minimo per infisso (per singolo pezzo)
        prezzo_unitario = max(prezzo_unitario, prezzi.get("prezzo_minimo_infisso", 180))
        tot = prezzo_unitario * a["quantita"]
        totale += tot

        # calcolo altezza blocco
        pdf.set_font("Arial", "", 9)
        line_height = 5  # pixel per riga
        padding = 8      # margini sopra/sotto totali
        altezza_blocco = line_height * len(dettagli) + padding


        # controllo spazio pagina
        if pdf.get_y() + altezza_blocco > 270:
            pdf.add_page()
            pdf.set_fill_color(150, 200, 240)
            scrivi_intestazione_tabella(pdf)

        # Cornice per blocco tabella singolo articolo
        # Colore grigio chiaro
        pdf.set_fill_color(200, 230, 255)

        pdf.cell(15, 10, f"{i+1}", border=1, align="C", fill=True)
        pdf.cell(85, 10, pulisci_testo_pdf(descrizione.upper()), border=1, fill=True)
        pdf.cell(20, 10, str(a["quantita"]), border=1, align="C", fill=True)
        pdf.cell(35, 10, f"{prezzo_unitario:.2f} EUR", border=1, align="C", fill=True)
        pdf.cell(35, 10, f"{tot:.2f} EUR", border=1, ln=True, align="C", fill=True)


        pdf.set_font("Arial", "", 9)
        y_start = pdf.get_y()
        pdf.rect(10, y_start, 190, altezza_blocco)
        pdf.line(130, y_start, 130, y_start + altezza_blocco)  # linea tra "Pz" e "Prezzo"


        # Inserisci elenco a sinistra
        x_dettagli = 15  # margine sinistro uniforme
        pdf.set_xy(x_dettagli, y_start + 5)
        for punto in dettagli:
            pdf.set_x(x_dettagli)
            pdf.cell(120, 5, f"- {pulisci_testo_pdf(punto)}", ln=True)


        # Inserisci immagine
        x_img = 140
        y_img = y_start + 8
        colore = determina_categoria(a["effetto_pellicolato"])
        ante = a.get("numero_ante", "2")
        modello = "singola" if ante == "1" else "doppia" if ante == "2" else "tripla"
        immagine_output = a.get("immagine") or f"static/immagini/finestra_{modello}_{colore}.jpg"
        # Calcolo spazio disponibile
        altezza_massima_immagine = altezza_blocco - 23  # margine top/bottom
        larghezza_massima_immagine = 43  # oppure 43 per sicurezza

        # Ottieni dimensioni originali
        from PIL import Image
        img_path = os.path.join("static", a["immagine"]) if not a["immagine"].startswith("static") else a["immagine"]
        img = Image.open(img_path)
        larghezza_img, altezza_img = img.size
        rapporto = larghezza_img / altezza_img

        # Calcola dimensioni finali per stare nel blocco
        w = min(larghezza_massima_immagine, altezza_massima_immagine * rapporto)
        h = w / rapporto

        # Inserisci immagine scalata
        if os.path.exists(img_path):
            pdf.image(img_path, x=x_img, y=y_img, w=w, h=h)

        # Linee di quota immagine
        altezza_testo = 4  # altezza del font
        pdf.set_draw_color(0, 0, 0)
        pdf.set_font("Arial", "", 7)

        # LARGHEZZA (sotto l'immagine)
        x_line_start = x_img
        x_line_end = x_img + w
        y_line = y_img + h + 2
        pdf.line(x_line_start, y_line, x_line_end, y_line)
        # Terminali verticali
        pdf.line(x_line_start, y_line - 1.5, x_line_start, y_line + 1.5)
        pdf.line(x_line_end, y_line - 1.5, x_line_end, y_line + 1.5)
        # Testo centrato
        pdf.set_xy(x_line_start, y_line + 1)
        pdf.cell(w, altezza_testo, f"{a['larghezza']} mm", align="C")

        # ALTEZZA (a destra dell’immagine)
        x_h = x_img + w + 2
        y_line_start = y_img
        y_line_end = y_img + h
        pdf.line(x_h, y_line_start, x_h, y_line_end)
        # Terminali orizzontali
        pdf.line(x_h - 1.5, y_line_start, x_h + 1.5, y_line_start)
        pdf.line(x_h - 1.5, y_line_end, x_h + 1.5, y_line_end)
        # Testo centrato in verticale
        pdf.set_xy(x_h + 1.5, y_line_start + (h / 2) - (altezza_testo / 2))
        pdf.cell(15, altezza_testo, f"{a['altezza']} mm", align="L")


        pdf.set_y(y_start + altezza_blocco)

        mesi = random.randint(2, 4)

    # Totali
    imponibile = totale + accessori_tot

    # 🔧 Definisci numero totale di pezzi
    totale_pezzi = sum(a["quantita"] for a in articoli)

    # Sconto applicato
    sconto_percentuale, sconto_valore = calcola_sconto_migliore(imponibile, totale_pezzi, prezzi)

    # Mostra imponibile iniziale
    pdf.ln(5)
    pdf.set_font("Arial", "", 8)
    pdf.cell(0, 5, pulisci_testo_pdf(f"Imponibile: {imponibile:.2f} EUR"), ln=True, align="R")

    # Mostra sconto se presente
    if sconto_percentuale > 0:
        pdf.set_font("Arial", "", 9)
        pdf.cell(160, 8, f"Sconto volume ({sconto_percentuale:.0f}%)", border=0, align="R")
        pdf.cell(30, 8, f"-{sconto_valore:.2f} EUR", border=0, ln=True, align="R")

    imponibile -= sconto_valore  # aggiorna imponibile

    # Calcolo trasferta
    try:
        distanza_km = calcola_distanza_km(cliente["citta"])
        giorni_lavoro = max(1, totale_pezzi // 5)

        # Calcola percentuale trasferta base in base alla distanza
        if distanza_km <= 50:
            percentuale_trasferta = 0.0
        elif distanza_km <= 100:
            percentuale_trasferta = 0.10
        elif distanza_km <= 150:
            percentuale_trasferta = 0.20
        elif distanza_km <= 200:
            percentuale_trasferta = 0.30
        elif distanza_km <= 250:
            percentuale_trasferta = 0.50
        elif distanza_km <= 300:
            percentuale_trasferta = 0.70
        elif distanza_km <= 350:
            percentuale_trasferta = 0.90
        else:
            percentuale_trasferta = 1.00

        base = prezzi.get("trasferta_base", 550)
        extra = prezzi["costo_giornata"] * giorni_lavoro

        costo_trasferta = round(base * percentuale_trasferta + extra, 2)

        pdf.set_font("Arial", "", 8)
        pdf.cell(0, 5, pulisci_testo_pdf(
            f"Trasferta (distanza stimata {distanza_km:.0f} km – {giorni_lavoro} gg lavoro): {costo_trasferta:.2f} EUR"),
            ln=True, align="R")

        imponibile += costo_trasferta

    except Exception:
        pdf.set_font("Arial", "", 8)
        pdf.cell(0, 5, pulisci_testo_pdf(
            "Trasferta: da definire in base alla distanza e al tempo stimato di posa."), ln=True, align="R")

    # Calcolo IVA e Totale finale scontato
    iva = imponibile * 0.10
    totale_finale = imponibile + iva

    # Mostra IVA e Totale scontato
    pdf.set_font("Arial", "", 8)
    pdf.cell(0, 5, pulisci_testo_pdf(f"IVA 10%: {iva:.2f} EUR"), ln=True, align="R")
    pdf.set_font("Arial", "B", 10)
    pdf.cell(0, 5, pulisci_testo_pdf(f"Totale comprensivo di IVA: {totale_finale:.2f} EUR"), ln=True, align="R")

    pdf.ln(5)
    
    # Note fiscali e lavorazione
    pdf.set_font("Arial", "", 8)
    pdf.multi_cell(0, 5, pulisci_testo_pdf(
        "La pratica ENEA è inclusa nel presente preventivo ed è necessaria per accedere alle detrazioni fiscali "
        "del 50% (Bonus Casa) o fino al 65% (Ecobonus) sui lavori di ristrutturazione o miglioramento energetico.\n\n"))

    pdf.set_font("Arial", "", 7)
    pdf.multi_cell(0, 5, pulisci_testo_pdf(
        "Il costo della pratica, che varia in base alla tipologia dell’intervento e all’eventuale necessità di asseverazione tecnica, "
        "è già stato considerato nel totale indicato."
    ))
    pdf.set_font("Arial", "", 8)
    pdf.cell(0, 5, pulisci_testo_pdf("Lavoro comprensivo di smontaggio, smaltimento e montaggio completo dei serramenti,"), ln=True, align="L")
    pdf.set_font("Arial", "U", 8)
    pdf.cell(0, 5, pulisci_testo_pdf("inclusa rifinitura finale in opera eseguita a regola d'arte."), ln=True, align="L")

    pdf.set_font("Arial", "", 7)
    pdf.cell(0, 5, pulisci_testo_pdf(
        f"Tempi stimati per l'esecuzione dei lavori: circa {mesi} mesi dalla conferma dell'ordine."), ln=True)

    pdf.multi_cell(0, 5, pulisci_testo_pdf(
        "La trasferta sarà valorizzata separatamente in base alla località di installazione "
        "e alla durata stimata della manodopera. Tale voce verrà definita in fase di conferma ordine."
    ))
    pdf.set_font("Arial", "", 7)
    pdf.multi_cell(0, 5, pulisci_testo_pdf(
        "Pagamento: 40% all'accettazione del preventivo e saldo alla consegna.\n\n"))
    pdf.set_font("Arial", "I", 8)
    pdf.multi_cell(0, 5, pulisci_testo_pdf(
        "N.B. L’offerta è da considerarsi indicativa ed è valida per 10 giorni dalla data riportata in calce."
    ))
    pdf.ln(5)

    pdf.set_font("Arial", "B", 8)
    pdf.cell(0, 5, "CONDIZIONI GENERALI DI VENDITA", ln=True)
    pdf.set_font("Arial", "", 7)
    pdf.multi_cell(0, 5, pulisci_testo_pdf(
        "La presente quotazione sarà formalizzata solo previo rilievo misure da parte nostra e, "
        "successivamente, verrà redatta l'offerta finale. "
        "Tutti i lavori saranno eseguiti da posatore installatore certificato senior (EQF3)."
    ))

    # 🔽 Spazio minimo richiesto per firma e intestazione
    spazio_firma = 10

    # 🔄 Se siamo troppo vicini al fondo, vai a nuova pagina
    if pdf.get_y() + spazio_firma > 270:
        pdf.add_page()
        pdf.set_y(240)  # parti da un'altezza comoda nella nuova pagina
    else:
        pdf.ln(5)  # altrimenti, solo un po' di spazio in più

    # 📌 Inserimento firma
    firma_path = os.path.join("static", "immagini", "firma.png")
    x_firma = pdf.w - 55
    y_firma = pdf.get_y() + 5

    # ✅ Inserisci immagine firma se esiste
    if os.path.exists(firma_path):
        pdf.image(firma_path, x=x_firma, y=y_firma, w=40)

    # ✍️ Testi a lato firma
    x_testo = x_firma - 15
    y_testo = y_firma + 5  # posizione iniziale sotto la firma

    pdf.set_xy(x_testo, y_testo)
    pdf.set_font("Arial", "B", 7)
    pdf.cell(0, 5, "FIRMA", ln=True, align="R")

    # Riga successiva con spazio maggiore
    pdf.set_xy(x_testo, y_testo + 7)  # 7 invece di 4 per evitare accavallamento
    pdf.set_font("Arial", "I", 7)
    pdf.cell(0, 5, "INFISSI di MICHELE AMERICO", ln=True, align="R")


    # Seconda pagina: Specifiche tecniche
    pdf.set_xy(10, pdf.get_y() + 15)  # Sposta leggermente più in basso e a sinistra
    pdf.set_font("Arial", "B", 9)
    pdf.cell(0, 5, "Scheda Tecniche", ln=True, align="L")
    pdf.ln(5)  # Spazio dopo il titolo


    # Imposta intestazione tabella
    pdf.set_font("Arial", "B", 8)
    pdf.cell(95, 8, "Caratteristica", border=1)
    pdf.cell(95, 8, "Valore", border=1, ln=True)

    # 🔄 Carica valori tecnici dinamici
    with open("valori_tecnici.json", "r") as f:
        valori_tecnici = json.load(f)

    # Prendi il primo infisso come riferimento per materiale e vetro
    tipo_materiale = articoli[0].get("tipo_serramento", "PVC").capitalize()
    tipo_vetro = "vetro_" + articoli[0].get("tipo_vetro", "doppio")

    valori = valori_tecnici.get(tipo_materiale, {})
    vetro = valori.get(tipo_vetro, {})

    # Default di fallback
    uw = vetro.get("Uw", "1.2")
    acustica = vetro.get("acustica", "35")
    aria = valori.get("aria", "Classe 4")
    acqua = valori.get("acqua", "E750")
    vento = valori.get("vento", "C4")

    zona_climatica = get_zona_climatica(cliente.get("citta", ""))
    requisito_uw = None
    conforme = None
    
    if zona_climatica:
        with open("zone_climatiche.json", "r") as f:
            zone_data = json.load(f)
        requisito_uw = zone_data.get(zona_climatica, {}).get("Uw_minimo")
        if requisito_uw:
            conforme = float(uw) <= float(requisito_uw)


    pdf.set_font("Arial", "", 8)
    righe = [
        ("Profondità telaio", "76 mm"),
        ("Profondità anta", "80 mm"),
        ("Fermavetro", "Arrotondato o squadrato"),
        ("Offset", "gradino"),
        ("Altezza battuta telaio", "25 mm"),
        ("Spessore battuta telaio-anta", "9 mm"),
        ("Spessori vetro fino a", "55 mm"),
        ("Sistema guarnizioni", "Tripla guarnizione"),
        ("Trasmittanza nodo fino a", "Uf=1,0W/m²K"),
        ("Resistenza al fuoco", "Classe EI30 secondo EN 13501-2"),
        ("Portate cerniere fino a", "130 kg"),
        ("Trasmittanza termica serramento fino a", f"Uw={uw}W/m²K"),
        ("Permeabilità all’aria fino a", aria),
        ("Tenuta all’acqua fino a", acqua),
        ("Resistenza al vento fino a", vento),
        ("Antieffrazione fino a", "RC3"),
        ("Abbattimento acustico fino a", f"{acustica} dB"),
    ]
    if requisito_uw:
        righe.append(("Uw minimo richiesto in zona " + zona_climatica, f"{requisito_uw} W/m²K"))

    if requisito_uw:
        conforme = float(uw) <= float(requisito_uw)
        sstato = "[✓] Conforme al requisito di trasmittanza della tua zona climatica" if conforme else "[X] NON conforme al requisito di trasmittanza della tua zona climatica"
        righe.append(("Verifica trasmittanza", sstato))
    
    # Scrittura tabella tecnica
    for caratteristica, valore in righe:
        pdf.cell(95, 8, pulisci_testo_pdf(caratteristica), border=1)
        pdf.cell(95, 8, pulisci_testo_pdf(valore), border=1, ln=True)


    # 🔽 ORA calcola lo spazio rimasto
    img_pellicole = os.path.join("static", "immagini", "struttura.jpg")
    if os.path.exists(img_pellicole):
        altezza_immagine = 90
        spazio_disponibile = 297 - pdf.get_y() - 10

        if spazio_disponibile >= altezza_immagine:
            pdf.image(img_pellicole, x=20, y=pdf.get_y() + 10, w=180)

    os.makedirs("preventivi", exist_ok=True)
    filepath = os.path.join("preventivi", f"preventivo_{numero_preventivo}.pdf")
    pdf.output(filepath)

    if os.path.exists(filepath):
        print(f"[📧 Invio] Invio email a {cliente['email']} con allegato {filepath}")
        invia_email(cliente["email"], filepath, numero_preventivo)
    else:
        print(f"[❌] PDF non generato correttamente per {cliente['email']}")

    return {
        "uw": uw,
        "zona_climatica": zona_climatica,
        "requisito_uw": requisito_uw,
        "conforme": conforme
    }
    # Elimina le immagini generate nella cartella temporanea
    import glob
    for img_path in glob.glob(f"static/immagini_generati/infisso_{cliente['email'].split('@')[0]}_*.png"):
        try:
            os.remove(img_path)
        except Exception as e:
            print(f"Errore nella rimozione di {img_path}: {e}")


import smtplib, ssl
from email.message import EmailMessage
import os

def invia_email(cliente_email, allegato_path, numero_preventivo):
    msg = EmailMessage()
    msg["Subject"] = f"Preventivo infissi n. {numero_preventivo}"
    msg["From"] = "noreply@bit4k.com"
    msg["To"] = cliente_email
    msg["Cc"] = "falegnameriaamerico@tiscali.it"
    msg.set_content("""\
Gentile Cliente,

in allegato trova il **preventivo indicativo** relativo alla sua richiesta di cambio serramenti interni.

Le consigliamo di **conservare il numero di preventivo riportato nell’oggetto**, in quanto sarà necessario per l'elaborazione del preventivo definitivo.

Eventuali **accessori, persiane o zanzariere aggiuntive** potranno essere inserite nell’offerta finale, se richiesto.

❗ La preghiamo di **non rispondere a questa email**.  
Per chiarimenti o modifiche, può contattarci telefonicamente o all’indirizzo email indicato in calce.

Cordiali saluti,

INFISSI – MOBILIFICIO E FALEGNAMERIA MICHELE AMERICO  
📍 Showroom Rocchetta Sant’Antonio – Cell. 333.4352383  
📍 Showroom Montefalcione (AV) – Cell. 389.9686594  
📧 Email: falegnameriaamerico@tiscali.it
""")

    with open(allegato_path, "rb") as f:
        file_data = f.read()
        file_name = os.path.basename(allegato_path)
        msg.add_attachment(file_data, maintype="application", subtype="pdf", filename=file_name)

    # Connessione con SSL Aruba
    context = ssl.create_default_context()

    with smtplib.SMTP_SSL("smtps.aruba.it", 465, context=context) as smtp:
        smtp.login("noreply@bit4k.com", "Michele1975!")
        smtp.send_message(msg)

from PIL import Image, ImageDraw, ImageFont

def ridimensiona_immagine_infisso(larghezza_mm, altezza_mm, path_input, session_id, numero, con_quote=False):
    try:
        img = Image.open(path_input).convert("RGB")

        rapporto = altezza_mm / larghezza_mm
        base = 150

        if rapporto > 1.5:
            nuova_larghezza = int(base * 0.6)
            nuova_altezza = int(base * 1.8)
        elif rapporto < 0.75:
            nuova_larghezza = int(base * 1.8)
            nuova_altezza = int(base * 0.6)
        else:
            nuova_larghezza = base
            nuova_altezza = base

        img = img.resize((nuova_larghezza, nuova_altezza), Image.LANCZOS)

        os.makedirs("static/immagini_generati", exist_ok=True)
        nome_file = f"infisso_{session_id}_{numero}.png"
        path_output = os.path.join("static/immagini_generati", nome_file)

        if not con_quote:
            img.save(path_output, format="PNG")
            return os.path.join("static", "immagini_generati", nome_file).replace("\\", "/")

        # Altrimenti: aggiungi quote su canvas più grande
        canvas_w = nuova_larghezza + 80
        canvas_h = nuova_altezza + 80
        canvas = Image.new("RGB", (canvas_w, canvas_h), "white")
        draw = ImageDraw.Draw(canvas)

        x_offset = (canvas_w - nuova_larghezza) // 2
        y_offset = (canvas_h - nuova_altezza) // 2
        canvas.paste(img, (x_offset, y_offset))

        # Font
        try:
            font = ImageFont.truetype("arial.ttf", 14)
        except IOError:
            font = ImageFont.load_default()

        # Larghezza (sotto)
        x_start = x_offset
        x_end = x_offset + nuova_larghezza
        y_line = y_offset + nuova_altezza + 10
        draw.line([(x_start, y_line), (x_end, y_line)], fill="black", width=1)
        draw.line([(x_start, y_line - 3), (x_start, y_line + 3)], fill="black")
        draw.line([(x_end, y_line - 3), (x_end, y_line + 3)], fill="black")
        draw.text(((x_start + x_end) // 2 - 20, y_line + 5), f"{larghezza_mm} mm", fill="black", font=font)

        # Altezza (a destra)
        y_start = y_offset
        y_end = y_offset + nuova_altezza
        x_line = x_offset + nuova_larghezza + 10
        draw.line([(x_line, y_start), (x_line, y_end)], fill="black", width=1)
        draw.line([(x_line - 3, y_start), (x_line + 3, y_start)], fill="black")
        draw.line([(x_line - 3, y_end), (x_line + 3, y_end)], fill="black")
        draw.text((x_line + 5, (y_start + y_end) // 2 - 7), f"{altezza_mm} mm", fill="black", font=font)

        # Salva con quote
        canvas.save(path_output, format="PNG")

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
            "telefono": request.form["telefono"],
            "indirizzo": request.form["indirizzo"],
            "citta": request.form["citta"].strip().title(),
            "data": request.form["data"]
        }
        os.makedirs("sessione", exist_ok=True)
        with open(f"sessione/cliente_{session_id}.json", "w") as f:
            json.dump(cliente, f)
        return redirect(f"/articolo/1?session={session_id}")
    return render_template("index.html", data_oggi=oggi)


def determina_categoria(effetto):
    effetto = effetto.lower()

    if any(x in effetto for x in [
        "legno", "golden oak", "noce", "douglasie", "oak", "af", "ac", "shogun",
        "mooreiche", "eiche", "bergkiefer", "mahagoni", "rosso", "braun", "hell"
    ]):
        return "noce"

    elif any(x in effetto for x in [
        "ral 6001", "verde", "ral6001"
    ]):
        return "RAL6001"

    elif any(x in effetto for x in [
        "ral 1018", "giallo", "ral1018"
    ]):
        return "RAL1018"

    elif any(x in effetto for x in [
        "ral 9001", "crema", "ral9001"
    ]):
        return "RAL9001"

    elif any(x in effetto for x in [
        "ral 3002", "ral 3003", "ral 3005", "ral 3011", "rosso rubino", "rosso vino", "ral3002", "ral3003", "ral3005", "ral3011"
    ]):
        return "RAL3002"

    elif any(x in effetto for x in [
        "ral 7016", "ral 9005", "grigio scuro", "antracite", "scuro", "black", "nero",
        "earl", "quarz", "crown", "metbrush", "db703", "7016", "9005"
    ]):
        return "scuro"

    return "bianca"


@app.route("/articolo/<int:n>", methods=["GET", "POST"])
def articolo(n):
    session_id = request.args.get("session")
    modifica = request.args.get("modifica") == "1"

    os.makedirs("sessione", exist_ok=True)
    lista_file = f"sessione/articoli_{session_id}.json"
    articoli = []

    # Carica gli articoli esistenti
    if os.path.exists(lista_file):
        with open(lista_file, "r") as f:
            articoli = json.load(f)

    articolo_da_modificare = {}
    if modifica and n - 1 < len(articoli):
        articolo_da_modificare = articoli[n - 1]

    if request.method == "POST":
        effetto = request.form.get("effetto_pellicolato", "")
        categoria = determina_categoria(effetto)
        ante = request.form.get("numero_ante", "2")
        modello = "singola" if ante == "1" else "doppia" if ante == "2" else "tripla"

        # 🔍 Cerca immagine base con estensione .jpg o .png
        immagine_base = None
        for ext in [".jpg", ".png"]:
            possibile = f"static/immagini/finestra_{modello}_{categoria}{ext}"
            if os.path.exists(possibile):
                immagine_base = possibile
                break

        # 🧹 Rimuove immagine generata vecchia per assicurare aggiornamento
        path_vecchia = os.path.join("static", "immagini_generati", f"infisso_{session_id}_{n}.png")
        if os.path.exists(path_vecchia):
            os.remove(path_vecchia)

        # 🖼️ Genera nuova immagine se possibile, altrimenti fallback
        if immagine_base:
            immagine_output = ridimensiona_immagine_infisso(
                float(request.form["larghezza"]),
                float(request.form["altezza"]),
                immagine_base,
                session_id,
                n
            )
        else:
            immagine_output = "static/immagini/finestra_doppia_bianca.jpg"

        # 🔁 Percorso relativo per HTML
        immagine_rel = immagine_output.replace("static/", "") if immagine_output else None

        articolo = {
            "descrizione": request.form["descrizione"],
            "larghezza": int(float(request.form["larghezza"])),
            "altezza": int(float(request.form["altezza"])),
            "vasistas": request.form.get("vasistas", "n"),
            "cassonetti": request.form.get("cassonetti", "n"),
            "avvolgibili": request.form.get("avvolgibili", "n"),
            "rullo": request.form.get("rullo", "n"),
            "pellicolato": request.form.get("pellicolato", "n"),
            "effetto_pellicolato": effetto,
            "accessori": request.form.get("accessori", ""),
            "costo_accessori": 0,
            "quantita": int(request.form["quantita"]),
            "spessore": int(float(request.form["spessore"])),
            "tipo_vetro": request.form.get("tipo_vetro", "doppio"),
            "numero_ante": ante,
            "tipo_serramento": request.form.get("tipo_serramento", "pvc"),
            "immagine": immagine_rel
        }

        # Salvataggio/modifica articolo
        if modifica and n - 1 < len(articoli):
            articoli[n - 1] = articolo
        else:
            articoli.append(articolo)

        with open(lista_file, "w") as f:
            json.dump(articoli, f)

        azione = request.form["azione"]
        if azione == "continua":
            return redirect(f"/articolo/{len(articoli)+1}?session={session_id}")
        else:
            return redirect(f"/conferma?session={session_id}")

    return render_template("articolo.html",
                           numero=n,
                           totale=len(articoli),
                           articolo=articolo_da_modificare,
                           articoli=articoli,
                           session_id=session_id)


@app.route("/conferma", methods=["GET", "POST"])
def conferma():
    session_id = request.args.get("session")

    if not session_id:
        return "<h1>Sessione non valida</h1><p>Torna alla <a href='/'>home</a> per ricominciare il preventivo.</p>", 400

    try:
        with open(f"sessione/cliente_{session_id}.json") as f:
            cliente = json.load(f)
        with open(f"sessione/articoli_{session_id}.json") as f:
            articoli = json.load(f)
    except FileNotFoundError:
        return "<h1>Sessione scaduta o non trovata</h1><p>I dati non sono disponibili. Torna alla <a href='/'>home</a> per iniziare un nuovo preventivo.</p>", 404

    # Calcola sconto
    prezzi = carica_prezzi()
    imponibile = 0
    for a in articoli:
        prezzo_unitario, _ = calcola_prezzo_mq(
            a["larghezza"],
            a["altezza"],
            prezzi.get(f"vetro_{a.get('tipo_vetro', 'doppio')}", prezzi["vetro_doppio"])
        )
        imponibile += prezzo_unitario * a["quantita"]
    totale_pezzi = sum(a["quantita"] for a in articoli)
    sconto_percentuale, sconto_valore = calcola_sconto_migliore(imponibile, totale_pezzi, prezzi)
    sconto_valore = round(sconto_valore, 2)

    if request.method == "POST":
        numero_preventivo = genera_numero_preventivo()
        filename = f"Preventivo_{numero_preventivo}.pdf"
        filepath = os.path.join("preventivi", filename)
        os.makedirs("preventivi", exist_ok=True)

        try:
            info_tecniche = genera_pdf(cliente, articoli, filepath, numero_preventivo)

            os.remove(f"sessione/cliente_{session_id}.json")
            os.remove(f"sessione/articoli_{session_id}.json")

            return render_template(
                "conferma.html",
                success=True,
                file=filename,
                session_id=session_id,
                info_tecniche=info_tecniche,
                sconto_valore=sconto_valore,
                sconto_percentuale=sconto_percentuale
            )
        except Exception as e:
            return f"<h1>Errore nella generazione del PDF</h1><p>{e}</p>", 500

    # GET: Riepilogo prima della conferma
    return render_template(
        "conferma.html",
        cliente=cliente,
        articoli=articoli,
        success=False,
        session_id=session_id,
        sconto_valore=sconto_valore,
        sconto_percentuale=sconto_percentuale
    )




import os
from PIL import Image, ImageDraw, ImageFont

import os
from PIL import Image, ImageDraw, ImageFont


@app.route("/download/<filename>")
def download(filename):
    # Costruisci il path assoluto
    path = os.path.abspath(os.path.join("preventivi", filename))
    
    # Verifica che sia effettivamente in quella directory (security fix)
    if not os.path.exists(path) or not path.startswith(os.path.abspath("preventivi")):
        return f"File {filename} non trovato", 404

    return send_file(path, as_attachment=True, mimetype="application/pdf")


@app.route("/prezzi", methods=["GET", "POST"])
def prezzi_view():
    prezzi_file = "prezzi.json"

    if request.method == "POST":
        with open(prezzi_file, "r") as f:
            prezzi = json.load(f)

        for key in request.form:
            try:
                prezzi[key] = float(request.form[key].replace(",", "."))
            except ValueError:
                pass  # ignora valori non validi

        # Imposta i valori di default se non esistono
        prezzi.setdefault("costo_giornata", 150.0)
        prezzi.setdefault("costo_km", 0.5)
        prezzi.setdefault("prezzo_minimo_infisso", 180.0)
        prezzi.setdefault("pellicolato_bicolore_percentuale", 10)

        with open(prezzi_file, "w") as f:
            json.dump(prezzi, f, indent=4)

        return redirect("/prezzi")

    # GET: carica i prezzi e mostra il form
    with open(prezzi_file, "r") as f:
        prezzi = json.load(f)

    # Default se non presenti
    prezzi.setdefault("costo_giornata", 150.0)
    prezzi.setdefault("costo_km", 0.5)
    prezzi.setdefault("prezzo_minimo_infisso", 180.0)

    return render_template("prezzi.html", prezzi=prezzi)

@app.route("/modifica-articoli")
def modifica_articoli():
    session_id = request.args.get("session")
    lista_file = f"sessione/articoli_{session_id}.json"

    if os.path.exists(lista_file):
        with open(lista_file, "r") as f:
            articoli = json.load(f)
        ultimo_n = len(articoli) + 1
    else:
        ultimo_n = 1

    return redirect(f"/articolo/{ultimo_n}?session={session_id}")
from flask import send_from_directory

@app.route('/static/comuni_zona_climatica.json')
def serve_comuni():
    return send_from_directory('web', 'comuni_zona_climatica.json')
