# LoA Future Features

Ten dokument opisuje plan rozwoju LoA: lokalnej aplikacji do uruchamiania, zarzadzania i uzywania agentow AI opartych o lokalnie dzialajace LLM. Ma sluzyc jako kontekst startowy dla kolejnych rozmow i decyzji projektowych.

## Wizja

LoA ma byc lekkim centrum zarzadzania lokalnymi agentami AI. Domyslnie powinno dzialac na slabszym komputerze, np. GTX 1080 i 16 GB RAM, ale z mozliwoscia rozszerzenia mocy przez inne komputery w sieci domowej.

Najwazniejsze zalozenia:

- dzialanie offline i lokalnie, bez wymogu chmury;
- uzycie istniejacych runtime LLM zamiast pisania inferencji od zera;
- mala liczba zaleznosci i rozsadne zuzycie RAM/VRAM;
- jeden interfejs dla lokalnych i zdalnych modeli;
- agenci jako konfiguracje: model, provider, prompt systemowy, parametry, narzedzia;
- mozliwosc laczenia wielu komputerow w LAN w jeden prosty klaster domowy.

## Stan Aktualny

Obecny prototyp zawiera:

- konfiguracje `loa.config.json`;
- adapter Ollama;
- adapter OpenAI-compatible;
- CLI: `agents`, `doctor`, `models`, `chat`, `serve`, `node-probe`;
- lokalny serwer HTTP;
- proste OpenAI-compatible endpointy `/v1/models` i `/v1/chat/completions`;
- web UI do czatu;
- web UI do tworzenia, edycji i usuwania agentow;
- zapis agentow do `loa.config.json`;
- podstawowe testy backendu.

## Priorytet 1: Stabilne Podstawy

### 1. Lepsze Zarzadzanie Procesami

Cel: LoA powinno umiec wygodnie uruchamiac i monitorowac lokalne runtime, szczegolnie Ollame.

Funkcje:

- wykrywanie instalacji Ollama na Windows;
- informacja, czy `ollama.exe serve` dziala;
- przycisk "Start Ollama" w UI;
- wykrywanie portu `11434`;
- pokazywanie bledow z logow Ollamy;
- opcjonalne ustawienie sciezki do `ollama.exe`;
- automatyczne odswiezanie statusu providera.

### 2. Zarzadzanie Modelami

Cel: uzytkownik powinien widziec modele, pobierac je i wybierac bez terminala.

Funkcje:

- lista lokalnych modeli z providerow;
- przycisk pobierania modelu dla Ollamy;
- postep pobierania;
- usuwanie modeli;
- oznaczanie modeli jako lekkie/srednie/ciezkie;
- rekomendacje modeli dla slabszego sprzetu;
- walidacja, czy agent uzywa modelu, ktory istnieje lokalnie.

### 3. Lepszy Czat

Cel: UI powinno nadawac sie do codziennego uzycia.

Funkcje:

- historia rozmow;
- nowe rozmowy;
- zapisywanie rozmow lokalnie;
- zmiana agenta w trakcie rozmowy;
- kopiowanie odpowiedzi;
- zatrzymanie generowania;
- pokazanie czasu odpowiedzi;
- pokazanie podstawowych statystyk tokenow, jesli provider je zwraca;
- streaming odpowiedzi zamiast czekania na cala odpowiedz.

## Priorytet 2: Siec Domowa i Wiele Komputerow

To jest kluczowy kierunek projektu.

### 4. Tryb Node

Cel: kazdy komputer w domu moze dzialac jako node LoA.

Node powinien udostepniac:

- informacje o zdrowiu: online/offline;
- liste agentow;
- liste modeli;
- typ providera;
- przyblizona moc: CPU, RAM, GPU, VRAM;
- aktualne obciazenie;
- liczbe aktywnych zadan;
- endpoint OpenAI-compatible;
- endpoint LoA-native z dodatkowymi metadanymi.

Minimalny endpoint:

- `GET /api/node/info`
- `GET /api/node/health`
- `GET /api/node/models`
- `GET /api/node/agents`
- `POST /api/chat`
- `POST /v1/chat/completions`

### 5. Dodawanie Komputerow w LAN

Cel: glowny LoA moze polaczyc sie z innym komputerem w domu.

Funkcje:

- formularz "Dodaj node";
- URL, nazwa, token, role;
- test polaczenia;
- zapis node do configu;
- automatyczne odpytywanie zdrowia;
- lista node'ow w UI;
- reczne wlaczanie/wylaczanie node'a;
- oznaczanie node'a jako lokalny, zdalny, mocny, slaby, eksperymentalny.

