# preferenze_roma

Sito statico e script per costruire mappe interattive delle preferenze elettorali a Roma, a partire dai dati presenti nel repository.

## Struttura

- `scripts/build_preference_maps.py`: generatore principale delle mappe e dei CSV di riepilogo.
- `notebooks/pd_roma_maps.ipynb`: notebook storico del progetto.
- `docs/index.html`: pagina pronta per GitHub Pages che incorpora le mappe generate.
- `docs/maps/`: destinazione degli HTML generati.
- `docs/data/`: riepiloghi CSV esportati dal generatore.

## Flusso rapido

1. Installa le dipendenze:

   ```bash
   pip install -r requirements.txt
   ```

2. Esegui `scripts/build_preference_maps.py`.
3. Verifica che siano comparsi i file HTML in `docs/maps/`.
4. Pubblica la cartella `docs/` con GitHub Pages.

## Output previsti

- `docs/maps/roma_pd_comune_2021.html`
- `docs/maps/municipio3_pd_comune_2021.html`
- `docs/maps/municipio3_pd_municipio_2021.html`

Questa versione di prova usa una coropleta sulla somma di `PD` e `Roma Futura` sul totale dei voti di lista. I popup mostrano i voti di coalizione e i voti delle due liste, mentre i layer preferenze sono separati per partito, con il solo `PD` attivo all'avvio e colori distinti per lista.
