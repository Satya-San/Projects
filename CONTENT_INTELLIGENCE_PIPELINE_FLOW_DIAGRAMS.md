```mermaid
%%{init: {'flowchart': {'htmlLabels': true}, 'theme': 'neutral'}}%%
flowchart LR
  subgraph LEGEND[" "]
    direction TB
    L1(( )):::trigger
    L2[step]:::action
    L3[(store)]:::store
    L4{{LLM}}:::llm
    L5{branch}:::branch
  end
  subgraph KEYS[" "]
    direction TB
    K1["trigger / start"]:::note
    K2["sync step"]:::note
    K3["disk artifact"]:::note
    K4["OpenRouter chat"]:::note
    K5["if / loop gate"]:::note
  end
  classDef trigger fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px
  classDef action fill:#E3F2FD,stroke:#1565C0,stroke-width:1px
  classDef store fill:#FFF3E0,stroke:#EF6C00,stroke-width:1px
  classDef llm fill:#F3E5F5,stroke:#7B1FA2,stroke-width:1px
  classDef branch fill:#ECEFF1,stroke:#455A64,stroke-width:1px
  classDef note fill:#FAFAFA,stroke:#BDBDBD,stroke-width:1px,color:#424242
```

```mermaid
flowchart LR
  subgraph CANVAS["CONTENT INTELLIGENCE — full canvas (operator view)"]
    direction LR
    T0((start)):::trigger
    T0 --> C0[load competitors.json + .env]:::action
    C0 --> W1[POST /ingest/blogs]:::action
    W1 --> D1[(raw JSON + manifest)]:::store
    D1 --> W2[POST /enrich]:::action
    W2 --> D2[(processed JSON)]:::store
    D2 --> W3[POST /index]:::action
    W3 --> D3[(LanceDB + BM25 + fingerprints)]:::store
    D3 --> W4[POST /generate/prompt]:::action
    W4 --> OUT((markdown blog)):::trigger
  end
  classDef trigger fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px
  classDef action fill:#E3F2FD,stroke:#1565C0,stroke-width:1px
  classDef store fill:#FFF3E0,stroke:#EF6C00,stroke-width:1px
```

```mermaid
flowchart LR
  subgraph ENTRY["entry surfaces → FastAPI"]
    direction LR
    U1((browser)):::trigger --> M[GET / dashboard]:::action
    U2((cli)):::trigger --> CL[blog_generation.cli]:::action
    U3((http client)):::trigger --> R[POST/GET /api/...]:::action
    M --> APP[FastAPI app + /static /templates]:::action
    CL --> API[router.py /api/v1/*]:::action
    R --> API
    APP --> API
  end
  classDef trigger fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px
  classDef action fill:#E3F2FD,stroke:#1565C0,stroke-width:1px
```

```mermaid
flowchart LR
  subgraph DEPS["what API touches"]
    direction LR
    API[router]:::action --> CFG[(competitors.json)]:::store
    API --> ENV[(.env Settings)]:::store
    API --> WEB{{HTTP fetch sites}}:::llm
    API --> YT{{YouTube transcript}}:::llm
    API --> OR{{OpenRouter}}:::llm
    API --> EMB{{BGE embedder local}}:::llm
    API --> CE{{cross-encoder local}}:::llm
    API --> RAW[(data/raw/**)]:::store
    API --> PR[(data/processed/**)]:::store
    API --> IDX[(data/embeddings/**)]:::store
  end
  classDef action fill:#E3F2FD,stroke:#1565C0,stroke-width:1px
  classDef store fill:#FFF3E0,stroke:#EF6C00,stroke-width:1px
  classDef llm fill:#F3E5F5,stroke:#7B1FA2,stroke-width:1px
```

```mermaid
flowchart TB
  subgraph PIPE["data pipeline — forward direction"]
    direction LR
    P0[config]:::action --> P1[1 ingest]:::action --> P2[2 enrich]:::action --> P3[3 index]:::action
    P3 -.query time.-> P4[4 retrieve]:::action --> P5[5 generate]:::action
  end
  classDef action fill:#E3F2FD,stroke:#1565C0,stroke-width:1px
```

