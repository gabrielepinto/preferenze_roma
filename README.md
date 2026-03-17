# preferenze_roma

Sito statico e notebook per costruire mappe interattive delle preferenze del Partito Democratico a Roma, a partire dai dati presenti nel repository.

## Struttura

- `notebooks/pd_roma_maps.ipynb`: notebook principale che legge i dati, costruisce le mappe e salva gli HTML.
- `docs/index.html`: pagina pronta per GitHub Pages che incorpora le mappe generate.
- `docs/maps/`: destinazione degli HTML creati dal notebook.
- `docs/data/`: riepiloghi CSV esportati dal notebook.

## Flusso rapido

1. Installa le dipendenze:

   ```bash
   pip install -r requirements.txt
   ```

2. Apri ed esegui `notebooks/pd_roma_maps.ipynb`.
3. Verifica che siano comparsi i file HTML in `docs/maps/`.
4. Pubblica la cartella `docs/` con GitHub Pages.

## Output previsti

- `docs/maps/roma_pd_comune_2021.html`
- `docs/maps/municipio3_pd_comune_2021.html`
- `docs/maps/municipio3_pd_municipio_2021.html`

Le mappe usano una coropleta verde sulla percentuale del PD sul totale dei voti di lista. Nei popup compaiono i voti alla lista PD e la top 10 delle preferenze dei consiglieri per sezione, distinguendo fra elezione comunale e municipale. Il notebook costruisce anche un layer testuale per quartiere con i candidati piu forti aggregati sul quartiere.
