import io
import os
import fitz  # PyMuPDF
from PIL import Image


def comprimir_pdf(
    caminho_entrada: str,
    caminho_saida: str,
    qualidade: int = 70,
    dimensao_maxima: int = 900,
) -> None:
    """
    Comprime o PDF aplicando otimização real nas imagens embutidas (estilo iLovePDF).
    
    :param caminho_entrada: Caminho do PDF original.
    :param caminho_saida: Caminho onde o PDF otimizado será salvo.
    :param qualidade: Qualidade JPEG (1-100). 65-75 mantém excelente qualidade e corta muito o peso.
    :param dimensao_maxima: Limite máximo (largura/altura em pixels) para evitar imagens com resolução desnecessária.
    """
    if not os.path.exists(caminho_entrada):
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho_entrada}")

    doc = fitz.open(caminho_entrada)
    tamanho_original = os.path.getsize(caminho_entrada) / 1024

    print(f"Processando: {caminho_entrada} ({tamanho_original:.1f} KB)")
    print(f"Total de páginas: {len(doc)}")

    # Mapeia cada imagem única (xref) e sua respectiva máscara de transparência (smask), se houver
    img_smasks = {}
    for page in doc:
        for img in page.get_images():
            xref = img[0]
            smask = img[1]
            if xref not in img_smasks:
                img_smasks[xref] = smask if smask > 0 else None

    print(f"Total de imagens únicas encontradas: {len(img_smasks)}")

    substituicoes = 0
    for xref, smask_xref in sorted(img_smasks.items()):
        try:
            pix_base = fitz.Pixmap(doc, xref)

            # Carrega a imagem base no PIL
            if pix_base.alpha:
                im_base = Image.frombytes("RGBA", (pix_base.width, pix_base.height), pix_base.samples)
            elif pix_base.n == 1:
                im_base = Image.frombytes("L", (pix_base.width, pix_base.height), pix_base.samples).convert("RGB")
            else:
                im_base = Image.frombytes("RGB", (pix_base.width, pix_base.height), pix_base.samples)

            # Trata transparência e máscara do PDF (evita fundos pretos)
            if smask_xref and smask_xref > 0:
                try:
                    mask_pix = fitz.Pixmap(doc, smask_xref)
                    im_mask = Image.frombytes("L", (mask_pix.width, mask_pix.height), mask_pix.samples)
                    bg = Image.new("RGB", im_base.size, (255, 255, 255))
                    bg.paste(im_base.convert("RGB"), (0, 0), mask=im_mask)
                    pil_img = bg
                except Exception:
                    pil_img = im_base.convert("RGB")
            elif im_base.mode == "RGBA":
                bg = Image.new("RGB", im_base.size, (255, 255, 255))
                bg.paste(im_base, (0, 0), mask=im_base.split()[-1])
                pil_img = bg
            else:
                pil_img = im_base.convert("RGB")

            # Redimensionamento inteligente preservando proporção
            w, h = pil_img.size
            if max(w, h) > dimensao_maxima:
                escala = dimensao_maxima / max(w, h)
                w, h = int(w * escala), int(h * escala)
                pil_img = pil_img.resize((w, h), Image.Resampling.LANCZOS)

            # Codifica a imagem em JPEG com compressão otimizada
            buffer = io.BytesIO()
            pil_img.save(buffer, format="JPEG", quality=qualidade, optimize=True)
            jpeg_bytes = buffer.getvalue()

            stream_original = doc.xref_stream_raw(xref) or b""

            # Apenas substitui se o novo JPEG for realmente menor
            if len(jpeg_bytes) < len(stream_original):
                # Redefine o objeto do PDF limpando referências antigas (smask)
                obj_def = f"<< /Type /XObject /Subtype /Image /Width {w} /Height {h} /ColorSpace /DeviceRGB /BitsPerComponent 8 >>"
                doc.update_object(xref, obj_def)
                # compress=False evita envolver o JPEG em um segundo deflate desnecessário
                doc.update_stream(xref, jpeg_bytes, new=False, compress=False)
                doc.xref_set_key(xref, "Filter", "/DCTDecode")
                substituicoes += 1
        except Exception as e:
            print(f"Aviso ao processar imagem xref {xref}: {e}")

    print(f"Imagens otimizadas: {substituicoes}/{len(img_smasks)}")

    # Salva limpando objetos não referenciados (garbage=4) e comprimindo textos/tabelas (deflate=True)
    doc.save(
        caminho_saida,
        garbage=4,
        deflate=True
    )
    doc.close()

    tamanho_final = os.path.getsize(caminho_saida) / 1024
    economia = (1 - (tamanho_final / tamanho_original)) * 100
    print("\n" + "=" * 45)
    print(f"Original:   {tamanho_original:.1f} KB")
    print(f"Otimizado:  {tamanho_final:.1f} KB")
    print(f"Redução:    {economia:.1f}%")
    print("=" * 45)


def main():
    pdf_original = "ADMISSÃO - COMPETÊNCIA 08-2026.pdf"
    pdf_comprimido = "arquivo_otimizado_adminissao.pdf"

    print("Comprimindo o PDF no estilo iLovePDF...")
    comprimir_pdf(
        caminho_entrada=pdf_original,
        caminho_saida=pdf_comprimido,
        qualidade=65,
        dimensao_maxima=850,
    )
    print(f"\nPronto! PDF otimizado salvo em: {pdf_comprimido}")


if __name__ == "__main__":
    main()