Przykladowy wpis:

```json
{
  "nodes": {
    "desktop-gpu": {
      "url": "http://192.168.1.40:8765",
      "enabled": true,
      "token": "shared-lan-token",
      "roles": ["chat", "code", "long-context"],
      "weight": 3
    }
  }
}
```

### 6. Discovery w Sieci Lokalnej

Cel: LoA powinno pomagac znajdowac inne instancje LoA w LAN.

Opcje:

- reczne dodanie adresu IP jako MVP;
- pozniej mDNS/Bonjour;
- alternatywnie prosty UDP broadcast tylko w podsieci lokalnej;
- przycisk "Szukaj node'ow";
- potwierdzenie przed dodaniem znalezionego node'a.

Zasady:

- discovery domyslnie wylaczone lub ograniczone do LAN;
- zadnego automatycznego zaufania;
- node musi miec token albo jednorazowy kod parowania.

### 7. Routing Zadan

Cel: LoA sam wybiera, czy zadanie ma isc na komputer lokalny czy zdalny.

Strategie routingu:

- pinned: agent zawsze uzywa konkretnego providera;
- local-first: najpierw lokalnie, fallback na LAN;
- fastest: wybor node'a z najlepszym czasem odpowiedzi;
- capacity: wybor node'a z najmniejsza kolejka;
- model-required: zadanie idzie tam, gdzie jest wymagany model;
- heavy-to-remote: duze modele i dlugi kontekst ida na mocniejszy komputer;
- offline-safe: tylko lokalny komputer, bez LAN.

Potrzebne dane:

- dostepnosc modeli;
- liczba zadan w kolejce;
- czas ostatniej odpowiedzi;
- blad ostatniego requestu;
- szacowany koszt pamieci;
- status GPU/VRAM, jesli dostepny.

### 8. Kolejka Zadan

Cel: slabszy sprzet nie powinien byc blokowany wieloma generacjami naraz.

Funkcje:

- kolejka per provider/node;
- limit rownoleglych zadan;
- anulowanie zadania;
- priorytety;
- status: queued, running, done, failed, cancelled;
- widok aktywnych zadan w UI;
- retry po bledzie providera;
- timeout per agent/provider.

## Priorytet 3: Bezpieczenstwo LAN

### 9. Tokeny i Parowanie

Cel: node'y w sieci domowej nie powinny byc otwarte dla kazdego urzadzenia.

Funkcje:

- `api_token` wymagany przy bindowaniu do `0.0.0.0`;
- kreator tokenu w UI;
- parowanie jednorazowym kodem;
- zapisywanie tokenow lokalnie;
- rotacja tokenow;
- informacja w UI, gdy node jest publicznie dostepny w LAN.

### 10. Ograniczenia Sieciowe

Cel: uniknac przypadkowego wystawienia LoA do internetu.

Zasady:

- domyslnie bind tylko do `127.0.0.1`;
- ostrzezenie przy `0.0.0.0`;
- sprawdzanie, czy adres jest prywatny LAN;
- dokumentacja firewall Windows;
- brak domyslnego wystawienia poza LAN;
- pozniej opcjonalny tryb reverse tunnel, ale nie jako MVP.

### 11. Uprawnienia Agentow

Cel: agent nie powinien automatycznie dostawac dostepu do wszystkiego.

Funkcje:

- profile uprawnien;
- agent tylko-czat;
- agent z dostepem do plikow;
- agent z dostepem do narzedzi;
- potwierdzanie operacji ryzykownych;
- log wykonanych akcji.

## Priorytet 4: Narzedzia Agentow

### 12. Tool System

Cel: agenci powinni miec opcjonalne narzedzia, ale kontrolowane.

Mozliwe narzedzia:

- czytanie plikow w wybranym katalogu;
- wyszukiwanie w projekcie;
- uruchamianie bezpiecznych komend;
- notatki lokalne;
- proste HTTP requesty do lokalnych uslug;
- analiza obrazow, jesli model/provider to wspiera.

Zasady:

- narzedzia przypisywane per agent;
- brak domyslnego shell access;
- audit log;
- wymagane potwierdzenie dla zapisu, usuwania i wysylania danych.

### 13. Agenci Specjalizowani

Przyklady agentow:

- `assistant`: ogolny, lekki model;
- `coder`: model codingowy, niski temperature;
- `summarizer`: szybkie streszczenia;
- `planner`: rozbija zadania;
- `research-local`: pracuje na lokalnych dokumentach;
- `heavy-reasoner`: agent kierowany na mocniejszy node LAN;
- `translator`: tlumaczenia i redakcja.

