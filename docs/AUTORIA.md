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

## Pacote

```bash
make audit
make package
```

O pacote inclui código, evidências, PDFs, slides e `data/readings.csv.gz` quando a massa local foi gerada. O manifesto registra SHA-256 e tamanho dos arquivos. Ele descreve o ZIP, não o estado de um checkout sem os dados gerados. Não inclua `.env`, volumes Docker, `node_modules` ou arquivos temporários na entrega.
