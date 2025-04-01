import os
from datetime import datetime
from fpdf import FPDF
from PIL import Image, ImageDraw, ImageOps

def clear_screen():
    """Pulisce lo schermo in base al sistema operativo."""
    os.system('cls' if os.name == 'nt' else 'clear')

def rimuovi_caratteri_non_supportati(testo):
    """Sostituisce i caratteri Unicode non supportati con caratteri latin-1 compatibili."""
    sostituzioni = {
        '’': "'",
        '“': '"',
        '”': '"',
        '–': '-',  # Dash lungo
        '—': '-'   # Dash em
    }
    for chiave, valore in sostituzioni.items():
        testo = testo.replace(chiave, valore)
    return testo

class PDF(FPDF):
    def header(self):
        # Aggiungi il logo aziendale dall'immagine salvata nella cartella "data"
        logo_path = os.path.join("data", "logo.png")
        if os.path.exists(logo_path):
            self.image(logo_path, 10, 8, 33)  # Posiziona il logo in alto a sinistra
        
        # Aggiungi l'intestazione dal file intestazione.txt a destra del logo
        intestazione_path = os.path.join("data", "intestazione.txt")
        if os.path.exists(intestazione_path):
            with open(intestazione_path, 'r', encoding='utf-8') as f:
                intestazione = f.read()
            intestazione = rimuovi_caratteri_non_supportati(intestazione)
            self.set_xy(50, 8)  # Posiziona l'intestazione accanto al logo a destra
            self.set_font('Arial', '', 10)
            self.multi_cell(0, 8, intestazione)  # Inserisci l'intestazione a destra

        # Spazio per separare l'intestazione dal corpo del preventivo
        self.ln(20)

def ridimensiona_immagine_infisso(larghezza_mm, altezza_mm, immagine_originale, nome_file_output):
    """Ridimensiona dinamicamente l'immagine dell'infisso in base alle dimensioni inserite dall'utente."""
    
    # Carica l'immagine originale
    immagine = Image.open(immagine_originale)
    
    # Ridimensionamento proporzionale in base alle dimensioni in millimetri (1 pixel = 3.78 mm)
    nuova_larghezza_px = int(larghezza_mm * 3.78)
    nuova_altezza_px = int(altezza_mm * 3.78)
    
    # Ridimensiona l'immagine mantenendo le proporzioni
    immagine_ridimensionata = ImageOps.fit(immagine, (nuova_larghezza_px, nuova_altezza_px), method=Image.Resampling.LANCZOS)
    
    # Salva l'immagine ridimensionata
    immagine_ridimensionata.save(os.path.join("immagini", nome_file_output))

def get_input(prompt, allow_back=False):
    """
    Funzione per ottenere l'input dall'utente.
    Se allow_back è True, l'utente può digitare 'back' per tornare indietro.
    """
    while True:
        user_input = input(prompt).strip()
        if allow_back and user_input.lower() == 'back':
            return 'back'
        if user_input == '':
            print("Input non valido. Per favore, riprova.")
        else:
            return user_input

def conferma_dati(dati):
    """Mostra i dati inseriti e chiede conferma all'utente."""
    print("\nRiepilogo dei dati inseriti:")
    for key, value in dati.items():
        print(f"{key}: {value}")
    while True:
        conferma = input("Confermi i dati? (s/n): ").strip().lower()
        if conferma in ['s', 'si']:
            return True
        elif conferma in ['n', 'no']:
            return False
        else:
            print("Input non valido. Digita 's' per confermare o 'n' per tornare indietro.")

def calcola_prezzo_mq(larghezza_mm, altezza_mm, costo_mq=230):
    """Calcola il prezzo dell'infisso in base alla sua area e al costo per metro quadro."""
    larghezza_m = larghezza_mm / 1000  # Converti da millimetri a metri
    altezza_m = altezza_mm / 1000      # Converti da millimetri a metri
    area_mq = larghezza_m * altezza_m  # Calcola l'area in metri quadri
    prezzo = area_mq * costo_mq        # Calcola il prezzo per pezzo
    return round(prezzo, 2), round(area_mq, 2)

def calcola_trasmittanza(d, lambda_materiale):
    """Calcola la trasmittanza termica (U) dell'infisso."""
    R = d / lambda_materiale  # R = d/λ (in m²K/W)
    U = 1 / R                 # U = 1/Rt (in W/m²K)
    return round(U, 2)

