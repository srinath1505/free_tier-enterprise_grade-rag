import json
import os
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import simpleSplit

SQUAD_FILE = "data/squad_dev.json"
OUTPUT_DIR = "data"

def generate_squad_pdfs(num_articles=5):
    if not os.path.exists(SQUAD_FILE):
        print(f"Error: {SQUAD_FILE} not found. Run benchmark script first to download it.")
        return

    with open(SQUAD_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    articles = data['data']
    
    print(f"Generating {num_articles} PDFs from SQuAD data...")
    
    for i in range(min(num_articles, len(articles))):
        article = articles[i]
        title = article['title']
        filename = f"squad_doc_{i}_{title.replace(' ', '_').replace('/', '-')}.pdf"
        filepath = os.path.join(OUTPUT_DIR, filename)
        
        c = canvas.Canvas(filepath, pagesize=letter)
        width, height = letter
        
        # Title
        c.setFont("Helvetica-Bold", 16)
        c.drawString(72, height - 72, title)
        
        # Content
        c.setFont("Helvetica", 12)
        y = height - 100
        
        full_text = ""
        for paragraph in article['paragraphs']:
            full_text += paragraph['context'] + "\n\n"
            
        # Simple text wrapping
        lines = simpleSplit(full_text, "Helvetica", 12, width - 144)
        
        for line in lines:
            if y < 72:
                c.showPage()
                y = height - 72
                c.setFont("Helvetica", 12)
            c.drawString(72, y, line)
            y -= 14
            
        c.save()
        print(f"Created: {filepath}")

if __name__ == "__main__":
    generate_squad_pdfs()
