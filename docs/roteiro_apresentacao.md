# Roteiro de apresentação - 20 minutos

## Preparação

Execute make up, abra http://localhost:8000 e confira /api/health. Preencha a identificação da equipe. Tenha o CSV bruto, a verificação integral e os planos PostgreSQL disponíveis. Os slides incluem notas de apresentação e fontes.

## Conceitos e comparação - 0 a 8 minutos

**0:00-1:00 - Cenário.** Apresente o campus e as leituras de temperatura/umidade. Defina registro lógico.

**1:00-2:30 - Paradigma.** Explique chave-valor, hashes e sorted sets. Distinga Redis de Memcached e cite os relatos de mercado.

**2:30-4:00 - Arquitetura.** Mostre frontend, API e bancos independentes. Explique AOF everysec, WAL, noeviction e os limites da instância única.

**4:00-6:00 - Modelagem.** Compare FK/UNIQUE e índices PostgreSQL com hashes, índice temporal e validação Lua. Mostre os diagramas.

**6:00-8:00 - Dados e método.** Apresente um milhão de leituras, seed 42 e hashes iguais. Explique cinco aquecimentos, 30 repetições e ordem alternada.

## Demonstração - 8 a 16 minutos

**8:00-10:00 - Filtros.** Selecione Biblioteca, Sensor 0002 e período de 01/11/2026 até 12:00 UTC. Confira as 145 leituras.

**10:00-11:30 - Fontes.** Alterne PostgreSQL/Redis mantendo os filtros. Compare indicadores e tempos retornados.

**11:30-13:00 - Busca.** Compare o ID 500001 ao vivo. Explique que uma amostra pode oscilar.

**13:00-14:30 - Experimento.** Abra as medianas e o CSV bruto. Explique a vantagem Redis na Q1 e PostgreSQL nas Q2/Q3.

**14:30-16:00 - CRUD.** Execute docker compose exec -T app python -m scripts.crud_demo. Mostre results/crud.json, os hashes e um plano com índice.

## Conclusões e perguntas - 16 a 20 minutos

**16:00-18:00 - Escolha.** Relacione padrão de acesso, integridade, RAM e durabilidade. Discuta a composição entre os bancos e o bloqueio de Lua na agregação.

**18:00-20:00 - Perguntas.** Prepare respostas sobre equivalência, volume, cache aquecido, concorrência, falhas e migração para Cluster.

Se um resultado ao vivo oscilar, preserve-o e explique as medianas. Se um serviço cair, consulte docker compose ps e make logs e retome com make up. As capturas documentam o ensaio anterior; a demonstração exigida usa o sistema funcionando.
