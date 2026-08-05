# Responsible AI – Reflexion: Risiken, Bias und Missbrauchspotenzial im Job-Such-Agenten

## Allocative oder representational harm?

Der Kredit-Klassifikator aus der Vorlesung trifft eine binäre Entscheidung *über* eine
dritte Person (Approve/Deny). Unser Agent trifft keine solche Entscheidung. Der Agent 
entscheidet nicht, wer einen Job bekommt, sondern kuratiert und formuliert Informationen
*für* den Nutzer selbst. Klassische Fairness-Metriken (Independence/Separation/
Sufficiency, R/A/Y) greifen hier deshalb nicht direkt: Es gibt kein R, das über eine
Gruppe A entscheidet. Trotzdem ist der Agent nicht harmlos, und die Vorlesung liefert
dafür genau die richtige Unterscheidung: **representational harm dominiert**, aber es
gibt eine subtile allocative Komponente, nicht "wer bekommt den Kredit", sondern
"welche Jobmöglichkeiten werden dem Nutzer überhaupt sichtbar gemacht". Sichtbarkeit ist
selbst eine knappe Ressource; ein System, das systematisch bestimmte Stellentypen
unterrepräsentiert, alloziert Aufmerksamkeit ungleich, auch ohne eine formale
Ja/Nein-Entscheidung zu treffen. Die Abhängikeit des System von den Jobbörsen spielt auch eine massive Rolle, da die Suche innerhalb der Börsen durch verschiedene Metriken beeinflusst wird. 
## Konkrete Bias-Quellen im System

**Retrieval-Bias als Feedback-Loop (RAG-spezifisch, Vorlesungskapitel "LLM- und
Agent-spezifische Risiken"):** `search_jobs` speichert jeden Treffer automatisch in
ChromaDB (`JobApplicationStore.add_jobs`, `core_functions/rag_store.py`). Was der Nutzer
anfangs sucht, prägt damit dauerhaft, was später über `query_knowledge` überhaupt
gefunden werden kann. Genau das ist der in der Vorlesung angesprochene, bekannte Mechanismus: "was die
Wissensbasis nicht enthält, existiert für den Agenten nicht". Anders als beim
Kredit-Beispiel verstärkt sich hier keine Diskriminierung einer fremden Gruppe, sondern
ein enger werdender Suchhorizont des Nutzers selbst. Das ähnelt eher einem Echokammer-Effekt statt eines klassischen Feedback-Loops.

**Ein versteckter Proxy-Default:** `JobsucheClient.search()`
(`core_functions/arbeitsagentur_jobsuche_API_jobs_client.py`, Zeile 103) setzt
`zeitarbeit: bool = True` fest und übergibt diesen Parameter bei *jeder* Suche, ohne dass
der Systemprompt oder der Nutzer das explizit entscheidet. Zeitarbeitsstellen sind
statistisch häufiger prekär und überproportional mit bestimmten sozioökonomischen
Gruppen assoziiert. Das ist kein Bias in den Trainingsdaten eines Modells, sondern ein
stiller Engineering-Default, der reale ökonomische Konsequenzen hat, ohne dokumentiert
oder begründet zu sein – genau die Art von Entscheidung, die laut Vorlesung "explizit und
nachvollziehbar" statt versteckt sein müsste.

**Fairness through Unawareness in der Generierung:** Der Agent bekommt nirgends ein
explizites sensibles Merkmal A übergeben – aber `get_profile_context` speist den vollen
Freitext des Lebenslaufs direkt in den LLM-Kontext ein (`rag_store.py`,
`get_profile_context`), inklusive Namen, Ausbildungsstätten, Wohnort. Wenn das LLM laut
Systemprompt Stellen "sinnvoll kategorisiert" und priorisiert (`SYSTEM_PROMPT` in
`agents/job_search_agent.py`), verarbeitet es damit exakt die Proxys (Name, Hochschule,
Wohnort als PLZ-Analogon), die im Amazon-Recruiting-Fall zur systematischen Abwertung
bestimmter Bewerbergruppen führten. Das Fehlen eines expliziten A-Merkmals schützt hier
nicht, es macht das Risiko nur unsichtbarer.

**Bias skaliert zur Handlung:** Der Agent bleibt aktuell beim Lesen/Speichern, aber die
Architektur ist bereits handlungsfähig (`store_jobs`, `ingest_documents` schreiben
persistent in die Wissensbasis). Jede verzerrte Kategorisierung oder Priorisierung
schreibt sich damit in einen Zustand, der künftige Antworten mitbestimmt – der in der
Vorlesung beschriebene Übergang von Text-Bias zu strukturellem Bias ist hier technisch
bereits angelegt, auch wenn die Konsequenzen im Einzelnutzer-Kontext kleiner ausfallen als
bei einem Recruiting-System mit tausenden Bewerbungen.

## Privacy und Accountability als weitere Säulen

Der Vektorspeicher enthält hochsensible Personendaten: Lebenslauf, Noten, Zeugnisse
(`VALID_TYPES` in `rag_store.py`), lokal und unverschlüsselt, ohne Datasheet, ohne
dokumentierte Aufbewahrungsfrist oder Löschregel. Es existiert weder eine Model Card
für das verwendete LLM/Embedding-Modell noch ein Hinweis auf dessen bekannte Schwächen
(der Code-Kommentar zu `all-MiniLM-L6-v2` in `ChromaDB/rag/vector_store.py` nennt selbst
eine bessere, aber ungenutzte Alternative für Deutsch). Ohne diese Dokumentation lässt
sich Verantwortung nicht zuordnen, wenn der Agent systematisch schlechtere Ergebnisse für
bestimmte Profile liefert – das Problem wäre schlicht nicht sichtbar, weil niemand danach
misst.

## Missbrauchspotenzial

Über die reine Bias-Frage hinaus: `ingest_documents` liest beliebige Dateien aus einem
Ordner ein und deren Inhalt landet ungefiltert im LLM-Kontext künftiger Anfragen –
präparierte Dokumente könnten so (Prompt-Injection-artig) das Verhalten des Agenten
manipulieren. Zudem erlaubt `search_jobs` durch fehlende Rate-Begrenzung theoretisch ein
automatisiertes Massen-Abfragen der Arbeitsagentur-API über den eigenen API-Key hinaus,
was gegen deren Nutzungsbedingungen verstoßen könnte.

## Fazit

Am ehesten trifft **representational harm mit einer stillen allocativen Komponente** zu:
Der Agent entscheidet nicht formal über Menschen, aber er entscheidet, welche
Jobmöglichkeiten sichtbar werden und wie sie dargestellt werden – gespeist aus Proxys, die
er nie explizit als sensibel behandelt. Verantwortung dafür liegt eindeutig bei den
Entwicklern des Systems, nicht bei "dem Modell": Defaults wie `zeitarbeit=True`, die Wahl
eines nicht deutsch-optimierten Embedding-Modells und das Fehlen jeder Dokumentation sind
Konstruktionsentscheidungen, keine Naturgesetze. Genau wie in der Vorlesung betont, gehört
diese Verantwortung von Anfang an in die Architektur – nicht als nachträglicher Anstrich.
