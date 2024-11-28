import streamlit as st
import tempfile
import pymupdf  # PyMuPDF
import difflib
import pdfplumber
import io
from PIL import Image, ImageChops, ImageDraw
import fitz
import os
import zipfile

# Streamlitの表示をデフォルトでWide modeにする
st.set_page_config(layout="wide")

st.title("PDF Diff Viewer")

# PDFファイルのアップロード
pdf1 = st.file_uploader("Upload first PDF", type="pdf")
pdf2 = st.file_uploader("Upload second PDF", type="pdf")

# ハイライトの色、四角の色、線の太さのカスタマイズオプション
st.sidebar.header("Highlight Options")
highlight_color = st.sidebar.color_picker("Highlight Color", "#FF0000")
box_color = st.sidebar.color_picker("Box Color", "#0000FF")
deleted_box_color = st.sidebar.color_picker("Deleted Box Color", "#FF0000") # 削除された部分の色のオプション
line_width = st.sidebar.slider("Line Width", 1, 5, 2)
show_deleted_boxes = st.sidebar.checkbox("Show Deleted Boxes", False)
show_updated_boxes = st.sidebar.checkbox("Show Updated Boxes", True) # 更新された部分の表示オプション
show_html = st.sidebar.checkbox("Show HTML Diff", True) # HTML表示の有無を選択するオプション
show_diff_image = st.sidebar.checkbox("Show Diff Image", True) # 差分画像表示の有無を選択するオプション

def extract_text_from_pdf(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        text = ""
        for page in pdf.pages:
            text += page.extract_text()
    return text

def compare_pdfs(pdf1_path, pdf2_path):
    doc1 = fitz.open(pdf1_path)
    doc2 = fitz.open(pdf2_path)

    num_pages = min(len(doc1), len(doc2))

    if len(doc1) != len(doc2):
        st.warning(f"PDFファイルのページ数が異なります。少ない方のページ数({num_pages})まで比較します。")

    # すべてのページのHTMLと差分画像を保存する一時ディレクトリ
    with tempfile.TemporaryDirectory() as temp_dir:
        for page_num in range(num_pages):
            page1 = doc1[page_num]
            page2 = doc2[page_num]

            text1 = page1.get_text("words")
            text2 = page2.get_text("words")

            st.header(f"Page {page_num + 1}")  # ページ番号を表示
            diff = difflib.HtmlDiff().make_file([word[4] for word in text1], [word[4] for word in text2])

            # 結果のHTMLを一時ファイルに保存
            html_path = os.path.join(temp_dir, f"page_{page_num + 1}_diff.html")
            with open(html_path, "w") as f:
                f.write(diff)
            st.download_button(
                label=f"Download HTML for Page {page_num + 1}",
                data=open(html_path, 'rb').read(),
                file_name=f"page_{page_num + 1}_diff.html",
                mime="text/html",
            )

            # HTML表示の有無によって表示を制御
            if show_html:
                st.components.v1.html(diff, height=500, scrolling=True)

            # 比較結果を画像として表示
            pix1 = page1.get_pixmap()
            pix2 = page2.get_pixmap()

            # 画像をPIL Imageオブジェクトに変換
            img1 = Image.open(io.BytesIO(pix1.tobytes()))
            img2 = Image.open(io.BytesIO(pix2.tobytes()))

            # img1をコピーして、差分をハイライト表示する画像を作成
            img1_highlighted = img1.copy()
            draw1 = ImageDraw.Draw(img1_highlighted)
            img2_highlighted = img2.copy()
            draw2 = ImageDraw.Draw(img2_highlighted)

            # 差分をハイライト
            i = 0
            j = 0
            while i < len(text1) and j < len(text2):
                if text1[i][4] == text2[j][4]:
                    i += 1
                    j += 1
                else:
                    # first PDF: 削除された文字をハイライト
                    if show_deleted_boxes and i < len(text1):
                        x0, y0, x1, y1 = text1[i][:4]
                        draw1.rectangle([(x0, y0), (x1, y1)], outline=deleted_box_color, width=line_width)
                    # second PDF: 追加/変更された文字をハイライト
                    if show_updated_boxes and j < len(text2):
                        x0, y0, x1, y1 = text2[j][:4]
                        draw2.rectangle([(x0, y0), (x1, y1)], outline=box_color, width=line_width)
                    i += 1
                    j += 1
            # first PDF: 残りの削除された文字をハイライト
            if show_deleted_boxes:
                while i < len(text1):
                    x0, y0, x1, y1 = text1[i][:4]
                    draw1.rectangle([(x0, y0), (x1, y1)], outline=deleted_box_color, width=line_width)
                    i += 1
            # second PDF: 残りの追加された文字をハイライト
            if show_updated_boxes:
                while j < len(text2):
                    x0, y0, x1, y1 = text2[j][:4]
                    draw2.rectangle([(x0, y0), (x1, y1)], outline=box_color, width=line_width)
                    j += 1

            # img1_highlightedとimg2_highlightedを横に並べて表示
            img_combined = Image.new("RGB", (img1_highlighted.width + img2_highlighted.width, img2_highlighted.height))
            img_combined.paste(img1_highlighted, (0, 0))
            img_combined.paste(img2_highlighted, (img1_highlighted.width, 0))

            # 差分画像を一時ファイルに保存
            img_path = os.path.join(temp_dir, f"page_{page_num + 1}_diff.png")
            img_combined.save(img_path, "PNG")
            st.download_button(
                label=f"Download Diff Image for Page {page_num + 1}",
                data=open(img_path, 'rb').read(),
                file_name=f"page_{page_num + 1}_diff.png",
                mime="image/png",
            )

            # 差分画像表示の有無によって表示を制御
            if show_diff_image:
                st.image(img_combined, caption=f"Page {page_num + 1} Comparison", use_container_width=True)

        # すべてのHTMLと差分画像をzipファイルに圧縮
        zip_path = os.path.join(temp_dir, "all_diffs.zip")
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for file in os.listdir(temp_dir):
                if file.endswith((".html", ".png")):
                    zipf.write(os.path.join(temp_dir, file), file)

        # zipファイルをダウンロード
        st.sidebar.download_button(
            label="Download All Diffs",
            data=open(zip_path, 'rb').read(),
            file_name="all_diffs.zip",
            mime="application/zip",
        )

if pdf1 and pdf2:
    # 一時ファイルを作成
    with tempfile.NamedTemporaryFile(delete=False) as tmp1:
        tmp1.write(pdf1.read())
        pdf1_path = tmp1.name
    
    with tempfile.NamedTemporaryFile(delete=False) as tmp2:
        tmp2.write(pdf2.read())
        pdf2_path = tmp2.name

    # PDFの比較
    compare_pdfs(pdf1_path, pdf2_path)

    # 一時ファイルの削除
    import os
    os.remove(pdf1_path)
    os.remove(pdf2_path)

# 他の機能も必要に応じて追加
