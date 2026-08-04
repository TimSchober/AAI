# Continual Learning – Konzept für den Job-Such-Agenten

## Ausgangslage: Was heute schon "lernt" und was nicht

Das lokale LLM (`qwen3.5:4b` über Ollama, `agents/job_search_agent.py`) und das
Embedding-Modell `all-MiniLM-L6-v2` (`config.py`) sind eingefrorene Gewichte, dadurch hier findet
kein Lernen statt. "Lernfähig" ist im aktuellen System ausschließlich die **Datenschicht**:
`JobApplicationStore` in ChromaDB wächst mit jeder Suche (`add_jobs` in
`core_functions/rag_store.py`), weil `search_jobs` gefundene Stellen automatisch
persistiert. Das ist bereits eine einfache Form von Continual Learning, ein
retrieval-basiertes System lernt, indem sein Wissensspeicher wächst, nicht indem seine
Gewichte sich verändern. Drei Lücken verhindern aber, dass daraus echtes *Verbessern*
statt nur *Anwachsen* wird.

## Ansatzpunkt 1: Ein Feedback-Kanal, der heute fehlt

Aktuell fließt kein Ergebnis der Interaktion zurück ins System: Ob ein vorgeschlagener
Job für den Nutzer relevant war, ob er sich beworben hat oder ihn ablehnte, wird nirgends
erfasst: `search_jobs` speichert nur das *Angebot*, nie die *Reaktion* darauf. Ein
naheliegender erster Schritt wäre ein neuer Dokumenttyp (z.B. `feedback`, ergänzend zu
`VALID_TYPES` in `rag_store.py`) und ein passendes MCP-Tool (analog zu `store_jobs`), über
das der Agent explizites Feedback ("passt nicht, zu weit weg", "genau richtig") als
strukturierte Metadaten neben der `referenznummer` ablegt. `get_profile_context` könnte
dieses Feedback dann zusätzlich zu `lebenslauf`/`praeferenz` abfragen und damit die
Empfehlungen mit jeder Interaktion feiner kalibrieren – klassisches Beispiel für
inkrementelles Lernen ganz ohne Modell-Update, nur über die Retrieval-Schicht.

## Ansatzpunkt 2: Profil updates statt einmaligem Snapshot

