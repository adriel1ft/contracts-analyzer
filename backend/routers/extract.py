from fastapi import APIRouter, UploadFile, File
from pathlib import Path
from fastapi.responses import JSONResponse
import pymupdf as fitz
from PIL import Image
import io
import os
import base64
from dotenv import load_dotenv

from openai import AsyncOpenAI # <--- CHANGE 1: Use AsyncOpenAI for 'await'

load_dotenv(override=True)

router = APIRouter()

UPLOAD_DIR = Path("temp/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# print # <--- NOTE 1: You had a stray print here.
client = AsyncOpenAI(api_key = OPENAI_API_KEY) # <--- CHANGE 2: Instantiate AsyncOpenAI


async def ocr_with_openai(image: Image.Image) -> str:
    # Converte imagem para bytes (usando 'jpeg' para possivelmente reduzir tamanho/custo)
    buffered = io.BytesIO()
    # Usar 'JPEG' para reduzir o tamanho do payload e possivelmente o custo. 
    # Mantenha 'PNG' se a imagem tiver transparência ou for muito simples.
    image.save(buffered, format="PNG") 
    buffered.seek(0)
    
    # Converte para base64
    base64_image = base64.b64encode(buffered.getvalue()).decode("utf-8")
    
    # Constrói o URI de dados (Data URI)
    # Certifique-se de que o tipo MIME corresponda ao formato de salvamento (PNG, JPEG, etc.)
    mime_type = "image/png" 
    data_uri = f"data:{mime_type};base64,{base64_image}"

    # Chamada da API de OCR correta
    # <--- CRITICAL CHANGE 3: Switched to the standard Chat Completions API structure
    response = await client.chat.completions.create( 
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": [
                # Text part
                {"type": "text", "text": "Extrair todo o texto desta imagem"},
                # Image part using image_url
                {"type": "image_url", "image_url": {"url": data_uri}}
            ]
        }]
    )

    # <--- CHANGE 4: Correctly extracts content from the standard Chat Completion response
    return response.choices[0].message.content


async def extract_text_from_pdf(file_path: str):
    text = ""
    # Abre o arquivo com encoding 'rb' (read binary) - embora fitz o faça internamente, é bom saber
    with fitz.open(file_path) as pdf: 
        for page in pdf:
            page_text = page.get_text()
            if page_text.strip():
                text += page_text + "\n" # Adiciona nova linha para separação
            else:
                # Faz OCR via OpenAI
                # 300 DPI é um bom padrão para OCR
                pix = page.get_pixmap(dpi=300) 
                # Usa .tobytes() com 'png' para garantir formato consistente
                img_bytes = pix.tobytes("png") 
                img = Image.open(io.BytesIO(img_bytes))
                
                # Aguarda a chamada assíncrona
                ocr_text = await ocr_with_openai(img)
                text += ocr_text + "\n" # Adiciona nova linha para separação
    return text

@router.post("/extract-text")
async def extract_text(file: UploadFile = File(...)):
    # ... (Restante do código está correto)
    contents = await file.read()
    file_path = UPLOAD_DIR / file.filename
    with open(file_path, "wb") as f:
        f.write(contents)

    try:
        text = await extract_text_from_pdf(file_path)
        # Retorna o texto extraído
        return {"text": text}
    except Exception as e:
        # Adiciona um tratamento de erro básico
        return JSONResponse(status_code=500, content={"message": f"Erro ao processar PDF: {e}"})
