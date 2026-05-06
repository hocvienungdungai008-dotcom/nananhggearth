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
    st.session_state['input_string'] = "" # Biến để quản lý ô nhập tọa độ

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
        
        # Liên kết ô text_area với session_state để có thể xóa trắng sau khi bấm
        st.text_area("Chuỗi tọa độ:", key="input_string", height=100)
        
        if st.button("➕ Thêm điểm mốc này", type="primary", use_container_width=True):
            if st.session_state['last_pixel'] is None:
                st.error("⚠️ Hãy click chọn điểm trên ảnh ở màn hình chính trước!")
            elif not st.session_state['input_string'].strip():
                st.error("⚠️ Hãy dán tọa độ vào ô trống!")
            else:
                # --- THUẬT TOÁN BÓC TÁCH TỌA ĐỘ (REGEX) ---
                text = st.session_state['input_string']
                lng, lat = None, None
                
                # Tìm chính xác cụm lng và lat bất chấp dấu nháy kép hay đơn
                match_lng = re.search(r"lng:\s*['\"]?([\d.]+)['\"]?", text)
                match_lat = re.search(r"lat:\s*['\"]?([\d.]+)['\"]?", text)
                
                if match_lng and match_lat:
                    lng = float(match_lng.group(1))
                    lat = float(match_lat.group(1))
                else:
                    # Dự phòng: Nếu người dùng chỉ dán 2 con số (VD: 105.97 10.08)
                    nums = re.findall(r"\d+\.\d+", text)
                    if len(nums) >= 2:
                        lng = float(nums[0])
                        lat = float(nums[1])
                
                if lng is None or lat is None:
                    st.error("❌ Không thể đọc được tọa độ từ chuỗi bạn dán. Vui lòng kiểm tra lại định dạng!")
                else:
                    px, py = st.session_state['last_pixel']
                    st.session_state['gcp_list'].append({
                        'Pixel_X': px, 'Pixel_Y': py, 'Kinh độ': lng, 'Vĩ độ': lat
                    })
                    
                    # --- RESET DỮ LIỆU ĐỂ TRÁNH NHẦM LẪN ---
                    st.session_state['last_pixel'] = None # Hủy chọn mốc trên ảnh
                    st.session_state['input_string'] = "" # Xóa trắng ô dán chữ
                    st.rerun() # Tải lại giao diện ngay lập tức

        st.divider()
        st.subheader(f"3. Danh sách mốc ({len(st.session_state['gcp_list'])} điểm)")
        if st.session_state['gcp_list']:
            st.dataframe(st.session_state['gcp_list'], hide_index=True) 
            if st.button("🗑️ Xóa toàn bộ", use_container_width=True):
                st.session_state['gcp_list'] = []
                st.rerun()

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
    
    # 4. Xuất File (ĐÃ FIX LỖI GDAL WARP)
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
                    
                    # Bước 1: Gắn GCPs vào một tệp ảo trên RAM (vsimem) thay vì đĩa cứng
                    vrt_path = '/vsimem/temp.vrt'
                    vrt = gdal.Translate(vrt_path, ds, format='VRT', GCPs=gcps, outputSRS=srs.ExportToWkt())
                    
                    # Bước 2: Nắn ảnh từ VRT ảo sang TIF thực. Truyền trực tiếp kwargs thay vì WarpOptions
                    gdal.Warp(output_tif, vrt, format='GTiff', polynomialOrder=1, dstSRS='EPSG:4326')
                    
                    # Giải phóng bộ nhớ và file ảo (Cực kỳ quan trọng để Streamlit không bị lỗi sập app)
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
