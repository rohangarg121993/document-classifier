# Taxonomy review: `categories.draft.csv`

Draft cleanup of `config/categories.csv` for business review. `config/categories.csv` is unchanged; the draft is
`config/categories.draft.csv` (same columns, UTF-8 with BOM, comma-separated). Category IDs are kept; merged
categories keep one ID. **144 → 134 categories.**

How the fields are used by the title-first engine (`src/docclassifier/classify/title_first.py`):

- `synonyms` = how a document of this category is **titled** (Betreff line, line before the salutation, large or
  short print near the top). A synonym matches as whole words, or as the last part of a compound
  ("Verhaltensabmahnung" → "Abmahnung"). So a short, generic synonym ("Zeugnis", "Bescheinigung", "Protokoll") also
  matches every compound ending in it.
- A title match picks the **parent group**. Inside that group, the body decides: `description` + `positive_phrases`
  (what the body says) minus `negative_phrases` (body wording that rules the category out against its siblings).

## 1. Merges (10)

| Kept | Dropped | Why |
|---|---|---|
| AUS01 Aufhebungsvertraege | AUS06 Aufhebungsvertrag | Same document type; identical synonyms |
| VTR02 UnbefristeterVertrag | VTR03 unbefristeter Vertrag | Same document type; identical synonyms |
| URK01 Polizeiliches Fuehrungszeugnis | URK10 Polizeiliches Führungszeugnis | Same document type; identical synonyms |
| FIN02 Pfaendung | FIN04 Pfändung | Same document type; identical synonyms |
| BAV04 Rente | BAV10 Rentenunterlagen | Both cover statutory pension papers (Rentenbescheid, Renteninformation shared) |
| AUS02 Austrittsunterlagen | AUS07 Austritt | Both are the fallback for exit paperwork; same synonyms |
| BEW01 Bewerbung | BEW08 Anschreiben | An application *is* the cover letter; BEW01 already said "insbesondere Anschreiben" |
| BEU02 Leistungsbeurteilung Formular | BEU05 Beurteilungsbogen | Both are the standard appraisal form |
| VPF01 NDA Geheimhaltungsvereinbarung | VPF03 DA / Geheimhaltungsvereinbarung | Same document type; identical synonyms |
| ENT13 Verdienstabrechnung | ENT09 Entgeltbescheinigung / Entgeltnachweise | The monthly payslip legally *is* the Entgeltbescheinigung (§ 108 GewO) |

For each merge the kept row holds the union of synonyms and positive phrases (generic ones removed) and one
combined description. Existing label or review files that use a dropped ID must be mapped to the kept ID.

## 2. Synonym changes per category

