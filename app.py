import streamlit as st
import os
import random
import re
import io
import zipfile
import shutil
import tempfile
from PIL import Image, ImageDraw, ImageFont
import piexif

# --- 1. CẤU HÌNH GIAO DIỆN & TÀNG HÌNH STREAMLIT ---
st.set_page_config(page_title="Công cụ SEO Hình Ảnh PRO", page_icon="🚀", layout="centered")

hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

# --- 2. HÀM HỖ TRỢ XỬ LÝ ---
def sanitize_filename(text):
    text = text.lower()
    s1 = u'àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ'
    s0 = u'aaaaaaaaaaaaaaaaaeeeeeeeeeeeiiiiiooooooooooooooooouuuuuuuuuuuyyyyyd'
    table = str.maketrans(s1, s0, s1.upper())
    text = text.translate(table).replace(' ', '-')
    text = re.sub(r'[^\w\s-]', '', text)
    return re.sub(r'[-\s]+', '-', text).strip('-')

def add_watermark_and_text(img, logo_file, text_to_draw, is_thumbnail=False):
    # 1. Thêm Logo
    if logo_file:
        logo = Image.open(logo_file).convert("RGBA")
        w_logo = int(img.width * 0.10) # 10%
        ratio = w_logo / float(logo.width)
        h_logo = int(float(logo.height) * float(ratio))
        logo = logo.resize((w_logo, h_logo), Image.Resampling.LANCZOS)
        x_logo = img.width - w_logo - 20
        y_logo = img.height - h_logo - 20
        img.paste(logo, (x_logo, y_logo), logo)

    # 2. Thêm Chữ (Nền đen)
    if text_to_draw and is_thumbnail:
        draw = ImageDraw.Draw(img)
        fontsize = int(img.height * 0.06) 
        try:
            # Trên server mây có thể không có Arial, dùng font mặc định tạm
            # Tốt nhất fen up kèm 1 file arial.ttf lên cùng thư mục code
            font = ImageFont.truetype("arial.ttf", fontsize)
        except:
            font = ImageFont.load_default()

        # Dùng textbbox để tính toán
        bbox = draw.textbbox((0, 0), text_to_draw, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        
        x_text = (img.width - text_w) / 2
        margin_bottom = int(img.height * 0.15) 
        y_text = img.height - text_h - margin_bottom
        
        padding = 20
        draw.rectangle((x_text - padding, y_text - padding, x_text + text_w + padding, y_text + text_h + padding), fill="black")
        draw.text((x_text, y_text), text_to_draw, font=font, fill="white")
    
    return img

# --- 3. GIAO DIỆN CHÍNH ---
st.title("🚀 CÔNG CỤ TỐI ƯU SEO HÌNH ẢNH")
st.write("Giải pháp chuẩn hóa hình ảnh hàng loạt. Quà tặng độc quyền từ hệ thống App BĐS của chúng tôi!")

with st.form("seo_form"):
    st.subheader("1. Tải hình ảnh & Logo")
    uploaded_files = st.file_uploader("Kéo thả hình ảnh vào đây (Tối đa 10 ảnh, định dạng JPG/PNG)", type=['jpg', 'jpeg', 'png'], accept_multiple_files=True)
    uploaded_logo = st.file_uploader("Tải Logo của bạn lên (Định dạng PNG, nền trong suốt)", type=['png'])
    
    st.subheader("2. Thông tin SEO (Metadata)")
    col1, col2 = st.columns(2)
    with col1:
        title = st.text_input("Tiêu đề bài viết (Title):")
        author = st.text_input("Tác giả (Author):")
    with col2:
        main_key = st.text_input("Từ khóa chính (Main Keyword):")
        copyright_val = st.text_input("Bản quyền (Copyright):")
        
    tags_input = st.text_area("Từ khóa phụ (Cách nhau bằng dấu phẩy - Dùng làm Tags):", placeholder="VD: mua ban nha dat, can ho cao cap, bat dong san quan 1...")
    
    st.subheader("3. Viết chữ lên ảnh bìa")
    text_on_img = st.text_input("Dòng chữ in lên ảnh đầu tiên (Để trống nếu không muốn):", placeholder="VD: CĂN HỘ CAO CẤP Q1 - GIÁ TỐT")

    submit_button = st.form_submit_button("🚀 CHẠY XỬ LÝ (TỰ ĐỘNG NÉN ZIP)")

# --- 4. LOGIC XỬ LÝ KHI BẤM NÚT ---
if submit_button:
    if not uploaded_files:
        st.error("⚠️ Fen chưa tải ảnh nào lên kìa!")
    elif len(uploaded_files) > 10:
        st.warning("⚠️ Vượt quá giới hạn! Vui lòng chỉ tải tối đa 10 ảnh/lần.")
    elif not all([title, main_key, author, copyright_val]):
        st.error("⚠️ Điền thiếu thông tin SEO rồi (Tiêu đề, Từ khóa, Tác giả, Bản quyền).")
    else:
        with st.spinner('Đang dùng phép thuật xử lý ảnh... 🧙‍♂️'):
            # Sắp xếp ảnh theo tên file (để lấy ảnh số 1 làm ảnh bìa)
            uploaded_files.sort(key=lambda x: x.name)
            
            # Xử lý từ khóa phụ
            pool = [k.strip() for k in tags_input.split(',')] if tags_input else []
            
            # Tạo thư mục tạm trên Server
            temp_dir = tempfile.mkdtemp()
            folder_name = sanitize_filename(title)
            
            for i, file in enumerate(uploaded_files):
                img = Image.open(file).convert('RGBA')
                is_thumb = (i == 0)
                
                # Đóng Logo và Chữ
                img = add_watermark_and_text(img, uploaded_logo, text_on_img, is_thumbnail=is_thumb)
                img = img.convert("RGB")

                # EXIF Metadata
                random_tags = random.sample(pool, min(len(pool), 5)) if pool else []
                t_set = ", ".join([main_key] + random_tags)
                n_set = ", ".join(random_tags)
                
                exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
                exif_dict["0th"][0x9c9b] = title.encode('utf-16le')
                exif_dict["0th"][0x9c9f] = title.encode('utf-16le')
                exif_dict["0th"][0x9c9d] = author.encode('utf-16le')
                exif_dict["0th"][0x8298] = copyright_val.encode('utf-8')
                exif_dict["0th"][0x9c9e] = t_set.encode('utf-16le')
                exif_dict["0th"][0x9c9c] = n_set.encode('utf-16le')
                exif_dict["0th"][0x4746] = 5

                try:
                    exif_bytes = piexif.dump(exif_dict)
                except:
                    exif_bytes = b""
                    
                # Lưu tạm vào thư mục temp
                save_name = f"{folder_name}-{i+1}.jpg"
                img.save(os.path.join(temp_dir, save_name), "JPEG", quality=90, exif=exif_bytes)

            # NÉN FILE ZIP VÀO RAM (Không ghi ra đĩa cứng -> Siêu tốc độ, tự hủy)
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for root_dir, _, files in os.walk(temp_dir):
                    for file in files:
                        file_path = os.path.join(root_dir, file)
                        zip_file.write(file_path, os.path.relpath(file_path, temp_dir))
            
            # Xóa thư mục tạm (Sạch sẽ server)
            shutil.rmtree(temp_dir)

            st.success(f"🎉 Đã xử lý thành công {len(uploaded_files)} ảnh!")
            st.balloons()

            # NÚT DOWNLOAD
            st.download_button(
                label="📥 TẢI FILE ẢNH (ZIP) VỀ MÁY",
                data=zip_buffer.getvalue(),
                file_name=f"{folder_name}-seo.zip",
                mime="application/zip",
                use_container_width=True
            )