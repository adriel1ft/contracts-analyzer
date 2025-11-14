from fastapi import APIRouter, HTTPException
from pathlib import Path
from fastapi.responses import JSONResponse
import pymupdf as fitz
from PIL import Image
import io
import os
import base64
import re
from dotenv import load_dotenv

from openai import AsyncOpenAI 

load_dotenv(override=True)

router = APIRouter()

CURRENT_DIR = Path(__file__).parent 

# Sobe um nível (de routers/ para backend/) e depois desce para temp/uploads/
# '..' representa o diretório pai.
UPLOAD_DIR = (CURRENT_DIR / ".." / "temp" / "uploads").resolve()
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = AsyncOpenAI(api_key = OPENAI_API_KEY) 
# --------------------------------------------------------


# --- Funções Reutilizadas do Bloco de Extração (Adaptadas) ---

async def ocr_with_openai(image: Image.Image) -> str:
    """Função de OCR que usa o GPT-4o para extrair texto de uma imagem (página de PDF sem texto)."""
    buffered = io.BytesIO()
    # Usar 'PNG' para manter a qualidade da imagem
    image.save(buffered, format="PNG") 
    base64_image = base64.b64encode(buffered.getvalue()).decode("utf-8")
    mime_type = "image/png" 
    data_uri = f"data:{mime_type};base64,{base64_image}"

    response = await client.chat.completions.create( 
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": "Extrair todo o texto desta imagem"},
                {"type": "image_url", "image_url": {"url": data_uri}}
            ]
        }]
    )
    return response.choices[0].message.content


async def extract_text_from_pdf(file_path: str):
    """Extrai texto do PDF, fazendo OCR via OpenAI se a página estiver vazia."""
    text = ""
    with fitz.open(file_path) as pdf: 
        for page in pdf:
            page_text = page.get_text()
            if page_text.strip():
                text += page_text + "\n"
            else:
                pix = page.get_pixmap(dpi=300) 
                img_bytes = pix.tobytes("png") 
                img = Image.open(io.BytesIO(img_bytes))
                ocr_text = await ocr_with_openai(img)
                text += ocr_text + "\n"
        print('texto extraído')
    return text

# ------------------------------------------------------------------



async def get_anonymization_positions(text: str, mode: str) -> list[dict]:
    """
    Identifica as posições (start e end offsets) das informações sensíveis (CPF ou Dinheiro)"""
    print('começou anonimização')
    positions = []

    if mode == "cpf":
        # 1. Regex para CPF
        # Busca o padrão ###.###.###-##, com ou sem a pontuação/hífen.
        # Usa \b para garantir que não pegue números parciais dentro de outros números.
        # Captura grupos para os separadores.
        cpf_pattern = r'\b\d{3}[.\s]?\d{3}[.\s]?\d{3}[-]?\d{2}\b'
        
        tag = '[CPF_ANONIMIZADO]'

    elif mode == "dinheiro":
            # Padrão 1: Valores numéricos com moeda (R$, $, etc.)
            money_pattern_num = r'(?:R\$|\$|USD|EUR)\s*[\d\.,]+(?:\s*(?:mil|milhão|milhões|bilhões))?(?:\s*de\s*reais)?'
            # Padrão 2: Valores por extenso simples (ex: 'milhões de reais')
            money_pattern_ext = r'(?:milhares?|milh(?:ão|ões)?|bilh(?:ão|ões)?)\s*de\s*reais'
            
            # Combina os padrões usando OR (|)
            pattern = f'({money_pattern_num})|({money_pattern_ext})'
            tag = "VALOR_MONETÁRIO_ANONIMIZADO"
    else:
        # Se um modo inválido for passado, apenas retorna o texto original ou levanta um erro
        raise ValueError("Modo de anonimização inválido. Use 'dinheiro' ou 'cpf'.")
    for match in re.finditer(pattern, text, re.IGNORECASE):
        # Coleta o início e o fim da correspondência (offsets)
        positions.append({
            "start": match.start(),
            "end": match.end(),
            "tag": tag
        })
    print('terminou anonimização')
    
    return positions

@router.post("/anonymize/positions/{mode}/{file_id}")
async def anonymize_document(mode: str, file_id: str):
    """
    Endpoint principal para anonimizar um documento:
    1. Localiza o arquivo.
    2. Extrai o texto (incluindo OCR).
    3. Anonimiza o texto com a OpenAI.
    4. Retorna o texto anonimizado.
    """
    # 1. Localiza o Arquivo
    # Presumindo que o arquivo foi previamente salvo como '{file_id}.pdf' 
    # pelo seu endpoint de upload/extração original.
    file_path = UPLOAD_DIR / f"{file_id}.pdf"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Arquivo '{file_id}.pdf' não encontrado.")

    if mode not in ["dinheiro", "cpf"]:
        raise HTTPException(status_code=400, detail="Modo de anonimização inválido. Use 'dinheiro' ou 'cpf'.")

    try:
        # 2. Extrai o Texto (incluindo OCR, se necessário)
        original_text = await extract_text_from_pdf(file_path)

        # 3. Anonimiza o Texto com a OpenAI
        anonymized_positions = await get_anonymization_positions(original_text, mode)

        # 4. Retorna o Texto Anonimizado
        return JSONResponse(status_code=200, content={
            "file_id": file_id,
            "mode": mode,
            "anonymized_positions": anonymized_positions
        })

    except ValueError as e:
            # Captura erros internos da função de Regex (se o modo for inválido, por exemplo)
        return JSONResponse(status_code=400, content={"message": str(e)})

    except Exception as e:
            # Tratamento de erros gerais
            return JSONResponse(status_code=500, content={"message": f"Erro interno ao processar a anonimização: {e}"})