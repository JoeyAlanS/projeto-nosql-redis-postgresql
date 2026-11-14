"""Diagramas vetoriais editáveis em SVG, sem serviços externos."""
from pathlib import Path
from html import escape

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/modelos'
OUT.mkdir(exist_ok=True)

def base(title, subtitle):
    return [f'<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="600" viewBox="0 0 1100 600"><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8" fill="#5b7a89"/></marker></defs><rect width="1100" height="600" fill="#f6f8fa"/><text x="45" y="50" font-family="sans-serif" font-size="27" font-weight="700" fill="#172f40">{title}</text><text x="45" y="80" font-family="sans-serif" font-size="14" fill="#637c8c">{subtitle}</text>']

def box(parts,x,y,w,title,lines):
    height=64+len(lines)*30
    parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{height}" rx="7" fill="white" stroke="#cbd6dc"/><path d="M{x+7},{y} H{x+w-7} Q{x+w},{y} {x+w},{y+7} V{y+47} H{x} V{y+7} Q{x},{y} {x+7},{y}" fill="#173d4b"/><text x="{x+18}" y="{y+30}" font-family="sans-serif" font-size="19" font-weight="700" fill="white">{escape(title)}</text>')
    for i,line in enumerate(lines):
        parts.append(f'<text x="{x+18}" y="{y+76+i*30}" font-family="sans-serif" font-size="16" fill="#29434d">{escape(line)}</text>')

def line(parts,d,label='',x=0,y=0):
    parts.append(f'<path d="{d}" fill="none" stroke="#5b7a89" stroke-width="2" marker-end="url(#arrow)"/>')
    if label:parts.append(f'<text x="{x}" y="{y}" font-family="sans-serif" font-size="15" fill="#58717d">{escape(label)}</text>')

def finish(parts,name):
    parts.append('</svg>');(OUT/name).write_text(''.join(parts))

p=base('Modelo relacional','PostgreSQL: metadados normalizados e integridade declarativa')
box(p,65,145,340,'SENSORS',['PK id : integer','name : text','location : text','active : boolean'])
box(p,650,145,380,'READINGS',['PK id : bigint','FK sensor_id : integer','ts : bigint / UTC','temperature_centi : integer','humidity_centi : integer','UNIQUE (sensor_id, ts)'])
line(p,'M405 265 H650','1 sensor registra N leituras',430,245)
p.append('<text x="65" y="505" font-family="sans-serif" font-size="16" fill="#29434d">Busca por ID: chave primária. Histórico: índice que cobre sensor, instante e valores.</text>')
finish(p,'relacional.svg')

p=base('Modelo chave-valor','Redis: hashes de objetos, índice temporal por sensor e unicidade mantida por Lua')
box(p,45,130,310,'iot:sensor:501 / hash',['id, name, location, active'])
box(p,45,330,310,'iot:sensors / set',['IDs dos 1.000 sensores'])
box(p,420,130,310,'Índice temporal / sorted set',['iot:sensor:501:readings','score = instante UTC','member = ID da leitura'])
box(p,420,350,310,'Unicidade / hash',['iot:unique:501','instante = ID da leitura'])
box(p,800,235,260,'iot:reading:500501',['id, sensor_id, ts','temperature_centi','humidity_centi'])
line(p,'M200 330 V224');line(p,'M355 180 H420');line(p,'M730 210 H765 V275 H800')
line(p,'M730 425 H765 V375 H800')
p.append('<text x="45" y="560" font-family="sans-serif" font-size="15" fill="#29434d">Lua mantém hash e índices em uma operação atômica. Instância única, sem TTL ou expulsão automática.</text>')
finish(p,'redis.svg')

p=base('Arquitetura da aplicação','O mesmo CSV canônico abastece as duas bases, e o dashboard consulta uma fonte por operação')
box(p,45,190,250,'Dashboard web',['Indicadores e filtros','Comparação de tempos'])
box(p,425,190,245,'API FastAPI',['Validação e contratos','Medição do cliente','CRUD por fonte'])
box(p,805,125,250,'PostgreSQL',['Tabelas e índices','WAL e restrições'])
box(p,805,350,250,'Redis',['Hashes e sorted sets','AOF everysec e Lua'])
line(p,'M295 250 H425','HTTP / JSON',310,235)
line(p,'M670 250 H740 V185 H805','SQL',750,170)
line(p,'M670 290 H740 V410 H805','RESP',750,395)
p.append('<text x="45" y="555" font-family="sans-serif" font-size="16" fill="#29434d">Scripts locais: geração, carga, verificação de 100% da massa, CRUD e benchmark com ordem alternada.</text>')
finish(p,'arquitetura.svg')
print('3 modelos SVG gerados em',OUT)
