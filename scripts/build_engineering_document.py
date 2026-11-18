"""Gera o Word da análise técnica a partir do Markdown revisado e diagramas PNG.

Autoria opcional: python-docx e Pillow; não é dependência da aplicação.
A versão final deve ser renderizada e conferida visualmente antes da entrega.
"""
from pathlib import Path
import re,textwrap
from docx import Document
from docx.shared import Inches,Pt,RGBColor,Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT,WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from PIL import Image
R=Path(__file__).resolve().parents[1]; src=R/'docs/engenharia/ANALISE_TECNICA_COMPLETA.md'
doc=Document(); sec=doc.sections[0];sec.page_width=Cm(21);sec.page_height=Cm(29.7);sec.top_margin=Cm(1.8);sec.bottom_margin=Cm(1.8);sec.left_margin=Cm(1.8);sec.right_margin=Cm(1.8)
styles=doc.styles
for s in ['Normal','Title','Subtitle','Heading 1','Heading 2','Heading 3','List Bullet']:
 styles[s].font.name='Noto Sans';styles[s].font.color.rgb=RGBColor(0,0,0)
styles['Normal'].font.size=Pt(10.5);styles['Normal'].paragraph_format.space_after=Pt(7);styles['Normal'].paragraph_format.line_spacing=1.12
styles['Caption'].font.color.rgb=RGBColor(0,0,0)
styles['Title'].font.size=Pt(26);styles['Title'].paragraph_format.space_after=Pt(14)
for n,size in [(1,16),(2,12),(3,11)]:
 s=styles[f'Heading {n}'];s.font.size=Pt(size);s.paragraph_format.space_before=Pt(14);s.paragraph_format.space_after=Pt(7);s.paragraph_format.keep_with_next=True
if 'Source Code' not in styles:
 st=styles.add_style('Source Code',1);st.font.name='DejaVu Sans Mono';st.font.size=Pt(8.2);st.font.color.rgb=RGBColor(0,0,0);st.paragraph_format.space_after=Pt(0);st.paragraph_format.space_before=Pt(0);st.paragraph_format.line_spacing=1.05
footer=sec.footer.paragraphs[0];footer.paragraph_format.space_before=Pt(6); footer.add_run('Observatório IoT   |   Engenharia reversa   |   ').font.size=Pt(8)
fld=OxmlElement('w:fldSimple');fld.set(qn('w:instr'),'PAGE');footer._p.append(fld)
props=doc.core_properties;props.title='Engenharia reversa do Observatório IoT';props.subject='Redis consultas testes e Dashboard';props.author='Observatório IoT';props.keywords='Redis PostgreSQL engenharia reversa Dashboard';props.comments=''
def safe(s):return s.replace('¹','1').replace('⁵','5')
def inline(p,t):
 t=safe(t)
 # References remain full and break after slash to keep source locations readable.
 pattern=r'(\[[^\]]+\]\([^\)]+\)|\*\*[^*]+\*\*|`[^`]+`)'
 for token in re.split(pattern,t):
  if not token:continue
  if token.startswith('[') and '](' in token:
   label,url=token[1:].split('](',1);url=url.removesuffix(')');label=label.replace('/','/\u200b')
   rr=p.add_run(label);rr.font.size=Pt(8.7) if url.startswith('/') else None
   rr.font.color.rgb=RGBColor(30,63,88)
   if url.startswith('https://'):
    hyperlink=OxmlElement('w:hyperlink');hyperlink.set(qn('r:id'),p.part.relate_to(url,RT.HYPERLINK,is_external=True))
    hyperlink.append(rr._r);p._p.append(hyperlink)
  elif token.startswith('**'):
   rr=p.add_run(token[2:-2]);rr.bold=True
  elif token.startswith('`'):
   rr=p.add_run(token[1:-1]);rr.font.name='DejaVu Sans Mono';rr.font.size=Pt(9)
  else:p.add_run(token)
def paragraph(t,style=None):
 p=doc.add_paragraph(style=style);inline(p,t);return p