```mermaid
flowchart LR
  subgraph S1["1 INGEST — ingest_blogs.py · POST /api/v1/ingest/blogs"]
    direction LR
    A((ingest)):::trigger --> B[load_competitors]:::action
    B --> C[discover links on blog_listing]:::action
    C --> D[filter blog_path_regex + same origin]:::action
    E{incremental + URL in manifest?}:::branch
    D --> E
    E -->|yes| F[skip fetch]:::action
    E -->|no| G[GET page + delay_s]:::action
    G --> H[trafilatura extract_main_text]:::action
    H --> I[build raw JSON document_id url title text hashes]:::action
    I --> J[(write data/raw/blog/...json)]:::store
    J --> K[(update manifest seen_urls)]:::store
    F --> L{limit?}:::branch
    K --> L
    L -->|more| C
    L -->|done| Z((return summary)):::trigger
  end
  classDef trigger fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px
  classDef action fill:#E3F2FD,stroke:#1565C0,stroke-width:1px
  classDef store fill:#FFF3E0,stroke:#EF6C00,stroke-width:1px
  classDef branch fill:#ECEFF1,stroke:#455A64,stroke-width:1px
```

```mermaid
flowchart LR
  subgraph YT["1b YOUTUBE — ingest_podcast_youtube.py · POST /api/v1/ingest/youtube"]
    direction LR
    Y0((ingest yt)):::trigger --> Y1[fetch transcript]:::action
    Y1 --> Y2[(data/raw/podcast/*.json)]:::store
    Y2 --> Y3[→ same enrich/index path as blogs]:::action
  end
  classDef trigger fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px
  classDef action fill:#E3F2FD,stroke:#1565C0,stroke-width:1px
  classDef store fill:#FFF3E0,stroke:#EF6C00,stroke-width:1px
```

```mermaid
flowchart TB
  subgraph S2["2 ENRICH — enrichment.py · POST /api/v1/enrich"]
    direction TB
    E0((enrich)):::trigger --> E1[scan raw blog podcast article]:::action
    E1 --> E2[optional competitor_id filter]:::action
    E2 --> E3{processed doc exists?}:::branch
    E3 -->|yes not force| E4[skip]:::action
    E3 -->|no or force| E5[ENRICHMENT_SYSTEM + body → OpenRouter T≈0.2]:::action
    E5 --> E6{strict JSON ok?}:::branch
    E6 -->|no| E7[fallback raw + default bucket + minimal tags]:::action
    E6 -->|yes| E8[text_clean summary bucket tags]:::action
    E7 --> E9[(write processed/documents/doc_id.json)]:::store
    E8 --> E9
    E9 --> E10[delay_s]:::action
    E4 --> E11{more files?}:::branch
    E10 --> E11
    E11 -->|yes| E1
    E11 -->|no| EZ((done)):::trigger
  end
  classDef trigger fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px
  classDef action fill:#E3F2FD,stroke:#1565C0,stroke-width:1px
  classDef store fill:#FFF3E0,stroke:#EF6C00,stroke-width:1px
  classDef branch fill:#ECEFF1,stroke:#455A64,stroke-width:1px
```

```mermaid
flowchart LR
  subgraph S3A["3 INDEX — chunking"]
    direction LR
    I0[prefer processed/*.json else raw]:::action --> I1[read text_clean or text]:::action
    I1 --> I2[chunk_text max_chars + overlap paragraph-aware]:::action
    I2 --> I3[chunk id = doc_id::cN]:::action
  end
  classDef action fill:#E3F2FD,stroke:#1565C0,stroke-width:1px
```

```mermaid
flowchart TB
  subgraph S3B["3 INDEX — build_index · POST /api/v1/index"]
    direction TB
    X0((index)):::trigger --> X1{rebuild true?}:::branch
    X1 -->|yes| X2[drop Lance table re-embed ALL]:::action
    X1 -->|no| X3{fingerprints + Lance missing?}:::branch
    X3 -->|yes| X4[full embed path]:::action
    X3 -->|no| X5[diff new changed removed doc_ids]:::action
    X5 --> X6[delete Lance rows removed/changed]:::action
    X6 --> X7[embed ONLY new/changed chunks]:::action
    X7 --> X8[append Lance rows + metadata columns]:::action
    X2 --> X9[rebuild BM25 from ENTIRE table → bm25.pkl]:::action
    X4 --> X9
    X8 --> X9
    X9 --> X10[(fingerprints + index_meta.json)]:::store
    X10 --> XZ((JSON mode counts full_reason)):::trigger
  end
  classDef trigger fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px
  classDef action fill:#E3F2FD,stroke:#1565C0,stroke-width:1px
  classDef store fill:#FFF3E0,stroke:#EF6C00,stroke-width:1px
  classDef branch fill:#ECEFF1,stroke:#455A64,stroke-width:1px
```