`ingest.py` ist  nur ein helper und der Lebenslauf wird einmalig manuell eingelesen. Ein kontinuierlich
lernendes System müsste stattdessen Profiländerungen laufend aufnehmen: z.B. indem der
Agent nach jedem Gespräch erkennt, ob der Nutzer neue Präferenzen genannt hat ("eigentlich
suche ich jetzt auch in Teilzeit"), und diese automatisch über `ingest_documents`/
`store_jobs`-artige Tools nachträgt, statt auf eine manuelle Neu-Ingestion zu warten. Die
`add_document`-Logik unterstützt das technisch bereits (Upsert über `_doc_id`, alte
Chunks werden beim erneuten Einlesen überschrieben) – es fehlt nur der Trigger. Das wichtige ist, die Wünsche und Verbesserungen sollten für ein kontinuierliches lernen automatisch vom Agent abgefragt und eingearbeitet werden. Das findet nicht statt, weswegen hier eine Überarbeitung nötig wäre.   

## Ansatzpunkt 3: Die Phoenix-Traces als Trainingssignal nutzen

`tracing.py` instrumentiert bereits jeden Modell- und Tool-Aufruf über
Phoenix/OpenTelemetry (`OpenAIInstrumentor`, `@traced`). Diese Traces sind im Moment reine
Debugging-Hilfe, könnten aber als Datenquelle für Verbesserung dienen: Anfragen, bei denen
der Nutzer seine Suche mehrfach umformuliert (implizites Signal "das Ergebnis war nicht
brauchbar"), oder Retrieval-Treffer mit niedrigem `score` aus `JobApplicationStore.query()`
ließen sich aus den Traces extrahieren und zu einem kuratierten Evaluationsdatensatz
zusammenstellen. Damit lässt sich regelmäßig prüfen, ob z.B. der Systemprompt, die
Tool-Beschreibungen oder die Chunking-Parameter (`CHUNK_SIZE`/`CHUNK_OVERLAP` in
`rag_store.py`) noch zur tatsächlichen Nutzungsrealität passen, und gezielt nachjustieren
– eine Form von Continual Learning auf Prompt-/Konfigurationsebene statt auf
Gewichtsebene. Tatsächlich wurde auch durch das Phoenix Tracing manuell das System angepasst, jedoch sollte in einer idealen Welt dies automatisch passieren. 

## Ansatzpunkt 4: Geplante Batch-Updates statt Online-Learning

Für die Komponenten, die sich nicht "online" nachziehen lassen, bietet sich ein
regelmäßiger Batch-Zyklus an:

- **Embedding-Modell**: `all-MiniLM-L6-v2` ist laut Code-Kommentar bewusst als
  Kompromiss gewählt; `paraphrase-multilingual-MiniLM-L12-v2` steht bereits als
  Alternative im Kommentar. Ein periodischer Vergleich beider Modelle auf denselben
  Testanfragen (mit denselben Metriken wie in Ansatzpunkt 3) wäre ein risikoarmer,
  kontrollierter Lernschritt, inklusive Re-Embedding des bestehenden Collection-Bestands.
- **Lokales LLM**: Ein echtes Fine-Tuning von `qwen3.5:4b` (z.B. per LoRA auf gesammelten,
  als "gut" markierten Interaktionen) wäre möglich und über Ollama lokal deploybar, ist
  aber der teuerste und riskanteste Schritt (Gefahr von Catastrophic Forgetting, hoher
  Kuratierungsaufwand) und sollte erst folgen, wenn die leichteren Schichten (Feedback,
  Retrieval, Prompt) ausgereizt sind.

## Voraussetzung: Kontrolle gegen unkontrolliertes Wachstum

Kontinuierliches Lernen aus neuen Daten braucht eine Gegenmaßnahme zur ungebremsten
Anhäufung, die heute fehlt: Ohne Verfallslogik für alte `stellenangebot`-Chunks würde jedes
neue Feedback- oder Profil-Signal in einem stetig wachsenden, nie bereinigten Index landen
(siehe auch die Drift-Reflexion). Continual Learning sollte hier also nicht nur "mehr
Daten aufnehmen" heißen, sondern immer mit einer Bewertung gekoppelt sein, welche
gespeicherten Informationen noch aktuell/relevant sind, bevor sie in künftige Antworten
einfließen. 

## Tiefe Reflexion: Wo das Konzept in Production brechen würde

Die vier Ansatzpunkte oben klingen sauber, solange man sie nur als Idee betrachtet. Prüft
man sie gegen die tatsächliche Codebasis, zeigen sich in jedem einzelnen Annahmen, die im
ersten Entwurf nicht ausgesprochen wurden.

**Ansatzpunkt 1 (Feedback-Kanal) hat dieselbe blinde Stelle wie der Rest des Systems:**
Weder `add_document` noch `add_jobs` in `rag_store.py` kennen eine `user_id`. Ein
Feedback-Dokumenttyp, wie hier vorgeschlagen, würde also genau wie CV- und
Präferenzdaten in einer einzigen, nutzerlosen Collection landen. Sobald das System von
mehr als einer Person genutzt wird, würde das Feedback von Nutzer A die Empfehlungen für
Nutzer B verfälschen – der Vorschlag würde also nicht *verbessern*, sondern aktiv
*verschlechtern*, sobald die im Drift-Dokument beschriebene Single-User-Annahme nicht mehr
gilt. Das hätte im ersten Entwurf mit angegeben werden müssen, statt es als
Implementierungsdetail zu übergehen.

**Ansatzpunkt 2 (automatische Profil-Updates)  Der Vorschlag, dass der Agent Präferenzänderungen
im Gespräch selbst erkennt und automatisch persistiert, verlässt sich vollständig auf die
korrekte Interpretation eines Freitext-Satzes durch ein 4B-Lokalmodell – ohne
Bestätigungsschritt. Versteht das Modell einen Nebensatz, eine Ironie oder eine vorläufige
Überlegung ("eigentlich könnte ich mir auch Teilzeit vorstellen") falsch als endgültige
Präferenzänderung, schreibt sich dieser Fehler dauerhaft in die Wissensbasis, ohne dass
irgendein Fehler oder Absturz das sichtbar macht. Anders als ein Crash fällt das niemandem
auf und die Empfehlungen verschlechtern sich. Ein Konzept ohne Bestätigungsschleife ist
hier schlicht unvollständig.

**Ansatzpunkt 3 (Phoenix-Traces als Trainingssignal) setzt voraus, dass Tracing
zuverlässig mitläuft – das stimmt laut Code nicht.** Laut README ist `python -m phoenix
serve` ein separater, manuell zu startender Schritt. `tracing.py` selbst ist bewusst
defensiv gebaut: Ist Phoenix nicht erreichbar oder nicht installiert, fällt
`init_tracing()` still auf einen No-Op-Tracer zurück (`_TRACE_INITIALIZED = False`), ohne
eine einzige Warnung auf der Konsole auszugeben. Genau in dem Moment, in dem die für
Ansatzpunkt 3 nötigen Daten am wichtigsten wären – z.B. weil im Produktivbetrieb niemand
mehr daran denkt, Phoenix separat zu starten – verschwindet die Datengrundlage
lautlos. Das Konzept hätte das nicht als gegeben voraussetzen dürfen, sondern hätte
fordern müssen, den No-Op-Fallback sichtbar zu machen (z.B. eine Warnung beim Start von
`main.py`).

**Ansatzpunkt 4 (Fine-Tuning) ist für dieses Projekt vermutlich unrealistisch, wurde
aber trotzdem gleichrangig neben die anderen gestellt.** Ein Single-User-CLI-Tool
erzeugt über ein Semester hinweg vermutlich Dutzende, nicht Zehntausende Interaktionen.
Das reicht nicht annähernd für ein robustes LoRA-Fine-Tuning, ohne dem Modell die
Eigenheiten genau einer Person und ihrer Formulierungsweise überzustülpen
(Overfitting auf ein Sample der Größe 1). Im Rückblick hätte dieser Punkt klar als
"für den aktuellen Projektumfang nicht sinnvoll" gekennzeichnet werden sollen, statt ihn als
gleichwertige vierte Option neben Feedback-Kanal, Profil-Updates und Trace-Auswertung zu
präsentieren – das erweckt einen falschen Eindruck von Reife des Konzepts.

## Fazit

Weil LLM und Embedding-Modell in diesem Setup bewusst statisch und lokal sind, liegt der
pragmatischste Hebel für Continual Learning nicht im Nachtrainieren von Gewichten, sondern
im Ausbau der bereits vorhandenen RAG-Infrastruktur: ein Feedback-Kanal, automatische statt
manuelle Profil-Aktualisierung und die systematische Auswertung der ohnehin vorhandenen
Phoenix-Traces. Modell-Fine-Tuning bleibt als letzter, teurer Schritt eine Option, sobald
diese leichteren, datengetriebenen Verbesserungen ausgeschöpft sind. Keiner dieser vier
Ansatzpunkte ist allerdings production-ready, wie er hier beschrieben wurde: Erst mit
Nutzer-Scoping, einer Bestätigungsschleife für automatische Profiländerungen und einer
sichtbaren statt stillen Tracing-Abhängigkeit würde aus der Idee ein Konzept, das man
tatsächlich deployen könnte.
