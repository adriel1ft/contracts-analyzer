from fastapi import APIRouter, HTTPException
from pathlib import Path
import fitz  # PyMuPDF
import re

router = APIRouter()

UPLOAD_DIR = Path("temp/uploads")

def find_positions_in_pdf(pdf_path: Path, pattern: str):
    """Retorna coordenadas (bounding boxes) onde o padrão acontece."""
    results = []
    doc = fitz.open(pdf_path)

    for page_num, page in enumerate(doc, start=1):
        text_instances = page.search_for(pattern)

        for inst in text_instances:
            results.append({
                "page": page_num,
                "x": inst.x0,
                "y": inst.y0,
                "width": inst.width,
                "height": inst.height,
                "text": page.get_textbox(inst)
            })

    doc.close()
    return results

@router.post("/anonymize/positions/{mode}/{file_id}")
def get_sensitive_positions(mode:str, file_id: str):
    pdf_path = UPLOAD_DIR / f"{file_id}.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.")
    
    if mode == "dinheiro":
        pattern = r"""
        (?:R\$\s?)?
        (?:
            \d{1,3}(?:\.\d{3})*(?:,\d{2})? |
            \d+(?:,\d{2})? |
            (?:um|dois|três|quatro|cinco|seis|sete|oito|nove|dez|cem|mil|milhão|milhões)
            (?:\sde)?\s?(?:reais?|mil(?:hão|hões)?)?
        )
        """
    elif mode == "cpf":
        pattern = r"\d{3}\.\d{3}\.\d{3}-\d{2}"  # CPF simples
    else:
        raise HTTPException(status_code=400, detail="Modo inválido.")

    positions = find_positions_in_pdf(pdf_path, pattern)

    return {"count": len(positions), "matches": positions}