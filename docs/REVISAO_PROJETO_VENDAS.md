# Revisão do Projeto_Vendas fornecido

Revisão realizada em **16/11/2026**, a pedido da equipe, para avaliar um segundo exemplo de comparação PostgreSQL × Redis.

**Conclusão:** o projeto é útil para explicar tabelas, hashes e relacionamentos de vendas, mas a versão recebida precisa de correções antes de sustentar a afirmação de que todos os CRUDs estão aprovados ou que a massa está correta. Para a demonstração pronta do Observatório IoT, use [este roteiro](DEMONSTRACAO_17_11.md) e `make crud`.

## O que foi executado

As dependências do `requirements.txt` foram instaladas em ambiente virtual separado. Foram usados uma cópia temporária dos scripts, os seis CSVs fornecidos e **dois contêineres exclusivos**, PostgreSQL 17 e Redis 8. O arquivo `.env` do projeto recebido não foi usado. Os arquivos originais e as bases do Observatório IoT foram preservados.

O schema e as referências carregaram. Em seguida, os dois carregadores originais concluíram a importação. Foram contados **1.400.015 registros lógicos em cada banco**, nas nove estruturas. As contagens também permaneceram iguais após os testes. Essa igualdade não comprova equivalência campo a campo nem consistência dos totais de vendas.

Foram executados os quatro programas CRUD originais, na ordem documentada, imediatamente após uma carga nova. A evidência estruturada está em [results/revisao_projeto_vendas.json](../results/revisao_projeto_vendas.json).

| CRUD original | Resultado reproduzido |
|---|---|
| Cliente | Falha por duplicidade de `id_cliente=1`. O programa captura o erro e termina com código 0. |
| Produto | Falha por duplicidade de `id_produto=1`, código 1. |
| Pedido | Falha por duplicidade de `id_pedido=1`, código 1. |
| Item do pedido | Fluxo executou e removeu o item temporário. O programa não confere automaticamente os valores após UPDATE. |

## Problemas e correções necessárias

### 1. Sequências de IDs após COPY

`carregar_postgres.py` importa IDs explícitos com `COPY`, mas não sincroniza as sequências das colunas identity. Após a carga, clientes e produtos têm IDs até 100.000, e pedidos até 500.000, enquanto as respectivas sequências continuam em 1, ainda não chamadas. O primeiro INSERT sem ID colide com a massa existente.

Depois da carga, sincronize as sequências antes de permitir novos cadastros. Para a tabela de clientes preenchida:

```sql
SELECT setval(
    pg_get_serial_sequence('cliente', 'id_cliente'),
    (SELECT max(id_cliente) FROM cliente),
    true
);
```

Aplique a mesma regra a endereço, telefone, produto e pedido; trate o caso de tabela vazia se o carregador também aceitar massas vazias. A correção deve fazer parte do carregador, e não depender de uma etapa manual esquecida. Veja a documentação oficial de [COPY](https://www.postgresql.org/docs/17/sql-copy.html) e [setval](https://www.postgresql.org/docs/17/functions-sequence.html).

### 2. Totais de pedidos inconsistentes

`gerar_pedidos()` sorteia quantidade e preço para calcular `valor_total`, mas `gerar_itens()` sorteia outros valores. Na massa recebida, **499.998 de 500.000 pedidos** têm `valor_total` diferente da soma de `quantidade × preco_unitario` de seus itens. A verificação percorreu os CSVs completos usando `Decimal`.

Exemplo: pedido 1 informa **R$ 1.568,07**, mas o seu item soma **R$ 7.979,40**. Não há desconto, frete ou outro ajuste no modelo que explique essa diferença.

Gere os itens primeiro e derive os totais deles, usando valores monetários exatos. Nas operações CRUD de itens, mantenha o total do pedido coerente. Acrescente uma validação automática de todos os totais antes da carga.

### 3. Aprovações fixas no gerador de evidências

`gerar_evidencias.py` escreve `APROVADO` para os quatro CRUDs por meio de valores literais. Ele não executa nem lê o resultado desses testes. Os tempos de carga também estão fixados no código, em vez de serem obtidos da execução atual.

Substitua os rótulos fixos por resultados de testes com assertions, falha com código diferente de zero e limpeza garantida em caso de erro. O fluxo atual de cliente mostra por que o código de saída, sozinho, também não é suficiente: ele captura uma falha e termina como sucesso para o sistema operacional. Leia os tempos do arquivo produzido pelo carregador e identifique a execução associada.

### 4. Equivalência e metodologia

A contagem por tabela é um primeiro controle. Adicione comparação dos campos, normalização de tipos e datas e verificação dos relacionamentos e índices Redis. O hash de cliente criado pelo CRUD também omite `data_cadastro`, presente na tabela e no CSV; os scripts comparam apenas parte dos campos visualmente.

Os tempos recebidos, **13,8412 s** e **37,6934 s**, referem-se à execução documentada pelo autor. Não devem ser apresentados como medidos nesta revisão. Aqui as cargas foram realizadas em paralelo, somente para reprodução funcional, sem finalidade de benchmark.

Para comparar desempenho, execute consultas equivalentes, repita as medições, controle o ambiente, verifique os resultados e registre os dados brutos. Espaço em disco PostgreSQL e memória Redis são métricas distintas; o README fornecido já explicita essa ressalva corretamente.

## Limites da revisão

Foram verificados carregamento, contagens das nove estruturas, sequências, os quatro fluxos CRUD e a consistência integral dos totais dos CSVs. Não foi feita validação integral campo a campo entre as duas bases, simulação de falhas durante todos os CRUDs ou benchmark de consultas deste segundo projeto. As correções acima são orientações; o código original recebido não foi reescrito nem incorporado ao repositório.
