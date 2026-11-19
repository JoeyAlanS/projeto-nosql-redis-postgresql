# Índice do trabalho

Atualização de 19/11: [Otimização Redis: estrutura, comandos, novos testes e limites](OTIMIZACAO_REDIS.md).

## Usar e apresentar

- [Engenharia reversa completa de Redis, consultas, testes e Dashboard](engenharia/ANALISE_TECNICA_COMPLETA.md), [PDF](../output/pdf/Analise_Tecnica_Completa_Redis_PostgreSQL.pdf) e [Word](../output/documentos/Analise_Tecnica_Completa_Redis_PostgreSQL.docx).
- [Dashboard: alterações, comparação visual e console](CONSOLE_DASHBOARD.md).
- [Comandos para testar os dados e as 10 mil leituras](COMANDOS_TESTES.md).
- [Roteiro de apresentação e VS Code](ROTEIRO_VSCODE.md).
- [Funcionamento e exemplos Redis](GUIA_CODIGO_REDIS.md).
- [Manual completo](MANUAL_COMPLETO.md), [PDF](../output/pdf/Manual_Completo_Observatorio_IoT.pdf) e [Word](../output/documentos/Manual_Completo_Observatorio_IoT.docx).
- [Apresentação PowerPoint](../output/apresentacao/Apresentacao_Final_Projeto_3.pptx) e [Canva](https://www.canva.com/design/DAHaf2M-EsI/rfjGTKd6PsB6jzMruNGYug/edit).

## Pesquisa, modelo e entregas

- [Conferência do documento com todos os requisitos do trabalho](CONFORMIDADE_TRABALHO.md).
- [Paradigma e pesquisa](01_pesquisa.md).
- [Modelagem e comparação](02_modelagem.md); diagramas em `modelos/`.
- [Massa de dados](03_dados.md).
- [Metodologia dos experimentos](04_experimentos.md).
- [Conferência dos requisitos](ENTREGAS.md); PDFs fornecidos em `fontes/`.
- [Revisão do Projeto Vendas enviado pelo aluno](REVISAO_PROJETO_VENDAS.md). Sua revisão é separada da implementação IoT.

## Testes de carga e gráficos

- [Resultados de 1 milhão × 5 milhões](COMPARACAO_1M_5M.md).
- [Como reproduzir a carga e os planos](TESTES_CARGA_1M_5M.md).
- [Gráficos Python: interpretação e reprodução](GRAFICOS_CARGA.md).
- [PDF da comparação](../output/pdf/Comparacao_Carga_1M_5M.pdf) e [PDF dos gráficos](../output/pdf/Graficos_Carga_1M_5M.pdf).
- [Medições brutas e planos](../results/escala/); [PNG e SVG](../output/graficos/).

## Localizar evidências

- `results/verification.json`: contagem, igualdade de todas as leituras e índices Redis.
- `results/tests.log`: testes de integração.
- `results/dashboard/`: operações enviadas pela nova interface e verificação visual.
- `results/console_operacoes.json`: primeira versão do console e seus testes de erro.
- `output/MANIFESTO_ENTREGA.json`: caminhos, tamanhos e SHA-256 dos arquivos de entrega.

Para reconstruir o pacote local: `make package`. Para validar o código e os resultados: `make check`. A entrega no sistema da disciplina continua a cargo da equipe.
