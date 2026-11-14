"""PDF de projeção com as renderizações do PPTX final já inspecionadas."""
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

root=Path(__file__).resolve().parents[1]
slides=sorted((root/'tmp/slides').glob('slide-*.png'))
assert len(slides)==14
target=root/'output/pdf/Slides_Projeto_3.pdf'
c=canvas.Canvas(str(target),pagesize=(960,540))
c.setTitle('Projeto 3 - Redis e PostgreSQL')
for slide in slides:
    c.drawImage(ImageReader(str(slide)),0,0,width=960,height=540)
    c.showPage()
c.save()
print(target)
