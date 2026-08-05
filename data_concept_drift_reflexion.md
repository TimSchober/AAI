# Reflexion: Data/Concept Drift im Job-Such-Agenten

## Wo im System Drift überhaupt entstehen kann

Der Agent stützt sich auf drei unterschiedliche Datenquellen, die jeweils ihre eigene
Drift-Charakteristik haben:

1. **Live-Daten von außen**: Der `JobsucheClient` fragt laufend die REST-API der
   Bundesagentur für Arbeit ab (`core_functions/arbeitsagentur_jobsuche_API_jobs_client.py`).
   Diese Quelle liegt vollständig außerhalb unserer Kontrolle.
2. **Ein Vektorindex, der nur wächst**: Jede Suche über `search_jobs` schreibt die
   gefundenen Stellen automatisch in ChromaDB (`JobApplicationStore.add_jobs`,
   `core_functions/rag_store.py`). Es gibt keinen TTL- oder Ablauf-Mechanismus – einmal
   gespeicherte Angebote bleiben dauerhaft durchsuchbar, auch wenn sie längst offline sind.
3. **Ein statisches Nutzerprofil**: Lebenslauf, Präferenzen und Zeugnisse werden nur
   einmalig und manuell über `ingest.py` eingelesen (im Code selbst als
   "TODO: Automate in the future and remove this helper" markiert). Ändert sich der
   Nutzer (neue Skills, neuer Wohnort, andere Präferenzen), merkt das System das nicht,
   solange niemand erneut ingestet.

## Data Drift: Wenn sich die Eingabeverteilung verschiebt

**Auf der Jobangebots-Seite** ändert sich das Vokabular des Arbeitsmarkts kontinuierlich –
neue Berufsbezeichnungen (z.B. "Prompt Engineer"), neue Abkürzungen, veränderte
Formatierung der API-Felder. Das Embedding-Modell `all-MiniLM-L6-v2`
(`config.py`, `EMBED_MODEL`) ist ein fixes, eingefrorenes Modell und – laut Kommentar im
Code selbst – nicht speziell für Deutsch optimiert (Alternative
`paraphrase-multilingual-MiniLM-L12-v2` wird explizit als Option genannt, aber nicht
verwendet). Verschiebt sich die Sprache der Stellenanzeigen weiter weg vom
Trainingskorpus des Embedding-Modells, sinkt die semantische Trennschärfe der Vektoren
schleichend, ohne dass der Code sich ändert.

Zusätzlich ist die API-Antwortstruktur eine Blackbox Dritter. `_extract_ort` und
`_extract_arbeitszeit` (`arbeitsagentur_jobsuche_API_jobs_client.py`) enthalten bereits
Fallback-Logik für fehlende Felder – ein Hinweis darauf, dass sich das Antwortformat schon
einmal geändert hat oder uneinheitlich ist. Ändert die Bundesagentur ihr Schema erneut,
fallen Felder still auf leere Strings zurück, statt einen Fehler zu werfen.

**Auf der Nutzerprofil-Seite** ist das Drift-Risiko umgekehrt: Nicht die Daten verändern
sich unbemerkt, sondern die Realität läuft dem eingefrorenen Snapshot davon. Der
gespeicherte Lebenslauf wird mit jeder Woche "älter" relativ zum tatsächlichen
Kenntnisstand des Nutzers.

## Concept Drift: Wenn sich "passend" verschiebt

Selbst bei stabilen Daten kann sich der *Zusammenhang* zwischen Sucheingabe und
gewünschtem Ergebnis ändern. Was für einen Nutzer vor drei Monaten ein "guter Match" war
(z.B. Vollzeit, Präsenz, bestimmter Radius), kann sich durch geänderte Lebensumstände
verschieben – das System erkennt das nicht, weil `praeferenz`-Dokumente in ChromaDB nicht
automatisch neu bewertet werden. Ebenso verschiebt sich der Arbeitsmarkt selbst: Gehälter,
Remote-Anteil oder gefragte Skills folgen Trends, die weder im LLM (lokal, statisch,
`qwen3.5:4b` über Ollama) noch im Systemprompt (`agents/job_search_agent.py`)
nachgebildet werden.

## Was im Betrieb konkret auffallen würde

- **Sinkende Relevanz-Scores beim Retrieval**: `JobApplicationStore.query()` gibt für
  jeden Treffer bereits einen Cosine-Similarity-`score` zurück. Ein schleichender Abfall
  der durchschnittlichen Scores über die Zeit wäre ein direktes, messbares Signal für
  Embedding-/Vokabular-Drift.
- **Mehr leere Pflichtfelder** in den Job-Objekten (Ort, Arbeitszeit) durch
  API-Formatänderungen – erkennbar an ungewöhnlich vielen leeren Strings in den
  gespeicherten Metadaten.
- **Vorschläge, die am Nutzer vorbeigehen**, obwohl das Retrieval technisch "korrekt"
  funktioniert – weil `praeferenz`/`lebenslauf` im Vektorspeicher veraltet sind.
- **Eine wachsende, nie bereinigte Knowledge Base**: `list_knowledge` würde einen stetig
  steigenden Anteil an `stellenangebot`-Chunks zeigen, von denen ein wachsender Teil
  längst nicht mehr aktive Angebote sind – der Agent könnte abgelaufene Stellen
  empfehlen.
