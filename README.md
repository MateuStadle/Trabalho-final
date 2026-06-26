# DataStore — Persistência em Múltiplos Formatos

Projeto de persistência de dados que demonstra a diferença entre armazenamento **texto** (JSON, CSV) e **binário** (pickle, struct) com interface de ordenação/busca integrada.

---

## Estrutura do projeto

```
projeto/
├── backend/
│   ├── app.py              # Flask — todos os endpoints
│   └── requirements.txt
├── frontend/
│   └── index.html          # SPA — busca, ordenação, painel comparativo
├── data/                   # Arquivos gerados em runtime
│   ├── dados.json
│   ├── dados.csv
│   ├── dados.pkl
│   └── dados.bin
└── README.md
```

---

## Como rodar

### 1. Backend

```bash
cd backend
pip install -r requirements.txt
python app.py
# Servidor em http://localhost:5000
```

### 2. Frontend

Abra `frontend/index.html` diretamente no navegador (ou sirva com `python -m http.server 8080` na pasta `frontend/`).

---

## Endpoints da API

| Método | Rota           | Descrição                                               |
|--------|----------------|---------------------------------------------------------|
| GET    | `/carregar`    | Baixa da API externa e salva nos 4 formatos             |
| POST   | `/salvar`      | Recebe JSON no body e grava nos 4 formatos              |
| GET    | `/offline`     | Lê do arquivo salvo (`?formato=json\|csv\|pickle\|struct`) |
| GET    | `/comparar`    | Tamanho (KB) + tempo de carregamento de cada formato   |
| GET    | `/inspecionar` | Amostra de texto (JSON) + hexdump do binário (pickle)  |

---

## Formatos implementados

### Texto (legível / portável)

#### JSON — `json.dump` / `json.load`
- Preserva a estrutura aninhada completa (address, company).
- Legível em qualquer editor de texto.
- Encoding explícito: `encoding="utf-8"`.

```python
with open(JSON_PATH, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
```

#### CSV — `csv.DictWriter` / `csv.DictReader`
- Achata a estrutura para 6 colunas fixas (id, name, username, email, city, company).
- Compatível com Excel, pandas, Google Sheets.

```python
with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["id","name","username","email","city","company"])
    writer.writeheader()
    writer.writerows(rows)
```

### Binário (compacto / rápido)

#### pickle — `pickle.dump` / `pickle.load`
- Serializa o objeto Python inteiro; estrutura aninhada preservada.
- **Não** use com dados não confiáveis (execução arbitrária ao carregar).
- Típico: menor que JSON, maior que struct fixo.

```python
with open(PKL_PATH, "wb") as f:
    pickle.dump(data, f)
```

#### struct — `struct.pack` / `struct.unpack`
- Registro de tamanho **fixo**: `!I 50s 30s 60s 40s 50s` = 234 bytes/registro.
- Sem overhead de chaves ou delimitadores.
- Limitação: strings truncadas ao tamanho fixo.

```python
STRUCT_FMT = "!I 50s 30s 60s 40s 50s"   # big-endian
record = struct.pack(STRUCT_FMT, id, name, username, email, city, company)
```

---

## Robustez

- Todos os arquivos abertos com `with open(...)`.
- Texto sempre com `encoding="utf-8"`.
- Binários com `"rb"` / `"wb"`.
- Endpoint `/offline` verifica se o arquivo existe antes de abrir e retorna 404 com mensagem clara caso não exista.

```python
if not os.path.exists(path):
    return jsonify({"erro": "Arquivo não encontrado. Carregue da API primeiro."}), 404
```

---

## Análise comparativa (10 registros — JSONPlaceholder `/users`)

| Formato | Tamanho | Salvar | Carregar | Observação |
|---------|---------|--------|----------|------------|
| JSON    | ~5 KB   | ~1 ms  | ~0.5 ms  | Maior; preserva tudo; legível |
| CSV     | ~1 KB   | ~0.5 ms| ~0.3 ms  | Menor texto; perde aninhamento |
| pickle  | ~3 KB   | ~0.3 ms| ~0.2 ms  | Compacto; rápido; Python-only |
| struct  | ~2.3 KB | ~0.2 ms| ~0.1 ms  | Mais rápido; tamanho fixo previsível |

> Valores ilustrativos para 10 registros. Com datasets maiores, pickle e struct ganham mais vantagem relativa.

### Quem ganhou em cada critério?

**Menor tamanho:** CSV (sem aninhamento, sem chaves repetidas).

**Menor em binário:** struct — tamanho 100% previsível (`N × 234 bytes`), sem metadados Python.

**Mais rápido para carregar:** struct — leitura sequencial de blocos fixos, sem parser.

**Mais portável:** JSON — interoperável com qualquer linguagem.

**Melhor fidelidade:** JSON e pickle — preservam estrutura aninhada completa.

### Por que struct é o mais rápido?

`struct.unpack` lê blocos de bytes de tamanho conhecido sem varredura de tokens. O sistema operacional pode prefetch as páginas de forma previsível. JSON e pickle precisam de um parser que atravessa cada byte para encontrar delimitadores ou marcadores de tipo.

### Por que JSON é o maior?

Cada chave é repetida para cada registro (`"name"`, `"username"` etc.), e o indentador `indent=2` adiciona espaços. Com muitos registros, a redundância de chaves torna JSON 3–5× maior que struct.

---

## Funcionalidades do frontend

- **Carregar da API** → chama `/carregar`, salva nos 4 formatos automaticamente.
- **Carregar do arquivo** → seleciona o formato e chama `/offline` (funciona sem internet).
- **Busca em tempo real** → filtra por nome, email, cidade, empresa.
- **Ordenação** → clique no cabeçalho da coluna ou use os selects; suporte a asc/desc.
- **Painel comparativo** → barras de tamanho + tempo de carregamento lado a lado.
- **Inspeção** → trecho legível do JSON vs hexdump do pickle (16 bytes/linha).
