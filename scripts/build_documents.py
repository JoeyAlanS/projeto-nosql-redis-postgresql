"""Gera os relatórios PDF a partir dos textos e das evidências medidas.

Dependências de autoria: reportlab, pillow e rsvg-convert.
O sistema da aplicação não precisa dessas bibliotecas.
"""
import json
import os
import re
import textwrap
import subprocess
from datetime import datetime
from html import escape
from pathlib import Path
from PIL import Image as PILImage

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image,
                                Table, TableStyle, Preformatted, KeepTogether)

ROOT=Path(__file__).resolve().parents[1]
REVISED_AT='18 NOV 2026'
OUT=ROOT/'output/pdf'; OUT.mkdir(parents=True,exist_ok=True)
TMP=ROOT/'tmp/pdfs'; TMP.mkdir(parents=True,exist_ok=True)
FONT=Path(os.getenv('IOT_FONT_DIR', '/usr/share/fonts/noto'))
if not FONT.exists():
    FONT=Path('/usr/share/fonts/truetype/noto')
pdfmetrics.registerFont(TTFont('Noto',str(FONT/'NotoSans-Regular.ttf')))
pdfmetrics.registerFont(TTFont('Noto-Bold',str(FONT/'NotoSans-Bold.ttf')))
pdfmetrics.registerFontFamily('Noto',normal='Noto',bold='Noto-Bold',italic='Noto',boldItalic='Noto-Bold')
styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='Body',fontName='Noto',fontSize=9.5,leading=13.5,spaceAfter=7,textColor=colors.HexColor('#233c49')))
styles.add(ParagraphStyle(name='BodyCompact',parent=styles['Body'],leading=13,spaceAfter=6))
styles.add(ParagraphStyle(name='H1x',fontName='Noto-Bold',fontSize=21,leading=27,spaceBefore=12,spaceAfter=16,keepWithNext=True,textColor=colors.HexColor('#173d4b')))
styles.add(ParagraphStyle(name='H2x',fontName='Noto-Bold',fontSize=13,leading=18,spaceBefore=14,spaceAfter=9,keepWithNext=True,textColor=colors.HexColor('#16846d')))
styles.add(ParagraphStyle(name='Cellx',fontName='Noto',fontSize=7.6,leading=11,spaceAfter=0,wordWrap='CJK'))
styles.add(ParagraphStyle(name='Captionx',fontName='Noto',fontSize=8,leading=12,spaceAfter=12,textColor=colors.HexColor('#637c8c')))
styles.add(ParagraphStyle(name='Codex',fontName='Noto',fontSize=7,leading=10,spaceAfter=12,backColor=colors.HexColor('#f2f5f7'),borderPadding=8))


def fmt(v,digits=3):
    return f'{v:,.{digits}f}'.replace(',','X').replace('.',',').replace('X','.')


def rich(text):
    text=escape(text).replace('`','')
    text=re.sub(r'\*\*(.+?)\*\*',r'<b>\1</b>',text)
    return text


def table(rows,compact=False):
    ncols=len(rows[0]); available=A4[0]-96
    padding=4 if compact else 6
    if ncols==2:widths=[available*.33,available*.67]
    elif ncols==3:widths=[available*.23,available*.385,available*.385]
    elif ncols==4:widths=[available*.17,available*.35,available*.24,available*.24]
    elif ncols==5:widths=[available*.13,available*.26,available*.2,available*.2,available*.21]
    else:widths=[available/ncols]*ncols
    t=Table([[Paragraph(rich(c),styles['Cellx']) for c in row] for row in rows],colWidths=widths,repeatRows=1,hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e6f4ee')),
                          ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f5f7f9')]),
                          ('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),padding),
                          ('BOTTOMPADDING',(0,0),(-1,-1),padding),('LINEBELOW',(0,0),(-1,0),.6,colors.HexColor('#bad3c8'))]))
    return [t,Spacer(1,12)]


