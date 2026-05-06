import streamlit as st
from streamlit_image_coordinates import streamlit_image_coordinates
from PIL import Image
import os
import re
from osgeo import gdal, osr

# Cấu hình trang
st.set_page_config(page_title="Tool Georeferencing Lưới Điện", layout="wide")

# Khởi tạo các biến nhớ (session state)
if 'gcp_list' not in st.session_state:
    st.session_state['gcp_list'] = []
if 'last_pixel' not in st.session_state:
    st.session_state['last_pixel'] = None
if 'input_string' not in st.session_state:
    st.session_state['input_string'] = ""
if 'ui_msg' not in st.session_state:
    st.session_state['ui_msg'] = None # Biến để hiển thị thông báo lỗi/thành công

# ==========================================
# HÀM XỬ LÝ DỮ LIỆU TỌA ĐỘ (CALLBACK)
# ==========================================
def process_add_point():
    # Reset thông báo cũ
    st.session_state['ui_msg'] = None 
    
    # Kiểm tra điều kiện
    if st.session_state['last_pixel'] is None:
        st.session_state['ui_msg'] = ("error", "⚠️ Hãy click chọn điểm trên ảnh ở màn hình chính trước!")
        return
        
    text = st.session_state['input_string']
    if not text.strip():
        st.session_state['ui_msg'] = ("error", "⚠️ Hãy dán tọa độ vào ô trống!")
        return

    # Thuật toán bóc tách tọa độ
    lng, lat = None, None
    match_lng = re.search(r"lng:\s*['\"]?([\d.]+)['\"]?", text)
    match_lat = re.search(r"lat:\s*['\"]?([\d.]+)['\"]?", text)
    
    if match_lng and match_lat:
        lng = float(match_lng.group(1))
        lat = float(match_lat.group(1))
    else:
        nums = re.findall(r"\d+\.\d+", text)
        if len(nums) >= 2:
            lng = float(nums[0])
            lat = float(nums[1])
            
    # Xử lý kết quả
    if lng is None or lat is None:
        st.session_state['ui_msg'] = ("error", "❌ Không thể đọc được tọa độ từ chuỗi bạn dán. Vui lòng kiểm tra lại định dạng!")
    else:
        px, py = st.session_state['last_pixel']
        st.session_state['gcp_list'].append({
            'Pixel_X': px, 'Pixel_Y': py, 'Kinh độ': lng, 'Vĩ độ': lat
        })
        
        # --- RESET DỮ LIỆU AN TOÀN TRONG CALLBACK ---
        st.session_state['last_pixel'] = None # Hủy chọn mốc trên ảnh
        st.session_state['input_string'] = "" # Xóa trắng ô dán chữ (Lúc này widget chưa load nên không bị lỗi)

# ==========================================
# KHU VỰC 1: THANH BÊN (SIDEBAR) - BẢNG ĐIỀU KHIỂN
# ==========================================
with st.sidebar:
    st.title("⚙️ Bảng Điều Khiển")
    
    uploaded_file = st.file_uploader("1. Tải sơ đồ (JPG/PNG)", type=["jpg", "jpeg", "png"])
    zoom_level = 800 

    if uploaded_file:
        st.divider()
        st.subheader("🔍 Công cụ Zoom")
        zoom_level = st.slider("Kéo để phóng to/thu nhỏ ảnh", min_value=500, max_value=3000, value=1000, step=100)

        st.divider()
        st.subheader("2. Nhập Tọa độ Thực tế")
        st.caption("Dán nguyên chuỗi copy từ hệ thống vào đây (VD: Tọa độ: (lng: '105.9...',lat:'10.08...'))")
        
        # Ô nhập liệu
        st.text_area("Chuỗi tọa độ:", key="input_string", height=100)
        
        # Nút bấm GỌI HÀM CALLBACK (on_click)
        st.button("➕ Thêm điểm mốc này", type="primary", use_container_width=True, on_click=process_add_point)
        
        # Hiển thị thông báo (nếu có lỗi từ hàm callback truyền ra)
        if st.session_state['ui_msg']:
            msg_type, msg_text = st.session_state['ui_msg']
            if msg_type == "error": st.error(msg_text)
            elif msg_type == "success": st.success(msg_text)

        st.divider()
        st.subheader(f"3. Danh sách mốc ({len(st.session_state['gcp_list'])} điểm)")
        if st.session_state['gcp_list']:
            st.dataframe(st.session_state['gcp_list'], hide_index=True) 
            
            # Hàm xóa toàn bộ
            def clear_all():
                st.session_state['gcp_list'] = []
            st.button("🗑️ Xóa toàn bộ", use_container_width=True, on_click=clear_all)

# ==========================================
# KHU VỰC 2: MÀN HÌNH CHÍNH - HIỂN THỊ ẢNH
# ==========================================
st.title("📍 Khu Vực Chấm Điểm Sơ Đồ")

if not uploaded_file:
    st.info("👈 Vui lòng tải một bức ảnh sơ đồ ở thanh công cụ bên trái để bắt đầu.")
else:
    img = Image.open(uploaded_file)
    img_path = "input_temp.jpg"
    img.save(img_path)

    if st.session_state['last_pixel'] is None:
        st.info("👆 Hãy di chuột và CLICK vào một vị trí trên ảnh. Dùng thanh trượt 'Zoom' bên trái để nhìn rõ hơn.")
    else:
        st.success(f"🎯 Đã khóa mục tiêu Pixel: {st.session_state['last_pixel']}. Dán tọa độ vào bên trái và bấm Thêm!")

    value = streamlit_image_coordinates(img, width=zoom_level, key="image_coords")
    
    if value and (st.session_state['last_pixel'] is None or st.session_state['last_pixel'] != (value['x'], value['y'])):
        st.session_state['last_pixel'] = (value['x'], value['y'])
        st.rerun()

    st.divider()
    
    # 4. Xuất File GDAL WARP
    if len(st.session_state['gcp_list']) >= 3:
        if st.button("🚀 XUẤT FILE GEOTIFF ĐỂ XEM TRÊN GOOGLE EARTH", type="primary", use_container_width=True):
            try:
                with st.spinner("Đang xử lý nắn ảnh bằng GDAL..."):
                    output_tif = "output_map.tif"

                    gcps = []
                    for p in st.session_state['gcp_list']:
                        gcps.append(gdal.GCP(p['Kinh độ'], p['Vĩ độ'], 0, p['Pixel_X'], p['Pixel_Y']))

                    srs = osr.SpatialReference()
                    srs.ImportFromEPSG(4326)

                    ds = gdal.Open(img_path)
                    
                    vrt_path = '/vsimem/temp.vrt'
                    vrt = gdal.Translate(vrt_path, ds, format='VRT', GCPs=gcps, outputSRS=srs.ExportToWkt())
                    
                    gdal.Warp(output_tif, vrt, format='GTiff', polynomialOrder=1, dstSRS='EPSG:4326')
                    
                    vrt = None
                    ds = None
                    gdal.Unlink(vrt_path)
                    
                    st.success("🎉 Đã tạo file GeoTIFF thành công!")
                    
                    with open(output_tif, "rb") as file:
                        st.download_button(
                            label="📥 TẢI XUỐNG BẢN ĐỒ (.TIF)",
                            data=file,
                            file_name="so_do_luoi_dien.tif",
                            mime="image/tiff",
                            type="primary"
                        )
            except Exception as e:
                st.error(f"Lỗi khi xử lý GDAL: {e}")
    elif uploaded_file:
        st.warning(f"Cần ít nhất 3 điểm mốc để xuất file (Hiện tại: {len(st.session_state['gcp_list'])}/3).")
