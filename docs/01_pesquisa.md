# Entrega 1 - Pesquisa e fundamentação

## Paradigma e adequação

O paradigma chave-valor relaciona uma chave identificadora a um valor. A aplicação define padrões de acesso e constrói as chaves necessárias. A leitura por identificador dispensa junções, enquanto consultas por outros atributos precisam de índices ou modelagem adicional. Cache, sessões, contadores, carrinhos e estados recentes de sensores são aplicações adequadas. Esquema flexível exige validação na aplicação e não dispensa regras de integridade.

O Redis amplia esse modelo com hashes, listas, sets, sorted sets e streams. O projeto usa hashes para objetos e sorted sets para índices temporais. O Memcached permanece como comparação teórica: seu modelo tradicional atende cache distribuído de itens simples, sem oferecer a mesma combinação de estruturas, persistência e replicação do Redis. Não há uma terceira base Memcached no experimento; o enunciado exige um NoSQL comparado com um relacional. [1, 2, 3]

## Visão geral, fornecedor e licença

Redis é distribuído pela Redis Ltd. e pelo projeto Redis Open Source. Instalação: https://redis.io/docs/latest/operate/oss_and_stack/install/. Para a família 8, consultar as alternativas AGPLv3, RSALv2 e SSPLv1 na licença da distribuição efetivamente usada. O arquivo de versões e os digests das imagens identificam a distribuição executada. Memcached é um projeto aberto, disponível em https://memcached.org/, sob BSD de três cláusulas. PostgreSQL é mantido pelo PostgreSQL Global Development Group, disponível em https://www.postgresql.org/download/ e distribuído sob a PostgreSQL License. [4, 5, 6]

## Arquitetura e consulta

O servidor Redis recebe comandos por TCP e trabalha principalmente sobre dados em RAM. A execução de comandos e scripts é predominantemente sequencial por instância. I/O e persistência podem usar outros mecanismos. Hashes permitem HSET/HGETALL, sorted sets permitem ZADD/ZRANGEBYSCORE e Lua reúne várias operações em uma execução atômica. Scripts longos bloqueiam outras operações e constituem uma limitação concreta para agregação neste projeto. [1, 7]

RDB cria snapshots e AOF registra operações. A configuração utilizada ativa AOF com appendfsync everysec, desativa snapshots periódicos e usa noeviction. Isso evita expulsão de dados por política de cache, mas não impede falhas de alocação se a RAM acabar. A sincronização periódica pode perder aproximadamente um segundo de escritas em certas falhas, podendo variar conforme o sistema. Ela não oferece a mesma garantia de confirmação de uma configuração PostgreSQL com fsync e synchronous_commit ativos. [8]

## Escalabilidade

Escala vertical depende principalmente de memória e capacidade por instância. Redis Cluster distribui chaves em 16.384 slots. Réplicas e Sentinel podem melhorar disponibilidade, com replicação assíncrona por padrão. O modelo prático deste projeto usa uma única instância e scripts com várias chaves sem hash tags: não pode ser migrado diretamente para Cluster. Seria necessário repartir por sensor, redesenhar transações e agregar resultados entre partições. Memcached distribui os itens entre servidores principalmente por decisão do cliente, no modelo tradicional. PostgreSQL admite réplicas de leitura e particionamento, mas distribuição horizontal transparente não decorre apenas de criar um índice. [3, 9, 10]

## Aplicações reais

- **MEO:** caso publicado pela Redis descreve cache para serviços OTT, autenticação e personalização em uma plataforma de transmissão. [11]
- **Axis Bank:** caso publicado pelo fornecedor descreve acesso rápido a informações bancárias integradas a sistemas tradicionais. [12]
- **WRSTBND:** mantém PostgreSQL como sistema de registro e Redis para consultas frequentes, sincronização de dispositivos e painéis de eventos. O relato ilustra complementaridade entre os bancos. [13]

Os casos são relatos do fornecedor e não constituem experimentos independentes da equipe. O PDF original da primeira entrega foi preservado em `docs/fontes/`. A implementação e as medições deste repositório complementam aquela proposta teórica.

## Comparação inicial e plano executado

O cenário escolhido é monitoramento ambiental de um campus. Um CSV canônico abastece PostgreSQL e Redis. Uma API expõe operações equivalentes e o dashboard consulta ambos os bancos. Scripts automatizam geração, carga, verificação integral, CRUD e benchmark. O relatório final consolida a fundamentação, os modelos e os resultados medidos. As referências numeradas estão em `docs/referencias.md`.