def diagram(name,caption):
    svg=ROOT/'docs/modelos'/f'{name}.svg'; png=TMP/f'{name}.png'
    subprocess.run(['rsvg-convert','-w','1650','-h','900','-o',str(png),str(svg)],check=True)
    return [Image(str(png),width=499,height=272),Paragraph(caption,styles['Captionx'])]


def markdown(text,compact=False):
    lines=text.splitlines();story=[];i=0
    while i<len(lines):
        line=lines[i].strip()
        if not line:i+=1;continue
        if line.startswith('```'):
            language=line[3:];i+=1;code=[]
            while i<len(lines) and not lines[i].strip().startswith('```'):
                code.append(lines[i]);i+=1
            i+=1
            if language=='mermaid':
                name='relacional' if any('erDiagram' in l for l in code) else 'redis'
                story+=diagram(name,'Modelo da implementação. Fonte: modelagem e código do projeto.')
            else:
                wrapped='\n'.join('\n'.join(textwrap.wrap(l,width=100,replace_whitespace=False,drop_whitespace=False)) if len(l)>100 else l for l in code)
                story.append(Preformatted(escape(wrapped),styles['Codex']))
            continue
        if line.startswith('|'):
            rows=[]
            while i<len(lines) and lines[i].strip().startswith('|'):
                row=[c.strip() for c in lines[i].strip().strip('|').split('|')]
                if not all(re.fullmatch(r':?-+:?',c) for c in row):rows.append(row)
                i+=1
            if len(rows)>12 and story and isinstance(story[-1],Paragraph):
                # Deixa a tabela longa ocupar o espaço da página do seu título.
                story[-1].keepWithNext=False
            story+=table(rows,compact=compact);continue
        if line.startswith('# '):story.append(Paragraph(rich(line[2:]),styles['H1x']));i+=1;continue
        if line.startswith('## '):story.append(Paragraph(rich(line[3:]),styles['H2x']));i+=1;continue
        if line.startswith('### '):story.append(Paragraph(rich(line[4:]),styles['H2x']));i+=1;continue
        paragraph=[line];i+=1
        if not line.startswith('- ') and not re.match(r'^\d+\.',line):
            while i<len(lines) and lines[i].strip() and not lines[i].strip().startswith(('#','|','```','- ')):
                paragraph.append(lines[i].strip());i+=1
        story.append(Paragraph(rich(' '.join(paragraph)),styles['BodyCompact' if compact else 'Body']))
    return story


def footer(canvas,doc):
    canvas.saveState();w,h=A4
    canvas.setStrokeColor(colors.HexColor('#dce5e8'));canvas.line(48,43,w-48,43)
    canvas.setFont('Noto',7);canvas.setFillColor(colors.HexColor('#637c8c'))
    canvas.drawString(48,29,'OBSERVATÓRIO IoT / PROJETO 3 / REVISÃO '+REVISED_AT)
    canvas.drawRightString(w-48,29,str(doc.page))
    if doc.page>1:canvas.drawString(48,h-30,'Redis e PostgreSQL - pesquisa, implementação e evidências')
    canvas.restoreState()


def cover(title,subtitle):
    identity=json.loads((ROOT/'docs/identificacao.json').read_text())
    body=[Spacer(1,95),Paragraph('PROJETO 3 / BANCOS DE DADOS NoSQL',styles['Captionx']),
          Paragraph(title,ParagraphStyle('Cover',parent=styles['H1x'],fontSize=29,leading=37)),
          Paragraph(subtitle,ParagraphStyle('Sub',parent=styles['Body'],fontSize=13,leading=20)),Spacer(1,30),
          Paragraph('Tema 3: chave-valor / cache<br/>Redis, Memcached e PostgreSQL',styles['Body'])]
    details=[]
    if identity.get('curso'):details.append('Curso: '+identity['curso'])
    if identity.get('professor'):details.append('Professor(a): '+identity['professor'])
    if identity.get('integrantes'):details.append('Equipe: '+', '.join(identity['integrantes']))
    body.append(Paragraph('<br/>'.join(map(rich,details)) if details else 'Identificação acadêmica: a equipe deve preencher docs/identificacao.json antes da submissão.',styles['Captionx']))
    body+=[Spacer(1,40),Paragraph('Revisão de 18 de novembro de 2026. A aplicação principal usa 1.000.000 de leituras por banco. Os ensaios isolados de 1 e 5 milhões e a verificação atual são identificados separadamente, preservando as datas das medições.',styles['Body']),PageBreak()]
    return body