- **In den Phoenix/OpenTelemetry-Traces** (`tracing.py`, bereits instrumentiert über
  `@traced` und `OpenAIInstrumentor`) wären das steigende Tool-Latenzen, mehr leere
  Modellantworten oder ein wachsender Anteil an Turns, in denen das Modell trotz
  Tool-Ergebnissen unpassend oder generisch antwortet – ein indirektes Signal, dass
  Prompt-Erwartungen und tatsächliche Datenrealität auseinanderlaufen.

## Tiefe Reflexion: Was in Production konkret schiefgehen würde

**Die Konfiguration selbst ist bereits gedriftet.** `.env.example` – die Vorlage, die laut
README (`cp .env.example .env`) jede neue Installation kopiert – zeigt
`DOCS_DIR=/Users/tomknittel/Desktop/applied_ai_w4/AAI/ChromaDB/docs`: einen absoluten Pfad
zu einem alten Projektordner ("applied_ai_w4"), der auf keinem anderen Rechner existiert.
Wer die Beispielwerte unreflektiert übernimmt, ingestet entweder gar nichts (Ordner fehlt,
`add_all_documents` iteriert über nichts und meldet keinen Fehler) oder, im schlimmsten
Fall auf einem geteilten Rechner, versehentlich Dateien aus einem völlig anderen Kontext.
Das ist noch vor jedem API- oder Embedding-Drift der erste Bruchpunkt – und er zeigt, wie
leicht Drift nicht in den Daten, sondern in der eigenen Konfiguration entsteht, weil sie
beim Schreiben dieses Dokuments nie gegen eine frische Installation gegengeprüft wurde.

**Die gesamte bisherige Analyse setzt "ein Nutzer, ein Profil, eine Zeitachse" voraus –
und das steht nirgends im Code, sondern nur implizit.** Weder `add_document` noch
`add_jobs` (`rag_store.py`) schreiben ein `user_id`-Feld in die Metadaten, und der
LangGraph-`thread_id` ist in `main.py:97` hart auf den String `"job-search"` fixiert.
Für ein einzelnes lokales CLI-Tool ist das eine bequeme Annahme. Sobald das System aber
mehr als einen Nutzer bedient (z.B. als kleiner Web-Dienst für Kommilitonen), bricht sie
sofort: Lebensläufe, Präferenzen und Konversationsverlauf verschiedener Personen landen in
derselben Collection und demselben Thread. Das wäre kein klassischer Drift-Fall mehr,
sondern eine direkte Folge davon, dass die Drift-Analyse oben – "das Nutzerprofil altert
gegenüber der Realität" – stillschweigend von *einer* Realität ausgeht.

**Persistenz ist asymmetrisch verteilt, und zwar an der falschen Stelle.** Der
`MemorySaver()`-Checkpointer (`agents/job_search_agent.py`) hält den Gesprächsverlauf nur
im Prozessspeicher. Jeder Neustart – Absturz, Update, einfaches Schließen des Terminals –
löscht die komplette Konversation samt gerade genannter, noch nicht ingesteter
Präferenzänderungen. Die ChromaDB-Wissensbasis dagegen bleibt für immer bestehen. In der
Praxis bedeutet das: ausgerechnet der frischeste, potenziell wichtigste Kontext ist am
unzuverlässigsten gespeichert, während veraltete Job-Chunks unbegrenzt überdauern – das
System driftet also aktiv in Richtung des Alten, nicht durch einen Fehler, sondern durch
eine Persistenz-Entscheidung, die nie bewusst getroffen wurde.

**Annahmen, die dieser Reflexion zugrunde liegen:** dass genau ein Nutzer das System
über Zeit benutzt; dass dieser Nutzer sein Profil diszipliniert manuell neu ingestet,
sobald sich etwas ändert; dass die Arbeitsagentur-API strukturell stabil genug bleibt,
damit die vorhandene Fallback-Logik (`_extract_ort`, `_extract_arbeitszeit`) ausreicht;
und dass lokaler Speicherplatz für einen nie bereinigten Vektorindex kein limitierender
Faktor wird. Keine dieser Annahmen ist im Code dokumentiert oder geprüft – sie stecken nur
implizit in den Default-Werten.

**Was man anders hätte machen können:** ein `user_id`-Feld in den Metadaten wäre in einem
Zweizeiler beim ersten Schreiben der `add_document`/`add_jobs`-Signaturen mitgekommen und
hätte spätere Umbauten überflüssig gemacht; `.env.example` hätte einen relativen statt
absoluten Pfad (`./ChromaDB/docs`) verwenden und vor jedem Commit gegen eine frische
Installation getestet werden müssen; der Checkpointer hätte von Anfang an persistent
gewählt werden können (LangGraph bietet mit `SqliteSaver` eine nahezu gleich einfache
Alternative zu `MemorySaver`), damit wenigstens der aktuellste Kontext einen Neustart
übersteht.

## Fazit

Am verwundbarsten ist das System nicht gegenüber dramatischem Drift, sondern gegenüber
**stillem** Drift: Weder die externe API noch das Nutzerprofil noch der Vektorindex haben
einen Mechanismus, der Veralterung aktiv meldet. Ohne ein Verfallsdatum für
Stellenangebote, eine Erinnerung zur Re-Ingestion des Nutzerprofils oder ein Monitoring
der Retrieval-Scores würde Drift ausschließlich indirekt auffallen – über schlechter
werdende, aber weiterhin "plausibel" aussehende Antworten. Am schwersten wiegt dabei, dass
schon die Konfiguration und die impliziten Ein-Nutzer-Annahmen des Systems selbst nie
gegen die Realität eines zweiten Nutzers oder einer zweiten Installation geprüft wurden –
Drift beginnt hier nicht erst im Betrieb, sondern schon im Setup.
