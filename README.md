# tv-gids

Bouwt elke nacht automatisch een XMLTV-gidsbestand voor TiviMate: de programma's van epgshare01 (NL)
onder de zender-ID's van de eigen IPTV-aanbieder. Het resultaat staat altijd op:

`https://github.com/<gebruiker>/tv-gids/releases/download/latest/epg_nl_merged.xml.gz`

De URL van de aanbieder (met login) staat alleen als versleutelde Actions-secret `EPG_PROVIDER_URL`, nooit in de code of het bestand.