def save(filename,title,subtitle,chapters):
    story=cover(title,subtitle)
    for index,chapter in enumerate(chapters):
        if index:story.append(PageBreak())
        story+=markdown((ROOT/chapter).read_text(),compact=chapter.endswith(('evidencias_dados.md','resultados.md')))
        if chapter.endswith('01_pesquisa.md'):story+=diagram('arquitetura','Arquitetura efetivamente implementada. Sem sincronização contínua entre as bases.')
        if chapter.endswith('04_experimentos.md'):
            story += [PageBreak(),Paragraph('Dashboard em execução',styles['H2x']),
                      Image(str(ROOT/'results/evidencias/dashboard_completo.png'),width=499,height=611),
                      Paragraph('Captura registrada da execução local. Indicadores e consultas acessam os dois bancos; o gráfico de medianas usa o experimento salvo.',styles['Captionx'])]
        if chapter.endswith('COMPARACAO_1M_5M.md'):
            for name,label in [('01_tempo_carga','Tempo de carga inicial'),
                               ('02_mediana_consultas','Medianas das três consultas'),
                               ('03_vazao_concorrencia','Vazão HTTP por concorrência')]:
                image_path=ROOT/'output/graficos'/f'{name}.png'
                with PILImage.open(image_path) as image:
                    image_height=499*image.height/image.width
                story += [PageBreak(),Paragraph(label,styles['H2x']),
                          Image(str(image_path),width=499,height=image_height),
                          Paragraph('Gráfico Python derivado dos resultados brutos de 1M e 5M. As medições históricas não foram repetidas na revisão documental.',styles['Captionx'])]
    doc=SimpleDocTemplate(str(OUT/filename),pagesize=A4,rightMargin=48,leftMargin=48,topMargin=52,bottomMargin=56,
                          title=title,author='Projeto 3 - Equipe de Banco de Dados')
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    print(filename)


def main():
    # Cada entrega parcial é autocontida e cita as fontes comuns.
    save('Entrega_2_Modelagem_e_Comparacao.pdf','Modelagem e comparação técnica','Entrega de 17/11: problema, vantagens, limitações e modelos dos dois bancos.',
         ['docs/02_modelagem.md','docs/referencias.md'])
    save('Entrega_3_Massa_de_Dados.pdf','Massa de dados e carga','Entrega de 19/11: geração, integridade, volumes e evidências da massa.',
         ['docs/03_dados.md','docs/evidencias_dados.md','docs/CONFORMIDADE_TRABALHO.md'])
    save('Entrega_4_Experimentos_e_Dashboard.pdf','Experimentos e dashboard','Entrega de 24/11: método, medições, aplicação funcional e demonstração.',
         ['docs/04_experimentos.md','docs/resultados.md','docs/COMPARACAO_1M_5M.md','docs/CONFORMIDADE_TRABALHO.md','docs/roteiro_apresentacao.md','docs/referencias.md'])
    save('Relatorio_Completo_Projeto_3.pdf','Observatório IoT','Análise comparativa de Redis e PostgreSQL com grande volume de dados e dashboard funcional.',
         ['docs/01_pesquisa.md','docs/02_modelagem.md','docs/03_dados.md','docs/evidencias_dados.md',
          'docs/04_experimentos.md','docs/resultados.md','docs/COMPARACAO_1M_5M.md',
          'docs/CONFORMIDADE_TRABALHO.md','docs/roteiro_apresentacao.md','docs/referencias.md'])


if __name__=='__main__':main()