## Priorytet 5: UX i Aplikacja Desktopowa

### 14. Lepszy Web UI

Funkcje:

- sidebar z rozmowami;
- widok node'ow;
- widok modeli;
- widok kolejki;
- ustawienia;
- logi;
- ciemny/jasny motyw;
- import/export configu;
- walidacja formularzy;
- komunikaty bledow przy providerach.

### 15. Desktop Wrapper

Cel: aplikacja powinna byc latwa do uruchomienia dla nietechnicznego uzytkownika.

Opcje:

- Tauri jako lekka obudowa;
- Electron tylko jesli Tauri bedzie ograniczac;
- tray icon;
- start/stop serwera LoA;
- start/stop Ollama;
- autostart z systemem;
- powiadomienia;
- ustawienia sciezek i portow.

## Priorytet 6: Dane Lokalne

### 16. Lokalna Baza

Obecny config JSON jest dobry na MVP, ale docelowo przyda sie SQLite.

Do zapisania:

- agenci;
- providery;
- node'y;
- rozmowy;
- wiadomosci;
- zadania;
- metryki;
- logi;
- ustawienia UI.

Podejscie:

- zachowac eksport/import JSON;
- migracja z `loa.config.json` do SQLite;
- config JSON moze zostac jako tryb portable.

### 17. Pamiec Agentow

Funkcje:

- proste notatki per agent;
- pamiec per rozmowa;
- przypinane fakty;
- usuwanie pamieci;
- import plikow tekstowych;
- pozniej embeddings i lokalny indeks wektorowy.

## Priorytet 7: Obserwowalnosc i Wydajnosc

### 18. Metryki

Funkcje:

- czas do pierwszego tokena;
- calkowity czas odpowiedzi;
- tokeny/s;
- liczba bledow;
- status modelu;
- RAM/VRAM, jesli mozliwe;
- historia wydajnosci node'a.

### 19. Tryb Slabego Komputera

Cel: aplikacja ma nie zabijac komputera z 16 GB RAM.

Funkcje:

- limit jednego modelu naraz;
- male domyslne `max_tokens`;
- ostrzezenia przed ciezkimi modelami;
- automatyczne preferowanie modeli 3B/4B;
- opcjonalny fallback CPU;
- widoczny status "model sie laduje";
- mozliwosc unload modelu.

## Proponowana Kolejnosc Prac

1. Node management w configu i UI.
2. `GET /api/node/info` i `GET /api/node/health`.
3. Dodawanie zdalnego node'a recznie przez URL.
4. Test polaczenia i lista modeli z node'a.
5. Routing agenta do remote node'a.
6. Widok node'ow w UI.
7. Kolejka zadan per provider.
8. Streaming odpowiedzi.
9. Zarzadzanie modelami Ollama z UI.
10. Tokeny/parowanie dla LAN.
11. Historia rozmow.
12. SQLite.
13. Desktop wrapper.

## Najblizszy Sensowny MVP LAN

Najmniejszy uzyteczny krok:

- dodac `nodes` jako edytowalne w UI;
- dodac endpoint `GET /api/node/info`;
- dodac endpoint `GET /api/nodes/status` w glownym LoA;
- pozwolic agentowi wskazac provider `openai-compatible` z drugiego komputera;
- w UI pokazac, czy remote node odpowiada;
- zachowac reczne dodawanie IP, bez discovery.

To pozwoli szybko sprawdzic scenariusz:

1. Komputer A ma LoA i slaby model lokalny.
2. Komputer B ma LoA albo Ollame z mocniejszym modelem.
3. Komputer A dodaje komputer B jako node.
4. Agent `heavy-reasoner` na komputerze A wysyla zadania do B.
5. Uzytkownik korzysta z jednego UI na komputerze A.

## Ryzyka Techniczne

- rozne runtime'y maja rozne warianty OpenAI-compatible API;
- Windows firewall moze blokowac LAN;
- starsze GPU beda mialy duze roznice wydajnosci;
- streaming i anulowanie generacji roznia sie miedzy providerami;
- automatyczne discovery moze byc problematyczne bez dobrego modelu zaufania;
- zbyt ciezki frontend moze popsuc zalozenie lekkosci aplikacji.

## Decyzje Projektowe Do Utrzymania

- Najpierw API i core, potem ladniejsze UI.
- Domyslnie wszystko lokalnie.
- LAN jako rozszerzenie, nie wymog.
- Bez chmury w podstawowym flow.
- Bez automatycznego shell access dla agentow.
- Slabszy komputer ma byc pierwszoklasowym targetem.
- Provider adapters zamiast lock-in na jeden runtime.
