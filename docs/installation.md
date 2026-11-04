# Installatiehandleiding — UC10 Document Anonymizer

Deze handleiding beschrijft hoe je de **UC10 Document Anonymizer** lokaal installeert en beheert op **macOS**, **Linux** en **Windows**.

Het systeem draait **100% lokaal** met ingebouwde spaCy AI-modellen en Docling. Er worden **geen externe cloud API's** aangeroepen, zodat alle documenten, namen en onderzoeksdata volledig privé binnen de organisatie blijven (in overeenstemming met ISO/IEC 27001 en AVG/GDPR).

---

## 1. Systeemvereisten

1. **Docker & Docker Compose:**
   - **macOS:** [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop) (werkt op zowel Apple Silicon M1/M2/M3/M4 als Intel x86_64).
   - **Linux:** Docker Engine & Docker Compose v2 plugin (`sudo apt install docker.io docker-compose-v2` op Debian/Ubuntu, of `sudo dnf install docker docker-compose-plugin` op Fedora/RHEL).
   - **Windows:** [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop) met WSL2 backend ingeschakeld.
2. **Geheugen (RAM):**
   - Minimaal **6 GB RAM** toegewezen aan Docker (gemeten: de stack gebruikt ~4 GB in rust; de anonymizer alleen mag tot 3 GB). De computer zelf: minimaal 8 GB, liefst 16 GB. Vrije schijfruimte: ~15 GB.
3. **Python (Optioneel, voor native dashboard):**
   - Python 3.10 of nieuwer. *(Niet vereist indien je de volledige Docker Compose stack gebruikt).*

---

## 2. Installatie op macOS & Linux

Open de terminal in de projectmap en voer het installatiescript uit:

```bash
./install.sh
```

### Wat dit script automatisch doet:
1. Controleert of Docker actief is en bereikbaar is.
2. Maakt automatisch een veilige `.env` aan met een uniek cryptografisch Neo4j-wachtwoord.
3. Richt de mappen `input/`, `output/` en `keys/` in met de juiste rechten.
4. Haalt de Docling document parser en Neo4j registry op.
5. Bouwt de `uc10-anonymizer` container met de Nederlandse (`nl_core_news_lg`) en Engelse (`en_core_web_lg`) spaCy-modellen.
6. Start de containers en voert een automatische gezondheidscontrole uit op poort 5010.

---

## 3. Installatie op Windows

1. Zorg dat Docker Desktop actief is (het walvis-icoon in de taakbalk is groen).
2. Dubbelklik op **`install.bat`** of open PowerShell in de projectmap:

```powershell
.\install.ps1
```

Het PowerShell-script configureert de containers, mappen en lokale omgevingsvariabelen automatisch.

---

## 4. De Applicatie Starten & Gebruiken

Er zijn drie eenvoudige manieren om documenten te verwerken:

### Optie A: Volledig via Docker (Aanbevolen voor servers & clean desktops)
Start alle componenten inclusief het dashboard met één Docker-commando:
```bash
docker compose up -d
```
Open vervolgens je browser op:
👉 **[http://localhost:5050](http://localhost:5050)**

### Optie B: Via het Lokale Web Dashboard
```bash
./dashboard.sh
```
*(Op Windows: `python scripts\web_dashboard.py`)*

In het dashboard kun je:
- Documenten (.pdf, .docx, .txt, .md) uploaden via drag-and-drop.
- Optioneel doelbedrijven opgeven die overal (inclusief bronvermeldingen) gemaskeerd moeten worden.
- Met één klik op **▶ SAY GO** documenten anonimiseren.
- Geanonimiseerde bestanden direct inzien en downloaden.
- De interactieve encryptiesleutel bekijken en exporteren naar Excel (CSV met UTF-8 BOM) of JSON.
- Met de knop **"🚀 Nu Bijwerken"** in het tabblad Technical Status met één klik de nieuwste software-versie installeren.

### Optie C: Direct via de Terminal ("SAY GO")
1. Plaats te anonimiseren bestanden in `input/`.
2. Vul optioneel het doelbedrijf in `input/targets.txt`.
3. Voer uit:
```bash
./go.sh
# of her-anonimiseer eerder verwerkte bestanden:
./go.sh --force
```

---

## 5. Overzicht van Lokale Poorten & Services

| Service | Poort | Container | Beschrijving |
|---|---|---|---|
| **Web Dashboard** | `:5050` | `uc10-dashboard` | Windesheim Research interactieve interface & file manager |
| **UC10 Anonymizer** | `:5010` | `uc10-anonymizer` | Presidio + spaCy NL/EN FastAPI service (BSN 11-proof) |
| **Docling Parser** | `:5001` | `uc10-docling` | PDF & Word naar gestructureerde markdown met lay-out behoud |
| **Neo4j Registry** | `:7687` / `:7474` | `uc10-neo4j` | Globale consistente pseudoniemen over meerdere documenten |

---

## 6. Het Systeem Bijwerken (One-Click Update)

### Via de Web Interface
1. Ga in het dashboard naar het tabblad **Technical Status**.
2. Klik in de kaart **📦 Systeem & Versiebeheer** op de knop **"🚀 Nu Bijwerken (One-Click Update)"**.
3. Het systeem haalt automatisch de nieuwste Git-commits op en herstart de Docker containers zonder dataverlies.

### Handmatig via Terminal
```bash
git pull --rebase
docker compose up -d --build
```

---

## 7. Probleemoplossing (Troubleshooting)

- **Docker daemon is niet actief:**
  Zorg dat Docker Desktop draait voordat je `./install.sh` of `./dashboard.sh` start.
- **Out of Memory (OOM):**
  Als een container crasht tijdens het laden van de spaCy-modellen, verhoog dan het werkgeheugen in Docker Desktop > Settings > Resources naar minimaal **4 GB**.
- **macOS Apple Silicon (M1/M2/M3/M4):**
  Docker Desktop voor Mac gebruikt automatisch de Rosetta 2 of native arm64 emulatie. Zorg dat *Use Virtualization framework* aan staat in de instellingen.
- **Logs inzien:**
  ```bash
  docker compose logs -f uc10-anonymizer
  docker compose logs -f uc10-dashboard
  ```