lines=src.read_text().splitlines();i=0;figure=0;codecount=0
while i<len(lines):
 l=lines[i]
 if not l.strip():i+=1;continue
 if l.startswith('```'):
  lang=l[3:].strip();i+=1;buf=[]
  while i<len(lines) and not lines[i].startswith('```'):buf.append(lines[i]);i+=1
  if lang=='mermaid':
   names=['01_arquitetura','02_execucao','03_redis','04_testes','05_dashboard'];name=names[figure];figure+=1
   path=R/f'docs/engenharia/diagramas/{name}.png';im=Image.open(path);w,h=im.size; width=6.6;height=width*h/w
   if height>7.0:width=7.0*w/h
   pp=doc.add_paragraph();pp.alignment=WD_ALIGN_PARAGRAPH.CENTER;run=pp.add_run();run.add_picture(str(path),width=Inches(width));pp.paragraph_format.space_after=Pt(4)
   paragraph(f'Diagrama {figure}   Mermaid renderizado a partir do arquivo editável',style='Caption')
  else:
   codecount+=1
   for line in buf:
    p=doc.add_paragraph(style='Source Code');p.paragraph_format.widow_control=False
    p.add_run(safe(line or ' '))
   doc.add_paragraph().paragraph_format.space_after=Pt(2)
  i+=1;continue
 if l.startswith('|'):
  tablelines=[]
  while i<len(lines) and lines[i].startswith('|'):tablelines.append(lines[i]);i+=1
  cells=[[c.strip() for c in x.strip().strip('|').split('|')] for x in tablelines];cells=[x for x in cells if not all(re.fullmatch(r'[:\-]+',c) for c in x)]
  n=len(cells[0]);tab=doc.add_table(rows=0,cols=n);tab.alignment=WD_TABLE_ALIGNMENT.CENTER;tab.autofit=False
  if n==3:weights=[.24,.28,.48]
  elif n==2:weights=[.35,.65]
  elif n>=6:weights=[.11,.13]+[(.76/(n-2))]*(n-2)
  else:weights=[1/n]*n
  for col,weight in zip(tab.columns,weights):col.width=Inches(6.8*weight)
  for ri,values in enumerate(cells):
   row=tab.add_row(); trpr=row._tr.get_or_add_trPr();cant=OxmlElement('w:cantSplit');trpr.append(cant)
   if ri==0:
    repeat=OxmlElement('w:tblHeader');trpr.append(repeat)
   for ci,cell in enumerate(row.cells):
    cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER;cell.width=Inches(6.8*weights[ci]);tcpr=cell._tc.get_or_add_tcPr()
    borders=OxmlElement('w:tcBorders')
    for edge in ['top','left','bottom','right']:
     e=OxmlElement('w:'+edge);e.set(qn('w:val'),'single');e.set(qn('w:sz'),'4');e.set(qn('w:color'),'D9D9D9');borders.append(e)
    tcpr.append(borders);sh=OxmlElement('w:shd');sh.set(qn('w:fill'),'E5ECF3' if ri==0 else ('F5F7F9' if ri%2==0 else 'FFFFFF'));tcpr.append(sh)
    mar=OxmlElement('w:tcMar')
    for edge in ['top','bottom','left','right']:
     e=OxmlElement('w:'+edge);e.set(qn('w:w'),'85');e.set(qn('w:type'),'dxa');mar.append(e)
    tcpr.append(mar);p=cell.paragraphs[0];p.paragraph_format.space_after=Pt(1);p.paragraph_format.line_spacing=1.05
    val=values[ci] if ci<len(values) else '';inline(p,val)
    if re.fullmatch(r'[0-9.,M ×]+',val):p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    for run in p.runs:run.font.size=Pt(8.4 if n>=6 else 9);run.bold=ri==0
  doc.add_paragraph().paragraph_format.space_after=Pt(3)
  continue
 if l.startswith('# '):
  paragraph(l[2:],'Title');i+=1;continue
 if l.startswith('## '):
  title=l[3:];p=doc.add_paragraph(title,'Heading 1');p.paragraph_format.keep_with_next=True;i+=1;continue
 if l.startswith('### '):
  p=doc.add_paragraph(l[4:],'Heading 2');i+=1;continue
 if l.startswith('- '):paragraph(l[2:],'List Bullet');i+=1;continue
 text=l;i+=1
 while i<len(lines) and lines[i].strip() and not lines[i].startswith(('#','```','|','- ')):text+=' '+lines[i];i+=1
 paragraph(text)
for st in doc.styles:
 if st.type==1 and st.element.pPr is not None:
  for border in list(st.element.pPr.findall(qn('w:pBdr'))):st.element.pPr.remove(border)
for pp in doc.paragraphs:
 if pp.style.name=='Title' and pp._p.pPr is not None:
  for border in list(pp._p.pPr.findall(qn('w:pBdr'))):pp._p.pPr.remove(border)
out=R/'output/documentos/Analise_Tecnica_Completa_Redis_PostgreSQL.docx';out.parent.mkdir(parents=True,exist_ok=True);doc.save(out)
print(out);print('Diagramas',figure,'Trechos de código',codecount)