Removed synonyms were generic words that, through compound matching, claimed unrelated titles. Examples
(current → draft, checked with the engine's title matcher):

| Title | Current CSV | Draft |
|---|---|---|
| Ärztliches Zeugnis | ZEU01 Arbeitszeugnis ("Zeugnis") | no title match → body decides |
| Teilnahmebestätigung | SON06 ("Bestätigung") | body decides |
| Versorgungszusage | BEW07 Zusage ("Zusage") | BAV01 ("Versorgungszusage") |
| Kirchenaustritt | AUS02/AUS07 ("Austritt") | SVS02 ("Kirchenaustritt") |
| Gefährdungsbeurteilung | BEU05 ("Beurteilung") | body decides |
| Versicherungsprämie | ENT02 ("Prämie") | body decides |
| SEPA-Lastschriftmandat | ORG04 ("Mandat") | body decides |
| Kostenübernahme | VTR10 ("Übernahme") | body decides |
| Prozessvollmacht | ORG02 ("Vollmacht") | body decides |
| Übergabeprotokoll | SON03 ("Protokoll") | body decides |
| Arztrechnung | ZUS07 ("Rechnung") | body decides |
| Brillenbestellung | ORG04 ("Bestellung") | body decides |
| Leasingangebot | BEW07 ("Angebot") | body decides |

Full list. For merged categories, "Removed" is counted against the union of both original rows.

| ID | Category | Removed | Added |
|---|---|---|---|
| ZEU01 | Arbeitszeugnisse extern | Zeugnis | Dienstzeugnis, Schlusszeugnis |
| AZF01 | ATZ Checkliste | ATZ | ATZ Checkliste, Checkliste ATZ |
| AUS01 | Aufhebungsvertraege | – | Auflösungsvereinbarung, Beendigungsvereinbarung, Vereinbarung über die Beendigung des Arbeitsverhältnisses, Abwicklungsvertrag |
| AUS02 | Austrittsunterlagen | Austritt, Ausscheiden | Austrittsmitteilung, Austrittsbestätigung, Mitteilung über das Ausscheiden, Bestätigung des Ausscheidens, Ausscheiden aus dem Unternehmen, Austritt aus dem Unternehmen, Ihr Austritt, Ihr Ausscheiden, Rückgabeprotokoll |
| ZUS01 | AVWL | VL, VWL | Antrag auf vermögenswirksame Leistungen, Mitteilung über vermögenswirksame Leistungen, VL-Vertrag, AVWL |
| BAV01 | BAV Schriftverkehr | – | Versorgungszusage, Pensionszusage, Standmitteilung |
| BAV02 | BAV Umwandlungserklaerung | – | Vereinbarung über Entgeltumwandlung, Umwandlungsvereinbarung |
| VTR01 | Befristeter Arbeitsvertrag | – | befristetes Arbeitsverhältnis |
| BEW01 | Bewerbung | Anschreiben, Begleitschreiben | Bewerbungsanschreiben, Initiativbewerbung |
| AUS03 | Checkliste_Austritt | – | Offboarding Checkliste, Laufzettel Austritt, Austrittslaufzettel |
| BEW02 | Checkliste_Eintritt | – | Onboarding Checkliste, Laufzettel Eintritt, Eintrittslaufzettel |
| FIN01 | Darlehen | – | Darlehensvereinbarung |
| ZUS02 | Dienstwagenberechnung | – | Berechnung des geldwerten Vorteils, Firmenwagenberechnung |
| BAV03 | Direktversicherung | Versicherungsschein | Direktversicherungsvertrag, Versicherungsschein zur Direktversicherung |
| FAM01 | Elternzeit | – | Bestätigung der Elternzeit, Verlängerung der Elternzeit |
| AZF02 | Checkliste LAKO Freiphase | LAKO, Langzeitkonto, Lebensarbeitszeitkonto, Freiphase | Checkliste LAKO Freiphase, Checkliste Freiphase, LAKO Checkliste, Checkliste Langzeitkonto |
| BEW03 | Lebenslauf | – | Resume |
| FAM02 | Mutterschutz | – | Beschäftigungsverbot, Bescheinigung über den mutmaßlichen Tag der Entbindung, Zuschuss zum Mutterschaftsgeld, Mutterschaftsgeld |
| VPF01 | NDA Geheimhaltungsvereinbarung | – | Confidentiality Agreement |
| FIN02 | Pfaendung | Abtretung | Pfändungsverfügung, Vorpfändung, Lohnabtretung, Gehaltsabtretung, Abtretung von Arbeitseinkommen, Drittschuldnererklärung |
| URK01 | Polizeiliches Fuehrungszeugnis | – | Auskunft aus dem Bundeszentralregister |
| ZEU02 | Qualifikationsnachweise | Urkunde, Abschlusszeugnis | Zeugnis der allgemeinen Hochschulreife, Abiturzeugnis, Hochschulzeugnis, Bachelorzeugnis, Masterzeugnis, Diplomzeugnis, Gesellenbrief, Facharbeiterbrief, Meisterbrief, Lehrgangsbescheinigung, Transcript of Records |
| BAV04 | Rente | – | Versicherungsverlauf, Kontenklärung, Antrag auf Altersrente |
| GES01 | Schwerbehinderung | Feststellungsbescheid, Gleichstellung | Gleichstellungsbescheid, Gleichstellung mit schwerbehinderten Menschen, Feststellung des Grades der Behinderung, Grad der Behinderung |
| GES02 | Sicherheitsunterweisung | Teilnahmenachweis | Nachweis der Unterweisung, Teilnehmerliste Unterweisung |
| SVS01 | Sozialversicherung | – | Versicherungsnummernnachweis, Beitragsbescheid |
| SVS02 | Steuerunterlagen | Steuer | Steuer-Identifikationsnummer, Lohnsteuerabzugsmerkmale, ELStAM, Bescheinigung für den Lohnsteuerabzug, Lohnsteuerermäßigung, Steuerbescheid, Einkommensteuerbescheid, Kirchenaustritt |
| VTR02 | UnbefristeterVertrag | – | unbefristetes Arbeitsverhältnis, Employment Contract |
| AZF03 | Unbezahlter Urlaub | – | unbezahlte Freistellung |
| URK05 | Trennung | Trennung | Scheidungsbeschluss, Ehescheidung, Scheidungsfolgenvereinbarung |
| BEW04 | Personalfragebogen | – | Personaldatenblatt, Personalstammblatt |
| VTR04 | Dienstzeitanrechnung | Betriebszugehörigkeit | Anerkennung von Vordienstzeiten, Anrechnung der Betriebszugehörigkeit, Anrechnung von Dienstzeiten |
| VTR05 | Entsendung | – | Entsendungsvereinbarung, Abordnungsvereinbarung |
| VTR06 | Genehmigung Nebentätigkeiten | – | Anzeige einer Nebentätigkeit, Nebenbeschäftigung |
| AZF04 | ATZ | – | Antrag auf Altersteilzeit |
| AZF05 | LAKO Freistellungsvereinbarung | LAKO, Langzeitkonto, Lebensarbeitszeitkonto | LAKO Freistellungsvereinbarung, Freistellung aus dem Langzeitkonto, Entnahme aus dem Wertguthaben |
| VTR07 | Telearbeitsvertrag | – | Telearbeitsvertrag, Vereinbarung über mobiles Arbeiten, Homeoffice-Vereinbarung |
| VTR08 | Versetzung | Umsetzung | Versetzungsmitteilung, Versetzungsvereinbarung |
| VPF04 | Verpflichtungserklärung Datenschutz | – | Verpflichtung auf die Vertraulichkeit, Verpflichtung zur Vertraulichkeit, Datenschutzverpflichtung |
| VPF05 | Verpflichtungserklärung private Nutzung IT | – | Verpflichtungserklärung private Nutzung IT, Private Nutzung von Internet und E-Mail, Nutzungsvereinbarung IT |
| ZEU04 | Immatrikulationsbescheinigung | – | Immatrikulationsnachweis, Bescheinigung über die Immatrikulation |
| VTR09 | Vertragsverlängerung / Entfristung | – | Verlängerung des befristeten Arbeitsvertrags, Verlängerungsvereinbarung |
| ORG02 | Handlungsvollmachten | Vollmacht, Bevollmächtigung | Erteilung der Prokura, Gesamtprokura, Einzelprokura, Zeichnungsberechtigung, Unterschriftsberechtigung |
| ORG03 | Pflichtenübertragung | Delegation | Übertragung von Arbeitgeberpflichten, Pflichtenübertragung Arbeitsschutz |
| AUS05 | Kündigung | – | ordentliche Kündigung, außerordentliche Kündigung, fristlose Kündigung, Änderungskündigung, Kündigung des Arbeitsverhältnisses |
| SON01 | sonstiger Schriftverkehr | Schreiben, Brief, E-Mail | sonstiger Schriftverkehr, Korrespondenz, Informationsschreiben |
| ORG04 | Betriebliches Mandat | Mandat, Beauftragung, Bestellung | Bestellung zum Sicherheitsbeauftragten, Bestellung zum Datenschutzbeauftragten, Bestellung zum Brandschutzhelfer, Bestellung zum Ersthelfer, Bestellung zur Fachkraft für Arbeitssicherheit, Bestellungsurkunde |
| ENT01 | Entgeltveränderungen | – | Entgelterhöhung, Lohnerhöhung, Tariferhöhung, Höhergruppierung |
| ENT02 | Einmalzahlungen | Prämie | Inflationsausgleichsprämie, Weihnachtsgeld, Urlaubsgeld, Jubiläumszuwendung, Sonderprämie |
| ENT03 | ERA / HAY | – | Umgruppierung |
| BEU02 | Leistungsbeurteilung Formular | Beurteilung | Regelbeurteilung, Personalbeurteilung, Leistungsbewertung, Performance Review |
| ENT04 | Variable Vergütung | – | Bonusvereinbarung, Zielvereinbarung, Leistungsprämie |
| ZUS03 | Zuschuss | – | Kinderbetreuungszuschuss, Kindergartenzuschuss, Essenszuschuss |
| ZUS06 | Gruppenunfallversicherung | Unfallversicherung | Gruppen-Unfallversicherung, Gruppenunfall |
| ENT07 | Altersverdienstsicherung | Alterssicherung | Verdienstsicherung im Alter |
| ZUS07 | Rechnungen Unterkunft / Umzug | Rechnung | Speditionsrechnung, Übernachtungsrechnung, Maklerrechnung, Rechnung Umzug, Rechnung Unterkunft |
| ZUS09 | Fahrtkosten | – | Reisekostenabrechnung, Fahrtkostenerstattung, Antrag auf Fahrtkostenerstattung |
| ZUS11 | Dienstwagenvereinbarung | – | Überlassungsvertrag Dienstwagen, Firmenwagenvereinbarung |
| BAV05 | Andere Pensionen | Pension | Zusatzversorgungskasse, private Rentenversicherung, Versorgungsbezüge, Ruhegehalt |
| BAV06 | Pensionskasse | – | Pensionskassenvertrag |
| FAM04 | Pflegezeit | – | Ankündigung der Pflegezeit |
| FAM05 | Teilzeit während Elternzeit | – | Teilzeit in der Elternzeit, Teilzeit in Elternzeit |
| AZF07 | Arbeitszeitänderungen | – | Teilzeitantrag, Antrag auf Teilzeit, Antrag auf Verringerung der Arbeitszeit, Brückenteilzeit, Erhöhung der Arbeitszeit |
| ZUS12 | Jobrad | – | Dienstradüberlassung |
| BAV08 | P3 Kontoauszug | P3, Kontostand | Kontoauszug P3 |
| BAV09 | P3 Benennungsrecht | Benennung | Benennungsrecht, Benennung von Bezugsberechtigten, Begünstigtenbenennung |
| BEW07 | Zusage | Zusage, Angebot | Stellenzusage, Jobangebot, Offer Letter |
| AZF09 | Lako Verzinsungsmodell | LAKO, Langzeitkonto, Verzinsung | LAKO Verzinsungsmodell, Verzinsungsmodell, Verzinsung des Wertguthabens, Verzinsung Langzeitkonto |
| SON03 | Gesprächsprotokoll | Protokoll | Gesprächsvermerk, Besprechungsprotokoll, Ergebnisprotokoll, Aktenvermerk, Telefonnotiz |
| BEU04 | FEF | Förderprogramm | – |
| ZEU05 | Abschlusszeugnis (künftig alle aus Zeugnismanager) | Endzeugnis | Zeugnis über die Berufsausbildung |
| ZEU06 | Praktikum Einsatzbestaetigung | – | Praktikantenzeugnis, Bescheinigung über ein Praktikum |
| GES03 | Arbeitsmedizinische Vorsorge | Betriebsarzt | Bescheinigung über arbeitsmedizinische Vorsorge, arbeitsmedizinische Untersuchung |
| GES04 | Unfallmeldung | – | Unfallbericht |
| GES05 | Krankheit / Reha / Wiedereingliederung | – | Wiedereingliederungsplan |
| SON04 | Antwortschreiben | Antwort, Stellungnahme | – |
| GES07 | Dokumentation BEM | – | Eingliederungsmanagement |
| BEW09 | Eintritt | Eintritt, Einstellung | Eintrittsunterlagen, Einstellungsunterlagen, Eintrittsmitteilung, Einstellungsmitteilung |
| AZF11 | Lako | – | Wertguthabenvereinbarung, Vereinbarung über ein Langzeitkonto |
| AUS08 | Tod Mitarbeiter | – | Beileidsschreiben, Kondolenzschreiben |
| SVS04 | Aussteuerung | – | Aussteuerungsmitteilung, Ende des Krankengeldanspruchs |
| VTR10 | Azubi-, Dualiübernahme | Übernahme | Übernahme nach dem dualen Studium, Übernahme in ein Arbeitsverhältnis, Übernahmeangebot |
| ENT13 | Verdienstabrechnung | – | Bezügeabrechnung, Payslip |
| SON05 | Änderung Adresse / Bankverbindung | Änderungsmitteilung | Änderung der Anschrift, Anschriftenänderung, Änderung Bankverbindung, neue Bankverbindung |
| VTR11 | Vertragsänderung | – | Änderung des Arbeitsvertrags, Ergänzung zum Arbeitsvertrag, Nachtragsvereinbarung |
| SON06 | sonstige Bescheinigungen | Bescheinigung, Bestätigung | sonstige Bescheinigung, Arbeitgeberbescheinigung, Arbeitsbescheinigung, Beschäftigungsbescheinigung, Bescheinigung des Arbeitgebers, Arbeitgeberbestätigung, Bestätigung des Arbeitgebers |
| BAV11 | P3 Umwandlungserklaerung | P3 | P3 Entgeltumwandlung |

## 3. Placeholders needing business input

The draft gives these categories working definitions so they can be classified, but the meaning has to be confirmed.

| ID(s) | Question for the business |
|---|---|
| BAV07, BAV08, BAV09, BAV11 (P3) | What is "P3"? The draft assumes it is a company plan within the bAV (company pension), based on its parent group and phrases (Kontoauszug, Benennungsrecht = beneficiary, Umwandlungserklärung). The old descriptions ("P3-System oder Projekt", "eine Person für eine Position benennen") were guesses and were replaced. What do P3 documents' titles actually say? |
| AZF02, AZF05, AZF09, AZF11 (LAKO) | Confirm that LAKO = Langzeitkonto / Lebensarbeitszeitkonto (Wertguthaben). The old AZF05/AZF11 descriptions said "Landesarbeitsgemeinschaft der kommunalen Arbeitgeber", which contradicted their own synonyms and phrases. Is the split into general account (AZF11), Freistellungsvereinbarung (AZF05), Freiphase checklist (AZF02) and Verzinsungsmodell (AZF09) how the documents arrive? |
| AZF04 (ATZ) | The old description described generic part-time work. Rewritten as Altersteilzeit (Altersteilzeit agreement). Please confirm. |
| BEU04 (FEF) | What does FEF stand for, and what do these documents look like (title, typical content)? "Förderprogramm" was removed as too generic; only "FEF" and "Führungskräfteentwicklung" remain. |
| ENT07 (Altersverdienstsicherung) | The old description described pension provision. Rewritten as the collective-agreement earnings protection for older employees, which matches its phrases (Lebensjahr, Betriebszugehörigkeit, Ausgleichsbetrag). Which collective agreement applies, and is this correct? |
| VPF02 (Obligation Letter Staatsangehörigkeit) | What is this letter for (e.g. export control / nationality declaration)? Who issues it, and what is its title? Left unchanged. |
| ZEU05 (Abschlusszeugnis, Zeugnismanager) | The draft reads this as the company's own Ausbildungszeugnis (final certificate for its trainees and dual students). Or is it the company's own final Arbeitszeugnis (Endzeugnis) for leavers? That decides whether "Endzeugnis" belongs here or with ZEU01 (external). |
| ZEU01 (Arbeitszeugnisse extern) | "Extern" (issued by a previous employer) cannot be told from the text. Where should the company's own final Arbeitszeugnisse go? |
| FAM03 / FAM06 (Care for Life) | Company programme: what do its documents' titles say? |
| SON04 (Antwortschreiben) | "Stellungnahme" and "Antwort" were removed as too generic (e.g. a works council Stellungnahme). Should a Stellungnahme go here, or to the topic it answers? |
| AUS01 | "Abwicklungsvertrag" (settlement after a dismissal) was added to the termination agreement category. OK? |
| AZF05 | "Freistellungsvereinbarung" is also used for garden leave before an exit (group Austritt). Body phrases (Wertguthaben, Langzeitkonto) keep them apart. Should a garden-leave agreement go to AUS01 instead? |

## 4. Other edits

- **Descriptions rewritten** where they were wrong or invented: AUS05 (said "by employer *or* employee"; now employer only), AZF04, AZF02/05/09/11, ENT07, BAV07/08/09/11, BEW07, BEW09, ZUS03, SVS04, VTR05, ORG04, ZEU05, FAM01 (no longer claims part-time during parental leave, which is FAM05), SVS02 (no longer lists the Lohnsteuerbescheinigung, which is SVS06).
- **No "kein X" clauses in new descriptions.** The description feeds the meaning model and is tested against the category's own negative phrases. A description saying "keine Checkliste" reads as being about checklists and triggers its own negative. Exclusions now sit in `negative_phrases`.
- **Negative phrases between siblings** added or changed: AUS04 ↔ AUS05 (employee vs employer dismissal: "kündigen wir", "Anhörung des Betriebsrats" vs "hiermit kündige ich", "Ihr Kündigungsschreiben"); AUS04 no longer has "Ihr Arbeitsverhältnis" as a negative, since its own confirmation letters use that phrase; VPF01 ↔ VPF04 ↔ VPF07 (agreement vs data-protection vs confidentiality declaration); FAM01 ↔ FAM05; AZF02/05/09/11; the BAV P3 group; BEW01 ↔ BEW05/BEW06/BEW07; ZEU01/02/03/05; ENT02 ↔ ENT04; DIS02 (a traffic "Verwarnungsgeld" is not a disciplinary warning); BAV03/04/05; GES05 ↔ GES07; SVS02 ↔ SVS06; AZF07.
- **Odd negative removed**: SVS04 had "Zwischenzeugnis".
- **Generic positive phrases removed**: AUS02 "Bestätigung", "Zeugnis"; ENT08 "Betrag", "Antrag"; SON06 "hiermit"; ZUS03 "Fördermittel"; BEW01 (merged) "Sehr geehrte", "mit freundlichen Grüßen"; AUS05 "fristgerecht", "Arbeitsverhältnis" (shared with AUS04).
- Category names are unchanged. Transliterated or odd names (e.g. "Pfaendung", "Sozialfond") are left for the business to decide.

## 5. Verification

- `load_categories('config/categories.draft.csv')` loads 134 categories without errors.
- Shared synonyms: 28 → 1 ("Kündigung", deliberately in AUS04 and AUS05; the body decides between them).
- `selfcheck`, both files run on the same code snapshot (commit 72aef96 plus uncommitted title-first work in progress):

| Engine | `categories.csv` | `categories.draft.csv` |
|---|---|---|
| title_first (current default) | 76/144 pass (68 failures) | 87/134 pass (47 failures) |
| evidence | 132/144 pass (12 failures, all duplicate pairs) | 134/134 pass (0 failures) |

On title_first, every category ranks first on its own page in both files. The failures come from the selfcheck
confidence formula, which returns 0 when the runner-up scores ≥ 1. Title-first scores (cosine + phrase bonus) often
exceed 1, so these failures are not collisions.
