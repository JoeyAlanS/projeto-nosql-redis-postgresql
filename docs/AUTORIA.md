# Atualizar os documentos de entrega

Os PDFs e o PPTX já estão prontos em `output/`. A aplicação e os testes de integração precisam somente do Docker; as ferramentas abaixo são opcionais e servem para regenerar os documentos.

## Relatórios PDF

Use Python 3.11 ou superior com `reportlab` e `Pillow`, fonte Noto Sans e o executável `rsvg-convert` (librsvg). Em Debian/Ubuntu, a fonte fica normalmente em `/usr/share/fonts/truetype/noto`; em Arch, em `/usr/share/fonts/noto`. Para outro diretório, defina `IOT_FONT_DIR`, contendo `NotoSans-Regular.ttf` e `NotoSans-Bold.ttf`.

Depois de atualizar os testes, a verificação, o benchmark e as capturas:

```bash
python3 scripts/build_models.py
python3 scripts/summarize_results.py
python3 scripts/build_documents.py
```

O gerador substitui os relatórios derivados, preservando o PDF original da Entrega 1. Confira a renderização das páginas antes da entrega. A identificação vem de `docs/identificacao.json`. Os textos interpretativos e o roteiro precisam ser revisados se o cenário ou a conclusão do benchmark mudar.

## Apresentação editável

O PPTX foi criado com `@oai/artifact-tool`, disponível no runtime de autoria do Codex, e validado pelas ferramentas da skill de apresentações. Esse runtime não é necessário para abrir ou editar o arquivo com PowerPoint ou LibreOffice.

Para repetir a geração no ambiente de autoria, obtenha os caminhos do runtime e da skill de apresentações. Defina `IOT_ARTIFACT_RUNTIME` para a pasta `dependencies` (com `node/node_modules` e `python/bin/python3`) e `IOT_PRESENTATION_SKILL` para a pasta da skill (com `container_tools`). Não há caminho pessoal fixo no código.

```bash
IOT_DECK_NAME=Apresentacao_Revisada.pptx node scripts/build_slides.mjs
python3 scripts/export_slide_pdf.py
```

O primeiro comando requer as duas variáveis de ambiente descritas acima, Node.js compatível com o runtime e Noto Sans instalada. Use um nome ainda inexistente: o finalizador evita sobrescrever apresentações já validadas. Confira todas as imagens geradas em `tmp/slides/` e, ao adotar a revisão, atualize o arquivo final referenciado na auditoria. O segundo comando gera o PDF a partir dessas imagens.

## Complemento de volume e carga: 1M e 5M

Depois dos ensaios isolados, use o ambiente Python de autoria com ReportLab e Noto Sans para atualizar o complemento em Markdown e PDF:

```bash
python3 -m scripts.compare_scales --summarize-only
python3 -m scripts.build_scale_report
```

O primeiro comando valida as amostras brutas e os hashes e reconstitui o resumo; o segundo gera `docs/COMPARACAO_1M_5M.md` e `output/pdf/Comparacao_Carga_1M_5M.pdf`. Confira as seis páginas renderizadas antes de distribuir a revisão. O experimento original em `results/benchmark.json` permanece independente.

## Gráficos em Python

As dependências de gráficos ficam separadas das da aplicação:

```bash
python3 -m venv .venv-graficos
.venv-graficos/bin/python -m pip install -r requirements-graficos.txt
make graficos
```

O comando valida os dados brutos e gera seis PNGs, seis SVGs e um PDF com seis páginas. O guia `docs/GRAFICOS_CARGA.md` explica as medidas, escalas e falas para apresentar. Confira as imagens antes de distribuir uma revisão.

## Revisar a análise técnica

O texto da engenharia reversa está em `docs/engenharia/ANALISE_TECNICA_COMPLETA.md`. Após editar o código, confira os trechos, caminhos e linhas citados. Os cinco diagramas editáveis estão em `docs/engenharia/diagramas/`; suas imagens PNG devem corresponder aos arquivos Mermaid.

No ambiente de autoria com python-docx e Pillow, `python3 -m scripts.build_engineering_document` gera o Word. Renderize o Word para PDF e confira todas as páginas antes de distribuir. `python3 -m scripts.build_documents` atualiza os PDFs acadêmicos, incluindo os resultados 1M/5M e a matriz `docs/CONFORMIDADE_TRABALHO.md`.

Com os bancos ativos e sem escritas concorrentes, `make verify` seguido de `docker compose exec -T app python -m scripts.validate_documentation` captura contagens, tipos SQL, equivalência das consultas e dos manifestos em `results/documentation_validation.json`. Essa validação não repete os benchmarks. Os manifestos de cargas antigas devem estar completos antes dessa conferência.

## Gerar o pacote atualizado

O resumo das melhorias e rotas é gerado por `python3 scripts/build_reading_summary.py`, no ambiente opcional de autoria com `python-docx`. Ele lê as medianas da central em `results/live/benchmark.json`; as explicações de código e os resultados históricos exigem revisão quando esses caminhos forem alterados. Renderize o Word, confira todas as páginas e copie o PDF aprovado para `output/pdf/Resumo_Melhorias_Rotas_Redis_PostgreSQL.pdf` antes de recompor o pacote.

```bash
make audit
make package
```

O pacote inclui código, evidências, PDFs, slides e `data/readings.csv.gz` quando a massa local foi gerada. O manifesto registra SHA-256 e tamanho dos arquivos. Ele descreve o ZIP, não o estado de um checkout sem os dados gerados. Não inclua `.env`, volumes Docker, `node_modules` ou arquivos temporários na entrega.