def crea_preventivo():
    # Creazione delle cartelle necessarie
    if not os.path.exists("immagini"):
        os.makedirs("immagini")
    
    if not os.path.exists("data"):
        os.makedirs("data")

    # Creazione del PDF
    pdf = PDF()
    pdf.add_page()
    
    # Dizionario per memorizzare i dati inseriti
    dati_cliente = {}
    
    # Inserimento dati del cliente
    while True:
        cliente = get_input("Inserisci il nome del cliente: ", allow_back=False)
        indirizzo = get_input("Inserisci l'indirizzo del cliente: ", allow_back=False)
        
        # Imposta la data di oggi
        data_oggi = datetime.now().strftime('%d/%m/%Y')
        conferma_data = get_input(f"La data sarà impostata su oggi: {data_oggi}. Confermi? (s/n): ").strip().lower()
        if conferma_data == 'n':
            data_preventivo = get_input("Inserisci la data del preventivo (es. 28/09/2024): ", allow_back=False)
        else:
            data_preventivo = data_oggi
        
        dati_cliente = {
            "Cliente": cliente,
            "Indirizzo": indirizzo,
            "Data": data_preventivo
        }
        
        if conferma_dati(dati_cliente):
            break
        else:
            print("Riprova a inserire i dati del cliente.\n")
    
    # Aggiungi dati del cliente più in basso rispetto all'intestazione
    pdf.set_xy(120, 50)  # Posiziona i dati del cliente più in basso rispetto all'intestazione
    pdf.set_font('Arial', '', 12)
    pdf.cell(0, 10, rimuovi_caratteri_non_supportati(f"{dati_cliente['Cliente']}"), ln=True, align='R')
    pdf.cell(0, 10, rimuovi_caratteri_non_supportati(f"{dati_cliente['Indirizzo']}"), ln=True, align='R')
    pdf.cell(0, 10, f'Data: {dati_cliente["Data"]}', ln=True, align='R')
    pdf.ln(10)
    
    # Dettagli del preventivo
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, 'Dettagli Preventivo', ln=True)
    
    # Inserimento articoli
    articoli = []
    totale = 0
    totale_accessori = 0
    lambda_materiale = 0.035  # Valore lambda del materiale (in W/mK), da personalizzare se necessario
    while True:
        try:
            num_articoli = int(get_input("Quanti articoli vuoi inserire? "))
            if num_articoli <= 0:
                print("Il numero di articoli deve essere almeno 1.")
                continue
            break
        except ValueError:
            print("Input non valido. Per favore, inserisci un numero intero.")
    
    for i in range(num_articoli):
        print(f"\n--- Inserimento Articolo {i+1} ---")
        while True:
            descrizione = get_input(f"Inserisci la descrizione dell'articolo {i+1} (es. Finestra, Porta): ", allow_back=True)
            if descrizione == 'back':
                if i == 0:
                    print("Non puoi tornare indietro. Sei al primo articolo.")
                    continue
                else:
                    i -= 2  # Torna all'articolo precedente
                    if i < -1:
                        i = -1
                    break
            
            try:
                larghezza = float(get_input(f"Inserisci la larghezza dell'articolo {i+1} (mm): ", allow_back=True))
            except ValueError:
                print("Input non valido. Per favore, inserisci un numero.")
                continue
            if larghezza == 'back':
                if i == 0:
                    print("Non puoi tornare indietro. Sei al primo articolo.")
                    continue
                else:
                    i -= 2  # Torna all'articolo precedente
                    if i < -1:
                        i = -1
                    break
            
            try:
                altezza = float(get_input(f"Inserisci l'altezza dell'articolo {i+1} (mm): ", allow_back=True))
            except ValueError:
                print("Input non valido. Per favore, inserisci un numero.")
                continue
            if altezza == 'back':
                if i == 0:
                    print("Non puoi tornare indietro. Sei al primo articolo.")
                    continue
                else:
                    i -= 2  # Torna all'articolo precedente
                    if i < -1:
                        i = -1
                    break

            # Chiedi se ci sono i cassonetti
            cassonetti = get_input("Ci sono i cassonetti? (s/n): ").lower()
            if cassonetti == 's':
                prezzo_cassonetti = 130
                totale_accessori += prezzo_cassonetti
                descrizione += " - Con cassonetti"

            # Chiedi se aggiungere gli avvolgibili
            avvolgibili = get_input("Aggiungere avvolgibili? (s/n): ").lower()
            if avvolgibili == 's':
                prezzo_avvolgibili = 35 * (larghezza / 1000) * (altezza / 1000)  # Costo in base ai mq
                totale_accessori += prezzo_avvolgibili
                descrizione += f" - Avvolgibili ({prezzo_avvolgibili:.2f} EUR)"

            # Chiedi se aggiungere il rullo calotta della puleggia
            rullo_calotta = get_input("Aggiungere rullo calotta della puleggia? (s/n): ").lower()
            if rullo_calotta == 's':
                prezzo_rullo = 40
                totale_accessori += prezzo_rullo
                descrizione += f" - Rullo calotta ({prezzo_rullo:.2f} EUR)"
            
            # Chiedi se l'infisso sarà pellicolato
            pellicolato = get_input("L'infisso sarà pellicolato? (s/n): ").lower()
            prezzo_unitario, area_mq = calcola_prezzo_mq(larghezza, altezza)
            
            if pellicolato == 's':
                prezzo_unitario *= 1.2  # Aggiungi il 20% al prezzo unitario se pellicolato
                effetto_pellicolato = get_input("Inserisci l'effetto della pellicolatura (es. effetto legno): ")
                descrizione += f" - Pellicolato ({effetto_pellicolato})"
            
            # Chiedi se ci sono altri accessori
            accessori = get_input("Inserisci eventuali accessori (se non ce ne sono, lascia vuoto): ")
            if accessori:
                descrizione += f" - Accessori: {accessori}"
                # Chiedi il costo degli accessori
                try:
                    costo_accessori = float(get_input("Inserisci il costo dell'accessorio (senza IVA): "))
                    totale_accessori += costo_accessori
                except ValueError:
                    print("Input non valido. Per favore, inserisci un numero valido.")
            
            try:
                quantita = int(get_input(f"Inserisci la quantità dell'articolo {i+1}: ", allow_back=True))
            except ValueError:
                print("Input non valido. Per favore, inserisci un numero intero.")
                continue
            if quantita == 'back':
                if i == 0:
                    print("Non puoi tornare indietro. Sei al primo articolo.")
                    continue
                else:
                    i -= 2  # Torna all'articolo precedente
                    if i < -1:
                        i = -1
                    break
            
            # Riepilogo articolo
            dati_articolo = {
                "Descrizione": descrizione,
                "Larghezza (mm)": larghezza,
                "Altezza (mm)": altezza,
                "Area (mq)": round(area_mq, 2),
                "Prezzo unitario (EUR)": f"{prezzo_unitario:.2f}",
                "Quantità": quantita,
                "Totale (EUR)": f"{prezzo_unitario * quantita:.2f}"
            }
            
            # Calcola la trasmittanza termica
            spessore = float(get_input("Inserisci lo spessore dell'infisso in mm (es. 50): "))
            trasmittanza = calcola_trasmittanza(spessore / 1000, lambda_materiale)
            dati_articolo["Trasmittanza (U)"] = f"{trasmittanza:.2f} W/m²K"
            
            print("\nRiepilogo Articolo Inserito:")
            for key, value in dati_articolo.items():
                print(f"{key}: {value}")
            conferma = get_input("Confermi l'articolo? (s/n): ").strip().lower()
            if conferma in ['s', 'si']:
                articoli.append(dati_articolo)
                totale += float(dati_articolo["Totale (EUR)"])
                
                # Ridimensiona l'immagine dell'infisso
                nome_immagine_output = f"finestra_{i+1}.png"
                ridimensiona_immagine_infisso(larghezza, altezza, os.path.join("immagini", "finestra.png"), nome_immagine_output)
                
                break
            elif conferma in ['n', 'no']:
                print("Riprova a inserire i dati dell'articolo.\n")
            else:
                print("Input non valido. L'articolo non è stato confermato.\n")
        
    # Inserimento degli articoli nel PDF in formato tabella centrata
    for idx, articolo in enumerate(articoli, 1):
        pdf.set_font('Arial', '', 12)  # Rimuovi il grassetto dalla descrizione
        
        # Aggiungi descrizione dell'articolo come titolo al posto di "Articolo X"
        pdf.cell(0, 10, rimuovi_caratteri_non_supportati(articolo["Descrizione"]), ln=True, align='L')  # Sposta a sinistra

        # Inizio della tabella con immagine e informazioni
        pdf.cell(60, 10, '', ln=0)  # Cell vuota per bilanciare la tabella a sinistra
        pdf.cell(130, 10, '', ln=1)  # Cell vuota per riempire la tabella

        # Aggiungi immagine dell'infisso (colonna sinistra)
        immagine_path = os.path.join("immagini", f"finestra_{idx}.png")
        if os.path.exists(immagine_path):
            pdf.image(immagine_path, x=20, y=pdf.get_y(), w=50, h=50)  # Sposta l'immagine a sinistra

        # Aggiungi descrizione e dimensioni (colonna destra)
        pdf.set_xy(80, pdf.get_y())  # Sposta il puntatore verso sinistra
        pdf.multi_cell(0, 10, rimuovi_caratteri_non_supportati(f'Dimensioni: {articolo["Larghezza (mm)"]} mm x {articolo["Altezza (mm)"]} mm\n'
                                                              f'Area: {articolo["Area (mq)"]} mq\n'
                                                              f'Prezzo unitario: {articolo["Prezzo unitario (EUR)"]} EUR\n'
                                                              f'Quantità: {articolo["Quantità"]}\n'
                                                              f'Totale: {articolo["Totale (EUR)"]} EUR\n'
                                                              f'Trasmittanza (U): {articolo["Trasmittanza (U)"]}'))
        pdf.ln(10)  # Lascia spazio sotto per il prossimo articolo
    
    # Calcolo e inserimento del totale preventivo (imponibile, IVA e totale)
    imponibile = totale + totale_accessori
    iva = imponibile * 0.10
    totale_con_iva = imponibile + iva
    
    # Totale generale (imponibile, IVA, totale)
    pdf.ln(10)
    pdf.set_font('Arial', '', 12)
    pdf.cell(0, 10, f'Imponibile: {imponibile:.2f} EUR', ln=True)
    pdf.cell(0, 10, f'IVA 10%: {iva:.2f} EUR', ln=True)
    pdf.set_font('Arial', 'B', 12)  # Totale in grassetto
    pdf.cell(0, 10, f'Totale: {totale_con_iva:.2f} EUR', ln=True)
    
    # Aggiungi informazioni e firme alla fine dell'ultima pagina
    pdf.ln(10)
    pdf.set_font('Arial', '', 12)

    # Leggi le informazioni aggiuntive dal file 'fondo.txt'
    fondo_path = os.path.join("data", "fondo.txt")
    if os.path.exists(fondo_path):
        with open(fondo_path, 'r', encoding='utf-8') as f:
            fondo = f.read()
        pdf.multi_cell(0, 10, rimuovi_caratteri_non_supportati(fondo))  # Inserisci le informazioni in fondo alla pagina

    # Firma del cliente
    pdf.cell(0, 10, 'Il Cliente', ln=True, align='L')
    pdf.cell(0, 10, '______________________________', ln=True, align='L')

    # Inserisci firma del titolare in basso a destra
    firma_path = os.path.join("data", "firma.png")
    if os.path.exists(firma_path):
        pdf.image(firma_path, x=150, y=pdf.get_y(), w=40)  # Firma in basso a destra

    # Salva il PDF
    nome_file = f"preventivo_{dati_cliente['Cliente'].replace(' ', '_')}.pdf"
    pdf.output(nome_file)
    print(f"\nPreventivo creato: {nome_file}")

if __name__ == "__main__":
    while True:
        # Pulisci lo schermo all'inizio dello script
        clear_screen()
        
        print("Benvenuto nel Generatore di Preventivi per Infissi\n")
        
        crea_preventivo()
        
        # Chiedi all'utente se vuole ripetere il processo
        while True:
            ripeti = input("\nVuoi creare un altro preventivo? (s/n): ").strip().lower()
            if ripeti in ['n', 'no']:
                print("Grazie per aver utilizzato il generatore di preventivi. Uscita in corso...")
                sys.exit()  # Esci dal programma
            elif ripeti in ['s', 'si']:
                break  # Torna all'inizio e ripeti

# Funzione per generare PDF
from fpdf import FPDF

def genera_pdf(cliente, articoli, filepath):
    pdf = PDF()
    pdf.add_page()

    # Logo in alto al centro
    logo_path = os.path.join("immagini", "logo.jpg")
    if os.path.exists(logo_path):
        pdf.image(logo_path, x=60, y=10, w=90)
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

        prezzo_unitario, area = calcola_prezzo_mq(a["larghezza"], a["altezza"], prezzi["prezzo_mq"])
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