```mermaid
flowchart LR
  subgraph S4["4 RETRIEVE — retrieval.py (query time)"]
    direction LR
    IN((topic + filters)):::trigger --> Q[BGE query prefix + topic embed]:::action
    IN --> S2[BM25 topic tokens sparse_top_k]:::action
    Q --> D2[Lance vector dense_top_k]:::action
    D2 --> F{filters empty set?}:::branch
    S2 --> F
    F -->|yes| FB[drop filters]:::action
    F -->|no| RRF[RRF fuse ranks]:::action
    FB --> RRF
    RRF --> POOL[truncate rerank_pool]:::action
    POOL --> CE[cross-encoder pairs]:::action
    CE --> CUT[dynamic cut vs best score + min/max chunks]:::action
    CUT --> OUT((chunk texts + debug)):::trigger
  end
  classDef trigger fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px
  classDef action fill:#E3F2FD,stroke:#1565C0,stroke-width:1px
  classDef branch fill:#ECEFF1,stroke:#455A64,stroke-width:1px
```

```mermaid
flowchart TB
  subgraph S5["5 GENERATE — query_pipeline + blog_generator · POST /api/v1/generate/prompt"]
    direction TB
    G0((prompt)):::trigger --> G1[prompt_parse → OpenRouter JSON topic intent_stage filters extras]:::action
    G1 --> G2{skip_retrieval?}:::branch
    G2 -->|no| G3[retrieve_context]:::action
    G2 -->|yes| G4[empty chunks]:::action
    G3 --> G5[generate_blog blueprint by intent_stage + context excerpts]:::action
    G4 --> G5
    G5 --> G6{{OpenRouter write markdown}}:::llm
    G6 --> G7((response markdown parsed retrieval chunks)):::trigger
  end
  classDef trigger fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px
  classDef action fill:#E3F2FD,stroke:#1565C0,stroke-width:1px
  classDef branch fill:#ECEFF1,stroke:#455A64,stroke-width:1px
  classDef llm fill:#F3E5F5,stroke:#7B1FA2,stroke-width:1px
```

```mermaid
flowchart LR
  subgraph SEQ["sequence — POST /generate/prompt (one row = one hop)"]
    direction LR
    C[client]:::action --> R[router]:::action --> QP[query_pipeline]:::action
    QP --> PP[prompt_parse]:::action
    PP --> OR1[OpenRouter]:::action
    QP --> RET[retrieval]:::action
    RET --> LDB[(Lance)]:::store
    RET --> BM[(BM25)]:::store
    RET --> XR[reranker]:::action
    QP --> BG[blog_generator]:::action
    BG --> OR2[OpenRouter]:::action
    OR2 --> C
  end
  classDef action fill:#E3F2FD,stroke:#1565C0,stroke-width:1px
  classDef store fill:#FFF3E0,stroke:#EF6C00,stroke-width:1px
```

```mermaid
flowchart LR
  subgraph OPS["cold start — operator order"]
    direction LR
    O1((1)):::trigger --> A1[ingest/blogs]:::action --> D1[(raw)]:::store
    D1 --> O2((2)):::trigger --> A2[enrich]:::action --> D2[(processed)]:::store
    D2 --> O3((3)):::trigger --> A3[index incremental]:::action --> D3[(index)]:::store
    D3 --> O4((4)):::trigger --> A4[generate/prompt]:::action --> O5((markdown)):::trigger
  end
  classDef trigger fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px
  classDef action fill:#E3F2FD,stroke:#1565C0,stroke-width:1px
  classDef store fill:#FFF3E0,stroke:#EF6C00,stroke-width:1px
```

```mermaid
flowchart TB
  subgraph APIMAP["HTTP nodes"]
    direction LR
    subgraph RO["GET"]
      R1[/health]:::action
      R2[/v1/stats]:::action
      R3[/v1/documents/blogs]:::action
      R4[/]:::action
    end
    subgraph WO["POST pipeline"]
      W1[/v1/ingest/blogs]:::action
      W2[/v1/ingest/youtube]:::action
      W3[/v1/enrich]:::action
      W4[/v1/index]:::action
    end
    subgraph GEN["POST generate"]
      G1[/v1/generate/prompt RAG]:::action
      G2[/v1/generate/blog explicit]:::action
    end
  end
  classDef action fill:#E3F2FD,stroke:#1565C0,stroke-width:1px
```

```mermaid
flowchart LR
  subgraph FAIL["failure edges"]
    direction LR
    F1[missing API key]:::bad --> E1[ValueError]:::bad
    F2[429 rate limit]:::bad --> E2[HTTPError after retries]:::bad
    F3[index missing]:::bad --> E3[retrieve/file errors]:::bad
    F4[weak parsed topic]:::bad --> E4[bad context]:::bad
    F5[skip_retrieval true]:::bad --> E5[no grounding]:::bad
  end
  classDef bad fill:#FFEBEE,stroke:#C62828,stroke-width:1px
```
